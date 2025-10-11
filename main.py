import os
import tempfile
import uuid
import time
import asyncio
import shutil
import logging
import re
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from contextlib import asynccontextmanager

import aiofiles
import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from pydub import AudioSegment
import yt_dlp

from faster_whisper import WhisperModel
# whisperx 延遲導入以避免 NumPy 2.0 相容性問題
# import whisperx
import torch
import gc
import nltk
from nltk.tokenize import sent_tokenize

# 導入歷史紀錄相關模組
from database import get_db
from file_manager import get_file_manager

# 導入 YouTube 相關模組
from youtube_metadata_extractor import get_youtube_metadata_extractor, YouTubeMetadata
from youtube_download_manager import get_youtube_download_manager

# 導入錯誤處理和驗證模組
from error_handling import (
    HistoryAPIException, ValidationException, FileAccessException, TaskNotFoundException,
    ErrorCodes, TaskSearchRequest, TaskCreateRequest, InputSanitizer, get_file_access_validator
)
from middleware import ErrorHandlingMiddleware, RequestLoggingMiddleware, SecurityMiddleware

# 導入維護功能模組
from maintenance_scheduler import get_maintenance_scheduler, MaintenanceConfig, MaintenanceLevel

# 導入效能最佳化和 UX 改進模組
from performance_optimizer import (
    get_cache, get_performance_monitor, get_query_optimizer,
    PerformanceMiddleware, cache_cleanup_task, generate_performance_report
)
from ux_improvements import (
    get_ux_manager, send_websocket_notification, send_websocket_progress,
    track_user_action, with_loading_state
)

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 全局變量
TEMP_DIR = Path("temp")
SUPPORTED_FORMATS = ["mp3", "wav", "m4a", "flac", "ogg"]
MODEL = None
ALIGN_MODEL = None
DIARIZE_MODEL = None
ACTIVE_CLIENTS = {}
MODELS_DIR = Path("models")
SEGMENTATION_MODEL_PATH = MODELS_DIR / "segmentation-3.0"
DIARIZATION_MODEL_PATH = MODELS_DIR / "speaker-diarization-3.1"

# 確保環境變量可用
try:
    HUGGINGFACE_TOKEN = os.environ.get("HUGGINGFACE_TOKEN", None)
    if HUGGINGFACE_TOKEN:
        print("已設置 Hugging Face token")
    else:
        print("未設置 Hugging Face token，將使用默認設置")
except Exception as e:
    print(f"獲取環境變量時出錯: {str(e)}")
    HUGGINGFACE_TOKEN = None

# 初始化臨時目錄
TEMP_DIR.mkdir(exist_ok=True)

# 確保模型目錄存在
MODELS_DIR.mkdir(exist_ok=True)

# 模型初始化
def init_models():
    global MODEL, DIARIZE_MODEL
    if MODEL is None:
        print("正在加載 Whisper 模型...")
        MODEL = WhisperModel("medium", device="cuda", compute_type="float16")
        print("Whisper 模型已加載")
        #tiny、base、small、medium、large
    
    if DIARIZE_MODEL is None:
        # 延遲導入 whisperx
        try:
            import whisperx
        except ImportError as e:
            print(f"無法導入 whisperx: {e}")
            print("說話者識別功能將不可用")
            DIARIZE_MODEL = None
            return
        # 檢查本地模型是否存在
        if SEGMENTATION_MODEL_PATH.exists() and DIARIZATION_MODEL_PATH.exists():
            try:
                print("正在預載本地說話者識別模型...")
                # 修正：正確使用 DiarizationPipeline，不再嘗試傳入本地模型路徑
                DIARIZE_MODEL = whisperx.DiarizationPipeline(use_auth_token=False, device="cuda")
                print("本地說話者識別模型已預載")
            except Exception as e:
                print(f"預載本地說話者識別模型時出錯: {str(e)}")
                # 如果本地模型加載失敗且有 token，嘗試在線模型
                if HUGGINGFACE_TOKEN:
                    try:
                        print("嘗試預載在線說話者識別模型...")
                        DIARIZE_MODEL = whisperx.DiarizationPipeline(use_auth_token=HUGGINGFACE_TOKEN, device="cuda")
                        print("在線說話者識別模型已預載")
                    except Exception as e:
                        print(f"預載在線說話者識別模型時出錯: {str(e)}")
                        DIARIZE_MODEL = None
                else:
                    DIARIZE_MODEL = None
        elif HUGGINGFACE_TOKEN:
            try:
                print("本地模型不存在，正在預載在線說話者識別模型...")
                DIARIZE_MODEL = whisperx.DiarizationPipeline(use_auth_token=HUGGINGFACE_TOKEN, device="cuda")
                print("在線說話者識別模型已預載")
            except Exception as e:
                print(f"預載在線說話者識別模型時出錯: {str(e)}")
                DIARIZE_MODEL = None
        else:
            print("本地模型不存在且無 Hugging Face token，跳過預載說話者識別模型")
            DIARIZE_MODEL = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在非同步上下文中初始化模型
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, init_models)

    def check_dependencies():
        try:
            import nltk
            print("NLTK 已安裝")
        except ImportError:
            print("警告: NLTK 未安裝，segmentation-3.0 功能將不可用")
            print("請安裝: pip install nltk")
            return False
        return True
    
    # 在啟動時調用
    dependencies_ok = check_dependencies()
    
    # 初始化維護排程器
    try:
        maintenance_config = MaintenanceConfig(
            cleanup_enabled=True,
            cleanup_interval_hours=24,
            task_retention_days=30,
            failed_task_retention_days=7,
            disk_monitor_enabled=True,
            disk_monitor_interval_minutes=30,
            disk_warning_threshold_percent=80.0,
            disk_critical_threshold_percent=90.0,
            auto_cleanup_on_critical=True,
            db_optimize_enabled=True,
            db_optimize_interval_hours=168,
            vacuum_threshold_mb=100
        )
        
        scheduler = get_maintenance_scheduler(maintenance_config)
        await scheduler.start()
        logger.info("維護排程器已啟動")
        
    except Exception as e:
        logger.error(f"初始化維護排程器失敗: {e}")
    
    # 啟動快取清理任務
    try:
        asyncio.create_task(cache_cleanup_task())
        logger.info("快取清理任務已啟動")
    except Exception as e:
        logger.error(f"啟動快取清理任務失敗: {e}")
    
    yield  # 這裡是 FastAPI 運行的地方
    
    # 停止維護排程器
    try:
        scheduler = get_maintenance_scheduler()
        if scheduler.is_running:
            await scheduler.stop()
            logger.info("維護排程器已停止")
    except Exception as e:
        logger.error(f"停止維護排程器失敗: {e}")
    
    # 清理所有臨時文件 (原來的 shutdown_event 函數)
    try:
        for file in TEMP_DIR.glob("*"):
            file.unlink()
    except Exception as e:
        print(f"清理臨時文件時出錯: {str(e)}")

