"""
資料模型定義
包含 YouTube 元資料模型和擴展的轉換任務模型
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

# ==================== YouTube 相關資料模型 ====================

@dataclass
class YouTubeMetadata:
    """YouTube 影片元資料模型"""
    
    title: str
    description: Optional[str] = None
    uploader: Optional[str] = None
    upload_date: Optional[str] = None
    duration: Optional[int] = None
    thumbnail_url: Optional[str] = None
    view_count: Optional[int] = None
    webpage_url: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return asdict(self)
    
    def to_json(self) -> str:
        """轉換為 JSON 字串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'YouTubeMetadata':
        """從字典建立 YouTubeMetadata 實例"""
        return cls(
            title=data.get('title', ''),
            description=data.get('description'),
            uploader=data.get('uploader'),
            upload_date=data.get('upload_date'),
            duration=data.get('duration'),
            thumbnail_url=data.get('thumbnail_url'),
            view_count=data.get('view_count'),
            webpage_url=data.get('webpage_url', '')
        )
    
    @classmethod
    def from_ydl_info(cls, info: Dict[str, Any]) -> 'YouTubeMetadata':
        """從 yt-dlp 資訊字典建立 YouTubeMetadata 實例"""
        return cls(
            title=info.get('title', ''),
            description=info.get('description'),
            uploader=info.get('uploader'),
            upload_date=info.get('upload_date'),
            duration=info.get('duration'),
            thumbnail_url=info.get('thumbnail'),
            view_count=info.get('view_count'),
            webpage_url=info.get('webpage_url', '')
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'YouTubeMetadata':
        """從 JSON 字串建立 YouTubeMetadata 實例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_display_title(self) -> str:
        """取得顯示用標題（清理後的標題）"""
        if not self.title:
            return "未知標題"
        
        # 移除不適合顯示的字元
        import re
        cleaned_title = re.sub(r'[<>:"/\\|?*]', '', self.title)
        
        # 限制長度
        if len(cleaned_title) > 100:
            cleaned_title = cleaned_title[:97] + "..."
        
        return cleaned_title.strip() or "未知標題"
    
    def get_safe_filename(self) -> str:
        """取得安全的檔案名稱"""
        if not self.title:
            return "unknown_video"
        
        # 移除檔案名稱中的危險字元
        import re
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', self.title)
        safe_name = re.sub(r'[^\w\s\u4e00-\u9fff\-_.]', '', safe_name)
        
        # 限制長度
        if len(safe_name) > 50:
            safe_name = safe_name[:47] + "..."
        
        return safe_name.strip() or "unknown_video"
    
    def get_duration_formatted(self) -> str:
        """取得格式化的時長字串"""
        if not self.duration:
            return "未知時長"
        
        hours = self.duration // 3600
        minutes = (self.duration % 3600) // 60
        seconds = self.duration % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def get_upload_date_formatted(self) -> str:
        """取得格式化的上傳日期"""
        if not self.upload_date:
            return "未知日期"
        
        try:
            # yt-dlp 的日期格式通常是 YYYYMMDD
            if len(self.upload_date) == 8:
                year = self.upload_date[:4]
                month = self.upload_date[4:6]
                day = self.upload_date[6:8]
                return f"{year}-{month}-{day}"
            else:
                return self.upload_date
        except:
            return self.upload_date or "未知日期"

@dataclass
class EnhancedConversionTask:
    """擴展的轉換任務模型"""
    
    # 現有欄位
    id: str
    name: str
    source_type: str
    source_info: str
    status: str = "processing"
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    model_used: str = "whisper-1"
    language: Optional[str] = None
    has_diarization: bool = False
    file_size: Optional[int] = None
    duration: Optional[float] = None
    
    # 新增的 YouTube 相關欄位
    video_title: Optional[str] = None
    video_description: Optional[str] = None
    video_uploader: Optional[str] = None
    video_upload_date: Optional[str] = None
    video_duration: Optional[int] = None
    video_thumbnail_url: Optional[str] = None
    video_view_count: Optional[int] = None
    
    # 檔案路徑資訊
    audio_file_path: Optional[str] = None
    video_file_path: Optional[str] = None
    thumbnail_file_path: Optional[str] = None
    srt_file_path: Optional[str] = None
    txt_file_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return asdict(self)
    
    def to_json(self) -> str:
        """轉換為 JSON 字串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedConversionTask':
        """從字典建立 EnhancedConversionTask 實例"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'EnhancedConversionTask':
        """從 JSON 字串建立 EnhancedConversionTask 實例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_display_title(self) -> str:
        """取得顯示標題（優先使用影片標題）"""
        if self.video_title:
            return self.video_title
        return self.name or self.source_info or "未知任務"
    
    def get_display_source(self) -> str:
        """取得顯示來源資訊"""
        if self.source_type == "youtube" and self.video_uploader:
            return f"YouTube - {self.video_uploader}"
        elif self.source_type == "file":
            return "檔案上傳"
        else:
            return self.source_type or "未知來源"
    
    def is_youtube_task(self) -> bool:
        """判斷是否為 YouTube 任務"""
        return self.source_type == "youtube"
    
    def has_video_file(self) -> bool:
        """判斷是否有影片檔案"""
        return bool(self.video_file_path and Path(self.video_file_path).exists())
    
    def has_thumbnail_file(self) -> bool:
        """判斷是否有縮圖檔案"""
        return bool(self.thumbnail_file_path and Path(self.thumbnail_file_path).exists())
    
    def get_youtube_metadata(self) -> Optional[YouTubeMetadata]:
        """取得 YouTube 元資料物件"""
        if not self.is_youtube_task():
            return None
        
        return YouTubeMetadata(
            title=self.video_title or "",
            description=self.video_description,
            uploader=self.video_uploader,
            upload_date=self.video_upload_date,
            duration=self.video_duration,
            thumbnail_url=self.video_thumbnail_url,
            view_count=self.video_view_count,
            webpage_url=self.source_info or ""
        )
    
    def update_from_youtube_metadata(self, metadata: YouTubeMetadata):
        """從 YouTube 元資料更新任務資訊"""
        self.video_title = metadata.title
        self.video_description = metadata.description
        self.video_uploader = metadata.uploader
        self.video_upload_date = metadata.upload_date
        self.video_duration = metadata.duration
        self.video_thumbnail_url = metadata.thumbnail_url
        self.video_view_count = metadata.view_count
        
        # 如果任務名稱為空或是 URL，使用影片標題
        if not self.name or self.name.startswith('http'):
            self.name = metadata.get_safe_filename()
    
    def get_file_info(self) -> Dict[str, Any]:
        """取得檔案資訊摘要"""
        files = {}
        
        if self.audio_file_path and Path(self.audio_file_path).exists():
            files['audio'] = {
                'path': self.audio_file_path,
                'size': Path(self.audio_file_path).stat().st_size,
                'exists': True
            }
        
        if self.video_file_path and Path(self.video_file_path).exists():
            files['video'] = {
                'path': self.video_file_path,
                'size': Path(self.video_file_path).stat().st_size,
                'exists': True
            }
        
        if self.thumbnail_file_path and Path(self.thumbnail_file_path).exists():
            files['thumbnail'] = {
                'path': self.thumbnail_file_path,
                'size': Path(self.thumbnail_file_path).stat().st_size,
                'exists': True
            }
        
        if self.srt_file_path and Path(self.srt_file_path).exists():
            files['srt'] = {
                'path': self.srt_file_path,
                'size': Path(self.srt_file_path).stat().st_size,
                'exists': True
            }
        
        if self.txt_file_path and Path(self.txt_file_path).exists():
            files['txt'] = {
                'path': self.txt_file_path,
                'size': Path(self.txt_file_path).stat().st_size,
                'exists': True
            }
        
        return files
    
    def get_task_summary(self) -> Dict[str, Any]:
        """取得任務摘要資訊"""
        return {
            'id': self.id,
            'title': self.get_display_title(),
            'source': self.get_display_source(),
            'status': self.status,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'duration': self.get_duration_formatted() if self.duration else None,
            'has_video': self.has_video_file(),
            'has_thumbnail': self.has_thumbnail_file(),
            'file_count': len(self.get_file_info())
        }
    
    def get_duration_formatted(self) -> str:
        """取得格式化的時長字串"""
        duration = self.video_duration or self.duration
        if not duration:
            return "未知時長"
        
        # 如果是整數秒數
        if isinstance(duration, int):
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
        else:
            # 如果是浮點數秒數
            total_seconds = int(duration)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

# ==================== 資料轉換工具 ====================

class DataConverter:
    """資料轉換工具類別"""
    
    @staticmethod
    def task_to_db_dict(task: EnhancedConversionTask) -> Dict[str, Any]:
        """將任務物件轉換為資料庫儲存格式"""
        return {
            'id': task.id,
            'name': task.name,
            'source_type': task.source_type,
            'source_info': task.source_info,
            'status': task.status,
            'created_at': task.created_at,
            'completed_at': task.completed_at,
            'model_used': task.model_used,
            'language': task.language,
            'has_diarization': task.has_diarization,
            'file_size': task.file_size,
            'duration': task.duration,
            'video_title': task.video_title,
            'video_description': task.video_description,
            'video_uploader': task.video_uploader,
            'video_upload_date': task.video_upload_date,
            'video_duration': task.video_duration,
            'video_thumbnail_url': task.video_thumbnail_url,
            'video_view_count': task.video_view_count
        }
    
    @staticmethod
    def db_dict_to_task(data: Dict[str, Any]) -> EnhancedConversionTask:
        """將資料庫資料轉換為任務物件"""
        return EnhancedConversionTask(
            id=data.get('id', ''),
            name=data.get('name', ''),
            source_type=data.get('source_type', ''),
            source_info=data.get('source_info', ''),
            status=data.get('status', 'processing'),
            created_at=data.get('created_at'),
            completed_at=data.get('completed_at'),
            model_used=data.get('model_used', 'whisper-1'),
            language=data.get('language'),
            has_diarization=bool(data.get('has_diarization', False)),
            file_size=data.get('file_size'),
            duration=data.get('duration'),
            video_title=data.get('video_title'),
            video_description=data.get('video_description'),
            video_uploader=data.get('video_uploader'),
            video_upload_date=data.get('video_upload_date'),
            video_duration=data.get('video_duration'),
            video_thumbnail_url=data.get('video_thumbnail_url'),
            video_view_count=data.get('video_view_count')
        )
    
    @staticmethod
    def youtube_metadata_to_db_dict(metadata: YouTubeMetadata) -> Dict[str, Any]:
        """將 YouTube 元資料轉換為資料庫儲存格式"""
        return {
            'video_title': metadata.title,
            'video_description': metadata.description,
            'video_uploader': metadata.uploader,
            'video_upload_date': metadata.upload_date,
            'video_duration': metadata.duration,
            'video_thumbnail_url': metadata.thumbnail_url,
            'video_view_count': metadata.view_count
        }
    
    @staticmethod
    def merge_task_with_metadata(task: EnhancedConversionTask, metadata: YouTubeMetadata) -> EnhancedConversionTask:
        """將 YouTube 元資料合併到任務中"""
        task.update_from_youtube_metadata(metadata)
        return task

# ==================== 檔案路徑管理 ====================

class TaskFilePaths:
    """任務檔案路徑管理"""
    
    def __init__(self, task_id: str, base_path: str = "history/tasks"):
        self.task_id = task_id
        self.base_path = Path(base_path)
        self.task_folder = self.base_path / task_id
    
    def get_audio_path(self, extension: str = "mp3") -> Path:
        """取得音訊檔案路徑"""
        return self.task_folder / f"audio.{extension}"
    
    def get_video_path(self, extension: str = "mp4") -> Path:
        """取得影片檔案路徑"""
        return self.task_folder / f"video.{extension}"
    
    def get_thumbnail_path(self, extension: str = "jpg") -> Path:
        """取得縮圖檔案路徑"""
        return self.task_folder / f"thumbnail.{extension}"
    
    def get_srt_path(self) -> Path:
        """取得字幕檔案路徑"""
        return self.task_folder / "subtitles.srt"
    
    def get_txt_path(self) -> Path:
        """取得文字檔案路徑"""
        return self.task_folder / "transcript.txt"
    
    def get_metadata_path(self) -> Path:
        """取得元資料檔案路徑"""
        return self.task_folder / "metadata.json"
    
    def ensure_task_folder(self):
        """確保任務資料夾存在"""
        self.task_folder.mkdir(parents=True, exist_ok=True)
    
    def get_all_paths(self) -> Dict[str, Path]:
        """取得所有檔案路徑"""
        return {
            'audio': self.get_audio_path(),
            'video': self.get_video_path(),
            'thumbnail': self.get_thumbnail_path(),
            'srt': self.get_srt_path(),
            'txt': self.get_txt_path(),
            'metadata': self.get_metadata_path()
        }
    
    def update_task_file_paths(self, task: EnhancedConversionTask):
        """更新任務中的檔案路徑"""
        paths = self.get_all_paths()
        
        if paths['audio'].exists():
            task.audio_file_path = str(paths['audio'])
        
        if paths['video'].exists():
            task.video_file_path = str(paths['video'])
        
        if paths['thumbnail'].exists():
            task.thumbnail_file_path = str(paths['thumbnail'])
        
        if paths['srt'].exists():
            task.srt_file_path = str(paths['srt'])
        
        if paths['txt'].exists():
            task.txt_file_path = str(paths['txt'])