# 初始化 FastAPI 應用
app = FastAPI(
    title="Faster Whisper STT API", 
    description="語音轉文字 API，兼容 OpenAI 格式",
    lifespan=lifespan
)

# 添加錯誤處理中介軟體
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityMiddleware)
app.add_middleware(PerformanceMiddleware)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂載靜態文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 響應模型
class TranscriptionResponse(BaseModel):
    text: str
    segments: Optional[List[Dict[str, Any]]] = None
    speakers: Optional[List[Dict[str, Any]]] = None

# 歷史紀錄相關響應模型
class TaskHistoryResponse(BaseModel):
    tasks: List[Dict[str, Any]]
    total: int
    page: int
    limit: int
    has_next: bool

class TaskDetailResponse(BaseModel):
    task: Dict[str, Any]
    files: List[Dict[str, Any]]

# WebSocket 管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_message(self, client_id: str, message: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)
            
    async def send_json(self, client_id: str, data: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(data)

manager = ConnectionManager()


# ==================== WhisperX 輔助函數 ====================

def convert_to_whisperx_format(segments):
    """將 Faster Whisper 的結果轉換為 WhisperX 格式"""
    try:
        logger.info(f"將 {len(segments)} 個文字段落轉換為 WhisperX 格式")

        whisperx_segments = []
        for i, segment in enumerate(segments):
            # 確保文本不為空
            if not segment.get("text") or len(segment["text"].strip()) == 0:
                continue

            whisperx_segment = {
                "id": i,
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"],
                "words": []
            }

            # 計算每個詞的平均時間長度
            words = segment["text"].split()
            if len(words) > 0:  # 防止除以零錯誤
                avg_word_duration = (segment["end"] - segment["start"]) / len(words)

                for j, word in enumerate(words):
                    word_start = segment["start"] + j * avg_word_duration
                    word_end = word_start + avg_word_duration
                    if word_end > segment["end"]:
                        word_end = segment["end"]

                    whisperx_segment["words"].append({
                        "word": word,
                        "start": word_start,
                        "end": word_end
                    })

                whisperx_segments.append(whisperx_segment)

        return {
            "segments": whisperx_segments
        }
    except Exception as e:
        logger.error(f"轉換為 WhisperX 格式時出錯: {e}")
        import traceback
        traceback.print_exc()
        return {"segments": []}


def convert_from_whisperx_format(whisperx_result):
    """從 WhisperX 格式轉換回我們的格式"""
    try:
        logger.info("從 WhisperX 格式轉換回原格式")

        segments = []
        if not isinstance(whisperx_result, dict) or "segments" not in whisperx_result:
            logger.error(f"無效的 WhisperX 結果格式: {type(whisperx_result)}")
            return segments

        for segment in whisperx_result["segments"]:
            our_segment = {
                "id": segment.get("id", 0),
                "text": segment.get("text", ""),
                "start": segment.get("start", 0),
                "end": segment.get("end", 0)
            }

            # 添加說話者信息
            if "speaker" in segment:
                our_segment["speaker"] = segment["speaker"]

            segments.append(our_segment)

        return segments
    except Exception as e:
        logger.error(f"從 WhisperX 格式轉換時出錯: {e}")
        import traceback
        traceback.print_exc()
        return []


def perform_diarization_with_whisperx(audio_path, whisperx_result):
    """使用 WhisperX 執行說話者識別"""
    try:
        logger.info("開始執行說話者識別...")

        # 檢查輸入格式
        if not isinstance(whisperx_result, dict) or "segments" not in whisperx_result:
            logger.error(f"無效的 whisperX 格式: {type(whisperx_result)}")
            return whisperx_result

        # 確保有足夠的文字段落進行分析
        if len(whisperx_result["segments"]) == 0:
            logger.warning("沒有文字段落可供分析")
            return whisperx_result

        # 延遲導入 whisperx
        try:
            import whisperx
        except ImportError as e:
            logger.error(f"無法導入 whisperx: {e}")
            return whisperx_result

        # 使用全局 DIARIZE_MODEL 或創建新實例
        global DIARIZE_MODEL
        diarize_model = DIARIZE_MODEL

        if diarize_model is None:
            # 檢查本地模型是否存在
            if SEGMENTATION_MODEL_PATH.exists() and DIARIZATION_MODEL_PATH.exists():
                logger.info("使用本地預下載的說話者識別模型")
                try:
                    diarize_model = whisperx.DiarizationPipeline(use_auth_token=False, device="cuda")
                    logger.info("已成功初始化說話者識別模型")
                except Exception as e:
                    logger.error(f"使用本地模型初始化失敗: {str(e)}")
                    # 如果本地模型加載失敗，回退到在線模型
                    if HUGGINGFACE_TOKEN:
                        logger.info("回退到使用 Hugging Face token 初始化")
                        diarize_model = whisperx.DiarizationPipeline(use_auth_token=HUGGINGFACE_TOKEN, device="cuda")
                    else:
                        logger.error("無法初始化說話者識別模型，無法執行說話者分離")
                        return whisperx_result
            elif HUGGINGFACE_TOKEN:
                logger.info("本地模型不存在，使用 Hugging Face token 初始化")
                diarize_model = whisperx.DiarizationPipeline(use_auth_token=HUGGINGFACE_TOKEN, device="cuda")
            else:
                logger.warning("無 Hugging Face token，無法執行說話者識別")
                return whisperx_result

        # 執行說話者分離
        logger.info(f"處理音頻文件: {audio_path}")
        diarize_segments = diarize_model(str(audio_path))

        logger.info(f"說話者識別結果: {len(diarize_segments)} 個段落")

        # 分配說話者到文字段落
        logger.info("將說話者分配到文字段落...")
        result_with_speakers = whisperx.assign_word_speakers(diarize_segments, whisperx_result)

        logger.info("說話者識別完成")
        return result_with_speakers
    except Exception as e:
        logger.error(f"說話者識別出錯: {str(e)}")
        import traceback
        traceback.print_exc()
        return whisperx_result


# ==================== 主要路由 ====================

@app.get("/")
async def read_root():
    """返回主頁面"""
    return FileResponse("static/index.html")

# ==================== 語音轉文字 API ====================

@app.post("/v1/audio/transcriptions")
async def transcribe_audio(
    file: Optional[UploadFile] = File(None),
    youtube_url: Optional[str] = Form(None),
    model: str = Form("whisper-1"),
    response_format: str = Form("json"),
    temperature: Optional[float] = Form(0),
    language: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    with_diarization: bool = Form(False),
    vad_filter: bool = Form(False),
    min_silence_duration_ms: int = Form(500),
    speech_pad_ms: int = Form(400),
    download_video: bool = Form(False),
    download_thumbnail: bool = Form(True)
):
    """
    語音轉文字 API，相容 OpenAI Whisper API 格式
    支援檔案上傳和 YouTube URL
    """
    try:
        # 驗證輸入
        if not file and not youtube_url:
            raise HTTPException(status_code=400, detail="必須提供檔案或 YouTube URL")
        
        if file and youtube_url:
            raise HTTPException(status_code=400, detail="不能同時提供檔案和 YouTube URL")
        
        # 生成任務 ID
        task_id = str(uuid.uuid4())
        
        # 初始化資料庫和檔案管理器
        db = await get_db()
        file_manager = get_file_manager()
        
        # 建立任務記錄
        task_data = {
            'name': file.filename if file else f"YouTube: {youtube_url}",
            'source_type': 'file' if file else 'youtube',
            'source_info': file.filename if file else youtube_url,
            'model_used': model,
            'language': language,
            'status': 'processing'
        }

        # 建立任務資料夾
        task_folder = file_manager.create_task_folder(task_id, task_data['name'])
        task_data['task_folder'] = str(task_folder)
        
        # 插入任務記錄到資料庫
        await db.create_task(task_data, task_id)
        
        # 處理檔案或 YouTube URL
        if file:
            # 處理上傳的檔案
            audio_path = task_folder / "original.mp3"
            
            # 保存上傳的檔案
            async with aiofiles.open(audio_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            # 記錄檔案資訊
            await db.add_task_file(task_id, {
                'file_type': 'audio',
                'file_name': 'original.mp3',
                'file_path': str(audio_path),
                'file_size': len(content)
            })
            
        else:
            # 處理 YouTube URL
            try:
                # 下載 YouTube 音訊
                youtube_manager = get_youtube_download_manager()
                metadata_extractor = get_youtube_metadata_extractor()
                
                # 取得影片元資料
                metadata = await metadata_extractor.extract_metadata(youtube_url)

                # 更新任務名稱為清理過的影片標題
                if metadata and metadata.title:
                    task_data['name'] = InputSanitizer.sanitize_filename(metadata.title)

                # 根據選項決定下載內容
                if download_video:
                    # 同時下載音訊和影片
                    audio_path, video_path = await youtube_manager.download_audio_and_video(
                        youtube_url,
                        task_folder
                    )

                    # 記錄影片檔案
                    if video_path and video_path.exists():
                        video_size = video_path.stat().st_size
                        await db.add_task_file(task_id, {
                            'file_type': 'video',
                            'file_name': video_path.name,
                            'file_path': str(video_path),
                            'file_size': video_size
                        })
                else:
                    # 僅下載音訊
                    audio_output_path = task_folder / "original.mp3"
                    audio_path = await youtube_manager.download_audio_only(
                        youtube_url,
                        audio_output_path
                    )

                # 下載縮圖 (如果需要)
                if download_thumbnail and metadata:
                    thumbnail_output_path = task_folder / f"{metadata.title}_thumbnail.jpg"
                    thumbnail_path = await youtube_manager.download_thumbnail(
                        youtube_url,
                        thumbnail_output_path
                    )

                    # 記錄縮圖檔案
                    if thumbnail_path and thumbnail_path.exists():
                        thumbnail_size = thumbnail_path.stat().st_size
                        await db.add_task_file(task_id, {
                            'file_type': 'thumbnail',
                            'file_name': thumbnail_path.name,
                            'file_path': str(thumbnail_path),
                            'file_size': thumbnail_size
                        })

                # 更新任務資訊
                if metadata:
                    await db.update_task_metadata(task_id, metadata.to_dict())

                # 記錄音訊檔案
                if audio_path and audio_path.exists():
                    file_size = audio_path.stat().st_size
                    await db.add_task_file(task_id, {
                        'file_type': 'audio',
                        'file_name': audio_path.name,
                        'file_path': str(audio_path),
                        'file_size': file_size
                    })
                
            except Exception as e:
                logger.error(f"YouTube 下載失敗: {e}")
                await db.update_task_status(task_id, 'failed', error_message=str(e))
                raise HTTPException(status_code=500, detail=f"YouTube 下載失敗: {str(e)}")
        
        # 執行語音轉錄
        try:
            # 載入模型
            if MODEL is None:
                init_models()

            # 轉錄音訊 - 使用異步執行以支援 WebSocket 即時更新
            transcript_segments = []
            full_text = ""

            # 在執行緒池中執行轉錄
            loop = asyncio.get_event_loop()

            def transcribe_sync():
                return MODEL.transcribe(
                    str(audio_path),
                    language=language,
                    vad_filter=vad_filter,
                    vad_parameters={
                        "min_silence_duration_ms": min_silence_duration_ms,
                        "speech_pad_ms": speech_pad_ms
                    } if vad_filter else None
                )

            segments_generator, info = await loop.run_in_executor(None, transcribe_sync)

            # 處理轉錄結果並即時發送 WebSocket 更新
            for segment in segments_generator:
                segment_data = {
                    "id": len(transcript_segments),
                    "seek": segment.seek,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "tokens": segment.tokens,
                    "temperature": segment.temperature,
                    "avg_logprob": segment.avg_logprob,
                    "compression_ratio": segment.compression_ratio,
                    "no_speech_prob": segment.no_speech_prob
                }
                transcript_segments.append(segment_data)
                full_text += segment.text + " "

                # 發送即時進度和段落更新到 WebSocket
                if client_id and client_id in manager.active_connections:
                    # 計算進度百分比
                    if hasattr(info, 'duration') and info.duration:
                        progress = min(100, int((segment.end / info.duration) * 100))

                        # 發送進度更新
                        await manager.send_json(client_id, {
                            "type": "progress",
                            "progress": progress
                        })

                    # 發送段落更新
                    await manager.send_json(client_id, {
                        "type": "segment",
                        "text": segment.text,
                        "start": segment.start,
                        "end": segment.end,
                        "id": segment_data["id"]
                    })

            # 說話者分離（如果啟用）
            if with_diarization:
                try:
                    logger.info("開始執行說話者分離...")

                    # 發送 WebSocket 通知
                    if client_id and client_id in manager.active_connections:
                        await manager.send_json(client_id, {
                            "type": "status",
                            "message": "正在執行說話者識別..."
                        })

                    # 將轉錄結果轉換為 WhisperX 格式
                    whisperx_format = convert_to_whisperx_format(transcript_segments)

                    if whisperx_format["segments"]:
                        # 在執行緒池中執行說話者分離
                        diarized_result = await loop.run_in_executor(
                            None,
                            lambda: perform_diarization_with_whisperx(audio_path, whisperx_format)
                        )

                        # 將結果轉換回標準格式
                        diarized_segments = convert_from_whisperx_format(diarized_result)

                        if diarized_segments:
                            transcript_segments = diarized_segments
                            logger.info(f"說話者分離完成，共 {len(diarized_segments)} 個段落")

                            # 發送說話者分離完成通知
                            if client_id and client_id in manager.active_connections:
                                await manager.send_json(client_id, {
                                    "type": "diarization_complete",
                                    "segments": transcript_segments
                                })
                    else:
                        logger.warning("沒有有效的段落可供說話者分離")

                except Exception as e:
                    logger.error(f"說話者分離失敗: {e}")
                    import traceback
                    traceback.print_exc()
            
            # 保存轉錄結果
            # 保存文字檔案
            txt_path = task_folder / f"{task_data['name']}.txt"
            async with aiofiles.open(txt_path, 'w', encoding='utf-8') as f:
                await f.write(full_text.strip())
            
            await db.add_task_file(task_id, {
                'file_type': 'txt',
                'file_name': txt_path.name,
                'file_path': str(txt_path),
                'file_size': len(full_text.encode('utf-8'))
            })
            
            # 生成 SRT 字幕（包含說話者資訊）
            srt_content = ""
            for i, segment in enumerate(transcript_segments, 1):
                start_time = format_timestamp(segment['start'])
                end_time = format_timestamp(segment['end'])
                text = segment['text'].strip()

                # 如果有說話者資訊，添加到文字前
                if 'speaker' in segment and segment['speaker']:
                    text = f"[{segment['speaker']}] {text}"

                srt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
            
            srt_path = task_folder / f"{task_data['name']}.srt"
            async with aiofiles.open(srt_path, 'w', encoding='utf-8') as f:
                await f.write(srt_content)
            
            await db.add_task_file(task_id, {
                'file_type': 'srt',
                'file_name': srt_path.name,
                'file_path': str(srt_path),
                'file_size': len(srt_content.encode('utf-8'))
            })
            
            # 更新任務狀態
            await db.update_task_status(task_id, 'completed')
            
            # 準備回應
            if response_format == "verbose_json":
                response_data = {
                    "task": info.language,
                    "language": info.language,
                    "duration": info.duration,
                    "text": full_text.strip(),
                    "segments": transcript_segments
                }
            else:
                response_data = {
                    "text": full_text.strip()
                }
            
            return response_data
            
        except Exception as e:
            logger.error(f"轉錄失敗: {e}")
            await db.update_task_status(task_id, 'failed', error_message=str(e))
            raise HTTPException(status_code=500, detail=f"轉錄失敗: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"轉錄 API 錯誤: {e}")
        raise HTTPException(status_code=500, detail="內部伺服器錯誤")

def format_timestamp(seconds):
    """將秒數轉換為 SRT 時間格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

# ==================== 檔案下載和生成 ====================

@app.get("/download/{filename}")
async def download_file(filename: str):
    """下載臨時檔案"""
    try:
        # 基本安全檢查
        if not filename or '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="無效的檔案名稱")
        
        # 檔案存在性檢查
        file_path = TEMP_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="檔案不存在")
        
        # 路徑安全檢查
        try:
            file_path.resolve().relative_to(TEMP_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="檔案存取被拒絕")
        
        return FileResponse(path=file_path, filename=filename)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下載檔案失敗: {e}")
        raise HTTPException(status_code=500, detail="下載檔案失敗")

@app.post("/generate-srt")
async def generate_srt(request: dict):
    """生成 SRT 字幕檔案"""
    try:
        segments = request.get('segments', [])
        if not segments:
            raise HTTPException(status_code=400, detail="沒有提供轉錄段落")
        
        # 生成 SRT 內容
        srt_content = ""
        for i, segment in enumerate(segments, 1):
            start_time = format_timestamp(segment['start'])
            end_time = format_timestamp(segment['end'])
            text = segment['text'].strip()
            
            # 如果有說話者資訊，添加到文字前
            if 'speaker' in segment and segment['speaker']:
                text = f"[{segment['speaker']}] {text}"
            
            srt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
        
        # 生成檔案名稱
        filename = f"transcript_{int(time.time())}.srt"
        file_path = TEMP_DIR / filename
        
        # 保存檔案
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(srt_content)
        
        return {"filename": filename, "message": "SRT 檔案生成成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成 SRT 檔案失敗: {e}")
        raise HTTPException(status_code=500, detail="生成 SRT 檔案失敗")

# ==================== WebSocket 連接管理 ====================
# WebSocket 端點定義在下方，使用上面已定義的 ConnectionManager 和 manager

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            # 保持連接活躍
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket 錯誤: {e}")
        manager.disconnect(client_id)

# 效能監控和 UX 端點
@app.get("/api/performance/stats")
async def get_performance_stats():
    """取得效能統計"""
    try:
        report = generate_performance_report()
        return JSONResponse(content=report)
    except Exception as e:
        logger.error(f"取得效能統計失敗: {e}")
        raise HistoryAPIException(500, "無法取得效能統計", ErrorCodes.DATABASE_ERROR)

@app.get("/api/ux/analytics")
async def get_ux_analytics():
    """取得 UX 分析"""
    try:
        ux_manager = get_ux_manager()
        analytics = ux_manager.get_ux_analytics()
        return JSONResponse(content=analytics)
    except Exception as e:
        logger.error(f"取得 UX 分析失敗: {e}")
        raise HistoryAPIException(500, "無法取得 UX 分析", ErrorCodes.DATABASE_ERROR)

@app.post("/api/feedback")
async def submit_feedback(
    task_id: str = Form(...),
    rating: int = Form(...),
    comment: str = Form(""),
    category: str = Form("general")
):
    """提交使用者回饋"""
    try:
        # 驗證評分範圍
        if not 1 <= rating <= 5:
            raise ValidationException("評分必須在 1-5 之間", field="rating", value=rating)
        
        ux_manager = get_ux_manager()
        feedback_id = await ux_manager.collect_feedback(task_id, rating, comment, category)
        
        return JSONResponse(content={
            "success": True,
            "feedback_id": feedback_id,
            "message": "感謝您的回饋"
        })
    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"提交回饋失敗: {e}")
        raise HistoryAPIException(500, "提交回饋失敗", ErrorCodes.DATABASE_ERROR)

# ==================== 歷史紀錄 API 端點 ====================

@app.get("/api/history", response_model=TaskHistoryResponse)
async def get_conversion_history(
    limit: int = 50,
    offset: int = 0,
    page: int = 1
):
    """
    取得轉換歷史紀錄列表，支援分頁和排序功能
    
    Args:
        limit: 每頁顯示的任務數量 (預設 50)
        offset: 偏移量，用於分頁 (預設 0)
        page: 頁碼，從 1 開始 (預設 1)
    
    Returns:
        TaskHistoryResponse: 包含任務列表和分頁資訊的回應
    """
    try:
        # 輸入驗證
        if limit < 1 or limit > 100:
            raise ValidationException("限制數量必須在 1-100 之間", field="limit", value=limit)
        
        if offset < 0:
            raise ValidationException("偏移量不能為負數", field="offset", value=offset)
        
        if page < 1:
            raise ValidationException("頁碼必須大於 0", field="page", value=page)
        
        db = await get_db()
        
        # 如果提供了 page 參數，計算對應的 offset
        if page > 1:
            offset = (page - 1) * limit
        
        # 取得任務列表
        tasks = await db.get_task_history(limit=limit, offset=offset)
        
        # 取得總任務數量
        total = await db.get_task_count()
        
        # 計算是否有下一頁
        has_next = (offset + limit) < total
        
        return TaskHistoryResponse(
            tasks=tasks,
            total=total,
            page=page,
            limit=limit,
            has_next=has_next
        )
        
    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"取得歷史紀錄失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="取得歷史紀錄失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"original_error": str(e)}
        )



@app.get("/api/history/search")
async def search_conversion_history(
    q: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """
    搜尋和篩選轉換歷史紀錄
    
    Args:
        q: 搜尋關鍵字，會搜尋任務名稱和來源資訊
        page: 頁碼 (預設 1)
        limit: 每頁數量 (預設 20)
        status: 任務狀態篩選 ('processing', 'completed', 'failed')
        source_type: 來源類型篩選 ('file', 'youtube')
        date_from: 開始日期，ISO 格式 (例: 2024-01-01)
        date_to: 結束日期，ISO 格式 (例: 2024-12-31)
    
    Returns:
        Dict: 搜尋結果和分頁資訊
    """
    try:
        # 輸入驗證和清理
        if q:
            q = q.strip()
            if len(q) < 1:
                q = None
        
        page = max(1, page)
        limit = max(1, min(50, limit))
        
        db = await get_db()
        
        # 建立篩選條件
        filters = {}
        if status:
            filters['status'] = status
        if source_type:
            filters['source_type'] = source_type
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        
        # 執行搜尋
        if q:
            # 有搜尋關鍵字
            try:
                tasks = await db.search_tasks(q, **filters)
            except AttributeError:
                # 如果 search_tasks 方法不存在，使用基本查詢
                all_tasks = await db.get_task_history()
                tasks = []
                for task in all_tasks:
                    # 簡單的文字搜尋
                    searchable_text = f"{task.get('name', '')} {task.get('video_title', '')} {task.get('video_uploader', '')}".lower()
                    if q.lower() in searchable_text:
                        # 應用其他篩選條件
                        if status and task.get('status') != status:
                            continue
                        if source_type and task.get('source_type') != source_type:
                            continue
                        tasks.append(task)
        else:
            # 沒有搜尋關鍵字，只使用篩選條件
            if any(filters.values()):
                # 有篩選條件，使用基本查詢然後篩選
                all_tasks = await db.get_task_history()
                tasks = []
                for task in all_tasks:
                    if status and task.get('status') != status:
                        continue
                    if source_type and task.get('source_type') != source_type:
                        continue
                    # 日期篩選可以在這裡添加
                    tasks.append(task)
            else:
                # 沒有任何條件，返回所有任務
                tasks = await db.get_task_history()
        
        # 分頁處理
        total = len(tasks)
        offset = (page - 1) * limit
        paginated_tasks = tasks[offset:offset + limit]
        
        return {
            "tasks": paginated_tasks,
            "total": total,
            "page": page,
            "limit": limit,
            "has_next": offset + limit < total,
            "query": {
                "keyword": q,
                "status": status,
                "source_type": source_type,
                "date_from": date_from,
                "date_to": date_to
            }
        }
        
    except Exception as e:
        logger.error(f"搜尋歷史紀錄失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="搜尋歷史紀錄失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"original_error": str(e)}
        )



@app.get("/api/history/{task_id}", response_model=TaskDetailResponse)
async def get_task_details(task_id: str):
    """
    根據任務 ID 取得特定任務的詳細資訊
    
    Args:
        task_id: 任務唯一識別碼
    
    Returns:
        TaskDetailResponse: 任務詳細資訊和檔案列表
    """
    try:
        # 驗證任務 ID 格式
        validated_task_id = InputSanitizer.validate_task_id(task_id)
        
        db = await get_db()
        
        # 取得任務詳情
        task = await db.get_task_by_id(validated_task_id)
        
        if not task:
            raise TaskNotFoundException(validated_task_id)
        
        # 任務詳情已包含檔案列表，直接回傳
        return TaskDetailResponse(
            task=task,
            files=task.get('files', [])
        )
        
    except (ValidationException, TaskNotFoundException):
        raise
    except Exception as e:
        logger.error(f"取得任務詳情失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="取得任務詳情失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"task_id": task_id, "original_error": str(e)}
        )



# ==================== 歷史紀錄 API 端點 ====================

@app.delete("/api/history/{task_id}")
async def delete_conversion_task(task_id: str):
    """
    刪除指定的轉換任務及其相關檔案
    
    Args:
        task_id: 要刪除的任務 ID
    
    Returns:
        Dict: 刪除結果
    """
    try:
        # 驗證任務 ID 格式
        validated_task_id = InputSanitizer.validate_task_id(task_id)
        
        db = await get_db()
        file_manager = get_file_manager()
        file_validator = get_file_access_validator()
        
        # 先取得任務資訊
        task = await db.get_task_by_id(validated_task_id)
        if not task:
            raise TaskNotFoundException(validated_task_id)
        
        # 刪除任務資料夾和檔案
        task_folder_path = task.get('task_folder')
        if task_folder_path:
            task_folder = Path(task_folder_path)

            # 只驗證資料夾路徑安全性,不檢查副檔名(因為是資料夾)
            if task_folder.exists():
                try:
                    # 只驗證路徑是否在允許的範圍內,不驗證檔案存取(因為是資料夾)
                    file_validator.validate_file_path(task_folder)
                except FileAccessException as e:
                    logger.warning(f"資料夾路徑驗證失敗: {e.detail}")
                    raise e

                success = file_manager.delete_task_folder(task_folder)
                if not success:
                    raise HistoryAPIException(
                        status_code=500,
                        detail="刪除任務檔案失敗",
                        error_code=ErrorCodes.TASK_DELETE_FAILED,
                        context={"task_id": validated_task_id, "task_folder": str(task_folder)}
                    )
        
        # 從資料庫中刪除任務記錄
        db_success = await db.delete_task(validated_task_id)
        if not db_success:
            raise HistoryAPIException(
                status_code=500,
                detail="刪除任務記錄失敗",
                error_code=ErrorCodes.TASK_DELETE_FAILED,
                context={"task_id": validated_task_id}
            )
        
        logger.info(f"成功刪除任務: {validated_task_id}")
        
        return {
            "status": "success",
            "message": "任務已成功刪除",
            "task_id": validated_task_id
        }
        
    except (ValidationException, TaskNotFoundException, FileAccessException):
        raise
    except Exception as e:
        logger.error(f"刪除任務失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="刪除任務失敗",
            error_code=ErrorCodes.TASK_DELETE_FAILED,
            context={"task_id": task_id, "original_error": str(e)}
        )

@app.get("/api/history/{task_id}/files")
async def list_task_files(task_id: str):
    """
    取得指定任務的所有檔案列表
    
    Args:
        task_id: 任務 ID
    
    Returns:
        Dict: 包含檔案列表的回應
    """
    try:
        # 驗證任務 ID 格式
        validated_task_id = InputSanitizer.validate_task_id(task_id)
        
        db = await get_db()
        
        # 取得任務資訊
        task = await db.get_task_by_id(validated_task_id)
        if not task:
            raise TaskNotFoundException(validated_task_id)
        
        # 驗證任務資料夾存取權限
        task_folder_path = task.get('task_folder')
        if task_folder_path:
            file_validator = get_file_access_validator()
            try:
                file_validator.validate_file_path(task_folder_path)
            except FileAccessException as e:
                logger.warning(f"任務資料夾存取權限驗證失敗: {e.detail}")
                # 對於列表操作，如果資料夾不存在或無權限，回傳空列表而不是錯誤
                return {
                    "task_id": validated_task_id,
                    "files": [],
                    "task_folder": task_folder_path,
                    "warning": "任務資料夾不存在或無法存取"
                }
        
        # 回傳檔案列表
        return {
            "task_id": validated_task_id,
            "files": task.get('files', []),
            "task_folder": task.get('task_folder', '')
        }
        
    except (ValidationException, TaskNotFoundException):
        raise
    except Exception as e:
        logger.error(f"取得檔案列表失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="取得檔案列表失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"task_id": task_id, "original_error": str(e)}
        )

@app.get("/api/history/{task_id}/files/{file_type}")
async def download_task_file(task_id: str, file_type: str):
    """
    下載指定任務的特定類型檔案
    
    Args:
        task_id: 任務 ID
        file_type: 檔案類型 ('audio', 'srt', 'txt')
    
    Returns:
        FileResponse: 檔案下載回應
    """
    try:
        # 驗證任務 ID 格式
        validated_task_id = InputSanitizer.validate_task_id(task_id)
        
        # 驗證檔案類型
        allowed_file_types = ['audio', 'srt', 'txt', 'video', 'thumbnail']
        if file_type not in allowed_file_types:
            raise ValidationException(
                f"無效的檔案類型，允許的類型: {', '.join(allowed_file_types)}",
                field="file_type",
                value=file_type
            )
        
        db = await get_db()
        file_validator = get_file_access_validator()
        
        # 取得任務資訊
        task = await db.get_task_by_id(validated_task_id)
        if not task:
            raise TaskNotFoundException(validated_task_id)
        
        # 尋找指定類型的檔案
        target_file = None
        for file_info in task.get('files', []):
            if file_info.get('file_type') == file_type:
                target_file = file_info
                break
        
        if not target_file:
            raise HistoryAPIException(
                status_code=404,
                detail=f"找不到類型為 {file_type} 的檔案",
                error_code=ErrorCodes.FILE_NOT_FOUND,
                context={"task_id": validated_task_id, "file_type": file_type}
            )
        
        # 驗證檔案存取權限
        file_path = Path(target_file['file_path'])
        try:
            file_validator.validate_file_access(file_path, operation="read")
        except FileAccessException as e:
            logger.warning(f"檔案存取權限驗證失敗: {e.detail}")
            raise e
        
        # 檢查檔案是否存在
        if not file_path.exists():
            raise HistoryAPIException(
                status_code=404,
                detail="檔案不存在於檔案系統中",
                error_code=ErrorCodes.FILE_NOT_FOUND,
                context={"file_path": str(file_path)}
            )
        
        # 設定下載檔名（清理檔案名稱）
        download_filename = InputSanitizer.sanitize_filename(target_file['file_name'])
        
        logger.info(f"下載檔案: {validated_task_id}/{file_type} - {download_filename}")
        
        # 對檔案名稱進行 URL 編碼以支援中文字符
        from urllib.parse import quote
        encoded_filename = quote(download_filename.encode('utf-8'))
        
        # 回傳檔案
        return FileResponse(
            path=str(file_path),
            filename=download_filename,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "X-File-Type": file_type,
                "X-Task-ID": validated_task_id
            }
        )
        
    except (ValidationException, TaskNotFoundException, FileAccessException):
        raise
    except Exception as e:
        logger.error(f"下載檔案失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="下載檔案失敗",
            error_code=ErrorCodes.FILE_ACCESS_DENIED,
            context={"task_id": task_id, "file_type": file_type, "original_error": str(e)}
        )


# ==================== 維護管理 API 端點 ====================

@app.get("/api/maintenance/status")
async def get_maintenance_status():
    """
    取得系統維護狀態
    
    Returns:
        維護狀態資訊，包括磁碟使用量、清理狀態、任務統計等
    """
    try:
        scheduler = get_maintenance_scheduler()
        status = await scheduler.get_maintenance_status()
        
        logger.info("取得維護狀態")
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": status,
                "timestamp": time.time()
            }
        )
        
    except Exception as e:
        logger.error(f"取得維護狀態失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="取得維護狀態失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"original_error": str(e)}
        )

@app.post("/api/maintenance/cleanup")
async def force_cleanup(retention_days: Optional[int] = None):
    """
    強制執行清理操作
    
    Args:
        retention_days: 自訂保留天數，如果未提供則使用預設值
        
    Returns:
        清理操作報告
    """
    try:
        scheduler = get_maintenance_scheduler()
        
        # 驗證保留天數參數
        if retention_days is not None:
            if retention_days < 1 or retention_days > 365:
                raise ValidationException(
                    detail="保留天數必須在 1-365 天之間",
                    field="retention_days",
                    value=retention_days
                )
        
        report = await scheduler.force_cleanup(retention_days)
        
        logger.info(f"強制清理完成: 清理 {report.files_cleaned} 個檔案，釋放 {report.space_freed_mb:.2f} MB")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "timestamp": report.timestamp,
                    "maintenance_type": report.maintenance_type,
                    "level": report.level.value,
                    "actions_taken": report.actions_taken,
                    "files_cleaned": report.files_cleaned,
                    "space_freed_mb": report.space_freed_mb,
                    "errors": report.errors,
                    "duration_seconds": report.duration_seconds
                },
                "message": f"清理完成，清理了 {report.files_cleaned} 個檔案，釋放 {report.space_freed_mb:.2f} MB 空間"
            }
        )
        
    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"強制清理失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="執行清理操作失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"retention_days": retention_days, "original_error": str(e)}
        )

@app.get("/api/maintenance/disk-space")
async def check_disk_space():
    """
    檢查磁碟空間使用情況
    
    Returns:
        磁碟空間資訊和警告等級
    """
    try:
        scheduler = get_maintenance_scheduler()
        disk_info = await scheduler.check_disk_space()
        
        # 根據使用率設定回應狀態碼
        status_code = 200
        if disk_info.get('level') == 'critical':
            status_code = 503  # Service Unavailable
        elif disk_info.get('level') == 'high':
            status_code = 207  # Multi-Status (警告)
        
        return JSONResponse(
            status_code=status_code,
            content={
                "success": True,
                "data": disk_info,
                "warning": disk_info.get('level') in ['high', 'critical']
            }
        )
        
    except Exception as e:
        logger.error(f"檢查磁碟空間失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="檢查磁碟空間失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"original_error": str(e)}
        )

@app.post("/api/maintenance/optimize-database")
async def optimize_database():
    """
    執行資料庫最佳化操作
    
    Returns:
        資料庫最佳化報告
    """
    try:
        scheduler = get_maintenance_scheduler()
        report = await scheduler.optimize_database()
        
        logger.info(f"資料庫最佳化完成，耗時 {report.duration_seconds:.2f} 秒")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "timestamp": report.timestamp,
                    "maintenance_type": report.maintenance_type,
                    "level": report.level.value,
                    "actions_taken": report.actions_taken,
                    "errors": report.errors,
                    "duration_seconds": report.duration_seconds
                },
                "message": f"資料庫最佳化完成，執行了 {len(report.actions_taken)} 個操作"
            }
        )
        
    except Exception as e:
        logger.error(f"資料庫最佳化失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="資料庫最佳化失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"original_error": str(e)}
        )

@app.post("/api/maintenance/start-scheduler")
async def start_maintenance_scheduler():
    """
    啟動維護排程器
    
    Returns:
        啟動狀態
    """
    try:
        scheduler = get_maintenance_scheduler()
        
        if scheduler.is_running:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "維護排程器已在運行中",
                    "running": True
                }
            )
        
        await scheduler.start()
        
        logger.info("維護排程器已啟動")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "維護排程器已啟動",
                "running": True
            }
        )
        
    except Exception as e:
        logger.error(f"啟動維護排程器失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="啟動維護排程器失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"original_error": str(e)}
        )

@app.post("/api/maintenance/stop-scheduler")
async def stop_maintenance_scheduler():
    """
    停止維護排程器
    
    Returns:
        停止狀態
    """
    try:
        scheduler = get_maintenance_scheduler()
        
        if not scheduler.is_running:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "維護排程器未在運行",
                    "running": False
                }
            )
        
        await scheduler.stop()
        
        logger.info("維護排程器已停止")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "維護排程器已停止",
                "running": False
            }
        )
        
    except Exception as e:
        logger.error(f"停止維護排程器失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="停止維護排程器失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"original_error": str(e)}
        )

@app.get("/api/maintenance/reports")
async def get_maintenance_reports(limit: int = 10):
    """
    取得維護報告歷史
    
    Args:
        limit: 限制回傳的報告數量
        
    Returns:
        維護報告列表
    """
    try:
        # 驗證 limit 參數
        if limit < 1 or limit > 100:
            raise ValidationException(
                detail="limit 參數必須在 1-100 之間",
                field="limit",
                value=limit
            )
        
        scheduler = get_maintenance_scheduler()
        
        # 取得最近的報告
        recent_reports = scheduler.reports[-limit:] if scheduler.reports else []
        
        # 轉換報告格式
        reports_data = []
        for report in reversed(recent_reports):  # 最新的在前面
            reports_data.append({
                "timestamp": report.timestamp,
                "maintenance_type": report.maintenance_type,
                "level": report.level.value,
                "actions_taken": report.actions_taken,
                "files_cleaned": report.files_cleaned,
                "space_freed_mb": report.space_freed_mb,
                "errors": report.errors,
                "duration_seconds": report.duration_seconds
            })
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "reports": reports_data,
                    "total_reports": len(scheduler.reports),
                    "returned_count": len(reports_data)
                }
            }
        )
        
    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"取得維護報告失敗: {str(e)}")
        raise HistoryAPIException(
            status_code=500,
            detail="取得維護報告失敗",
            error_code=ErrorCodes.DATABASE_ERROR,
            context={"limit": limit, "original_error": str(e)}
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
