"""
任務檔案管理系統
提供轉換任務的檔案保存、組織和管理功能
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from datetime import datetime
import logging
import mimetypes
import hashlib

logger = logging.getLogger(__name__)

class TaskFileManager:
    """任務檔案管理類別"""
    
    def __init__(self, base_path: str = "history/tasks"):
        """
        初始化檔案管理器
        
        Args:
            base_path: 任務資料夾的基礎路徑
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"任務檔案管理器初始化，基礎路徑: {self.base_path}")
    
    def create_task_folder(self, task_id: str, task_name: str, source_type: str = "file") -> Path:
        """
        建立任務資料夾，使用有意義的命名規則
        
        Args:
            task_id: 任務唯一識別碼
            task_name: 任務名稱或描述
            source_type: 來源類型 ('file' 或 'youtube')
            
        Returns:
            Path: 建立的任務資料夾路徑
        """
        try:
            # 生成時間戳記 (格式: YYYYMMDD_HHMMSS)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 清理任務名稱，移除不適合檔案名稱的字元
            clean_name = self._sanitize_filename(task_name)
            
            # 限制名稱長度避免路徑過長
            if len(clean_name) > 50:
                clean_name = clean_name[:50]
            
            # 建立資料夾名稱: 時間戳記_來源類型_任務名稱_任務ID前8碼
            folder_name = f"{timestamp}_{source_type}_{clean_name}_{task_id[:8]}"
            
            # 建立完整路徑
            task_folder = self.base_path / folder_name
            task_folder.mkdir(parents=True, exist_ok=True)
            
            # 建立 .task_info 檔案記錄任務資訊
            task_info = {
                "task_id": task_id,
                "task_name": task_name,
                "source_type": source_type,
                "created_at": datetime.now().isoformat(),
                "folder_path": str(task_folder)
            }
            
            info_file = task_folder / ".task_info"
            with open(info_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(task_info, f, ensure_ascii=False, indent=2)
            
            logger.info(f"建立任務資料夾: {task_folder}")
            return task_folder
            
        except Exception as e:
            logger.error(f"建立任務資料夾失敗: {e}")
            raise
    
    def save_original_file(self, task_folder: Path, source_file: Path, 
                          source_type: str, original_filename: Optional[str] = None) -> Path:
        """
        保存原始檔案到任務資料夾
        
        Args:
            task_folder: 任務資料夾路徑
            source_file: 來源檔案路徑
            source_type: 來源類型 ('file' 或 'youtube')
            original_filename: 原始檔案名稱（用於上傳檔案）
            
        Returns:
            Path: 保存後的檔案路徑
        """
        try:
            if not source_file.exists():
                raise FileNotFoundError(f"來源檔案不存在: {source_file}")
            
            # 決定目標檔案名稱
            if source_type == "youtube":
                # YouTube 檔案通常是 MP3 格式
                target_filename = "original.mp3"
            else:
                # 上傳檔案保持原始副檔名
                if original_filename:
                    ext = Path(original_filename).suffix
                    target_filename = f"original{ext}"
                else:
                    target_filename = f"original{source_file.suffix}"
            
            target_path = task_folder / target_filename
            
            # 複製檔案
            shutil.copy2(source_file, target_path)
            
            # 記錄檔案資訊
            file_info = self.get_file_info(target_path)
            logger.info(f"保存原始檔案: {target_path} ({file_info['size_mb']:.2f} MB)")
            
            return target_path
            
        except Exception as e:
            logger.error(f"保存原始檔案失敗: {e}")
            raise
    
    async def save_video_file(self, task_folder: Path, video_path: Path, 
                             video_title: Optional[str] = None) -> Path:
        """
        保存影片檔案到任務資料夾
        
        Args:
            task_folder: 任務資料夾路徑
            video_path: 影片檔案路徑
            video_title: 影片標題（用於檔案命名）
            
        Returns:
            Path: 保存後的影片檔案路徑
        """
        try:
            if not video_path.exists():
                raise FileNotFoundError(f"影片檔案不存在: {video_path}")
            
            # 決定目標檔案名稱
            if video_title:
                clean_title = self._sanitize_filename(video_title)
                if len(clean_title) > 50:
                    clean_title = clean_title[:50]
                target_filename = f"{clean_title}{video_path.suffix}"
            else:
                target_filename = f"video{video_path.suffix}"
            
            target_path = task_folder / target_filename
            
            # 如果檔案已存在，添加數字後綴
            counter = 1
            original_target = target_path
            while target_path.exists():
                stem = original_target.stem
                suffix = original_target.suffix
                target_path = task_folder / f"{stem}_{counter}{suffix}"
                counter += 1
            
            # 複製檔案
            shutil.copy2(video_path, target_path)
            
            # 記錄檔案資訊
            file_info = self.get_file_info(target_path)
            logger.info(f"保存影片檔案: {target_path} ({file_info['size_mb']:.2f} MB)")
            
            return target_path
            
        except Exception as e:
            logger.error(f"保存影片檔案失敗: {e}")
            raise
    
    async def save_thumbnail_file(self, task_folder: Path, thumbnail_path: Path, 
                                 video_title: Optional[str] = None) -> Path:
        """
        保存縮圖檔案到任務資料夾
        
        Args:
            task_folder: 任務資料夾路徑
            thumbnail_path: 縮圖檔案路徑
            video_title: 影片標題（用於檔案命名）
            
        Returns:
            Path: 保存後的縮圖檔案路徑
        """
        try:
            if not thumbnail_path.exists():
                raise FileNotFoundError(f"縮圖檔案不存在: {thumbnail_path}")
            
            # 決定目標檔案名稱
            if video_title:
                clean_title = self._sanitize_filename(video_title)
                if len(clean_title) > 50:
                    clean_title = clean_title[:50]
                target_filename = f"{clean_title}_thumbnail{thumbnail_path.suffix}"
            else:
                target_filename = f"thumbnail{thumbnail_path.suffix}"
            
            target_path = task_folder / target_filename
            
            # 如果檔案已存在，添加數字後綴
            counter = 1
            original_target = target_path
            while target_path.exists():
                stem = original_target.stem
                suffix = original_target.suffix
                target_path = task_folder / f"{stem}_{counter}{suffix}"
                counter += 1
            
            # 複製檔案
            shutil.copy2(thumbnail_path, target_path)
            
            # 記錄檔案資訊
            file_info = self.get_file_info(target_path)
            logger.info(f"保存縮圖檔案: {target_path} ({file_info['size_mb']:.2f} MB)")
            
            return target_path
            
        except Exception as e:
            logger.error(f"保存縮圖檔案失敗: {e}")
            raise
    
    def save_transcript_files(self, task_folder: Path, segments: List[Dict], 
                            full_text: str, task_name: str = "") -> Tuple[Path, Path]:
        """
        保存轉錄結果檔案 (SRT 字幕檔和 TXT 文字檔)
        
        Args:
            task_folder: 任務資料夾路徑
            segments: 轉錄段落列表
            full_text: 完整轉錄文字
            task_name: 任務名稱（用於檔案命名）
            
        Returns:
            Tuple[Path, Path]: (SRT檔案路徑, TXT檔案路徑)
        """
        try:
            # 生成 SRT 字幕檔案
            srt_content = self._generate_srt_content(segments)
            srt_filename = "transcript.srt" if not task_name else f"{self._sanitize_filename(task_name)}.srt"
            srt_path = task_folder / srt_filename
            
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            # 生成 TXT 文字檔案
            txt_filename = "transcript.txt" if not task_name else f"{self._sanitize_filename(task_name)}.txt"
            txt_path = task_folder / txt_filename
            
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(full_text)
            
            logger.info(f"保存轉錄檔案: {srt_path}, {txt_path}")
            return srt_path, txt_path
            
        except Exception as e:
            logger.error(f"保存轉錄檔案失敗: {e}")
            raise
    
    def get_task_files(self, task_folder: Path) -> List[Dict]:
        """
        取得任務資料夾內的所有檔案資訊
        
        Args:
            task_folder: 任務資料夾路徑
            
        Returns:
            List[Dict]: 檔案資訊列表
        """
        try:
            if not task_folder.exists():
                logger.warning(f"任務資料夾不存在: {task_folder}")
                return []
            
            files = []
            for file_path in task_folder.iterdir():
                if file_path.is_file() and not file_path.name.startswith('.'):
                    file_info = self.get_file_info(file_path)
                    file_info['file_type'] = self._determine_file_type(file_path)
                    files.append(file_info)
            
            # 按檔案類型排序 (audio -> video -> thumbnail -> srt -> txt -> image -> other)
            type_order = {
                'audio': 0, 
                'video': 1, 
                'thumbnail': 2, 
                'srt': 3, 
                'txt': 4, 
                'image': 5, 
                'other': 6
            }
            files.sort(key=lambda x: type_order.get(x['file_type'], 6))
            
            return files
            
        except Exception as e:
            logger.error(f"取得任務檔案失敗: {e}")
            return []
    
    def delete_task_folder(self, task_folder: Path) -> bool:
        """
        刪除任務資料夾及其所有內容
        
        Args:
            task_folder: 要刪除的任務資料夾路徑
            
        Returns:
            bool: 刪除是否成功
        """
        try:
            if not task_folder.exists():
                logger.warning(f"任務資料夾不存在: {task_folder}")
                return True  # 已經不存在，視為成功
            
            # 確保路徑在我們的基礎目錄內，避免誤刪
            if not str(task_folder).startswith(str(self.base_path)):
                logger.error(f"拒絕刪除基礎路徑外的資料夾: {task_folder}")
                return False
            
            shutil.rmtree(task_folder)
            logger.info(f"刪除任務資料夾: {task_folder}")
            return True
            
        except Exception as e:
            logger.error(f"刪除任務資料夾失敗: {e}")
            return False
    
    def get_file_info(self, file_path: Path) -> Dict:
        """
        取得檔案的詳細資訊
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            Dict: 檔案資訊字典
        """
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"檔案不存在: {file_path}")
            
            stat = file_path.stat()
            
            # 計算檔案雜湊值（用於完整性檢查）
            file_hash = self._calculate_file_hash(file_path)
            
            # 取得 MIME 類型
            mime_type, _ = mimetypes.guess_type(str(file_path))
            
            return {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'file_size': stat.st_size,
                'size_mb': stat.st_size / (1024 * 1024),
                'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'mime_type': mime_type,
                'file_hash': file_hash,
                'extension': file_path.suffix.lower()
            }
            
        except Exception as e:
            logger.error(f"取得檔案資訊失敗: {e}")
            return {
                'file_name': file_path.name if file_path else 'unknown',
                'file_path': str(file_path) if file_path else '',
                'file_size': 0,
                'size_mb': 0,
                'error': str(e)
            }    

    def move_temp_file_to_task(self, temp_file: Path, task_folder: Path, 
                              target_filename: str) -> Path:
        """
        將臨時檔案移動到任務資料夾
        
        Args:
            temp_file: 臨時檔案路徑
            task_folder: 目標任務資料夾
            target_filename: 目標檔案名稱
            
        Returns:
            Path: 移動後的檔案路徑
        """
        try:
            target_path = task_folder / target_filename
            
            # 如果是同一個檔案系統，使用移動操作（更快）
            if temp_file.exists():
                shutil.move(str(temp_file), str(target_path))
                logger.info(f"移動檔案: {temp_file} -> {target_path}")
            else:
                raise FileNotFoundError(f"臨時檔案不存在: {temp_file}")
            
            return target_path
            
        except Exception as e:
            logger.error(f"移動臨時檔案失敗: {e}")
            raise
    
    def get_task_folder_by_id(self, task_id: str) -> Optional[Path]:
        """
        根據任務 ID 尋找對應的任務資料夾
        
        Args:
            task_id: 任務 ID
            
        Returns:
            Optional[Path]: 任務資料夾路徑，如果找不到則回傳 None
        """
        try:
            # 搜尋包含該任務 ID 的資料夾
            for folder in self.base_path.iterdir():
                if folder.is_dir() and task_id[:8] in folder.name:
                    # 驗證是否為正確的任務資料夾
                    info_file = folder / ".task_info"
                    if info_file.exists():
                        try:
                            import json
                            with open(info_file, 'r', encoding='utf-8') as f:
                                info = json.load(f)
                                if info.get('task_id') == task_id:
                                    return folder
                        except Exception:
                            continue
            
            logger.warning(f"找不到任務 ID {task_id} 對應的資料夾")
            return None
            
        except Exception as e:
            logger.error(f"搜尋任務資料夾失敗: {e}")
            return None
    
    def validate_task_folder_integrity(self, task_folder: Path) -> Dict:
        """
        驗證任務資料夾的完整性
        
        Args:
            task_folder: 任務資料夾路徑
            
        Returns:
            Dict: 驗證結果
        """
        try:
            result = {
                'is_valid': True,
                'errors': [],
                'warnings': [],
                'file_count': 0,
                'total_size': 0
            }
            
            if not task_folder.exists():
                result['is_valid'] = False
                result['errors'].append('任務資料夾不存在')
                return result
            
            # 檢查 .task_info 檔案
            info_file = task_folder / ".task_info"
            if not info_file.exists():
                result['warnings'].append('缺少任務資訊檔案')
            
            # 統計檔案
            files = list(task_folder.iterdir())
            result['file_count'] = len([f for f in files if f.is_file()])
            
            # 計算總大小
            total_size = 0
            for file_path in files:
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            
            result['total_size'] = total_size
            result['total_size_mb'] = total_size / (1024 * 1024)
            
            # 檢查是否有基本檔案類型
            has_audio = any(self._determine_file_type(f) == 'audio' for f in files if f.is_file())
            has_video = any(self._determine_file_type(f) == 'video' for f in files if f.is_file())
            has_thumbnail = any(self._determine_file_type(f) == 'thumbnail' for f in files if f.is_file())
            has_transcript = any(f.suffix.lower() in ['.srt', '.txt'] for f in files if f.is_file())
            
            if not has_audio:
                result['warnings'].append('缺少音訊檔案')
            if not has_transcript:
                result['warnings'].append('缺少轉錄檔案')
            
            # 檢查 YouTube 任務的特殊要求
            if has_video and not has_thumbnail:
                result['warnings'].append('YouTube 任務缺少縮圖檔案')
            
            return result
            
        except Exception as e:
            logger.error(f"驗證任務資料夾完整性失敗: {e}")
            return {
                'is_valid': False,
                'errors': [f'驗證失敗: {str(e)}'],
                'warnings': [],
                'file_count': 0,
                'total_size': 0
            }
    
    async def cleanup_temp_files(self, temp_paths: List[Path]) -> int:
        """
        清理臨時檔案
        
        Args:
            temp_paths: 要清理的臨時檔案路徑列表
            
        Returns:
            int: 成功清理的檔案數量
        """
        try:
            cleaned_count = 0
            
            for temp_path in temp_paths:
                try:
                    if temp_path.exists():
                        if temp_path.is_file():
                            temp_path.unlink()
                            logger.info(f"清理臨時檔案: {temp_path}")
                            cleaned_count += 1
                        elif temp_path.is_dir():
                            shutil.rmtree(temp_path)
                            logger.info(f"清理臨時資料夾: {temp_path}")
                            cleaned_count += 1
                except Exception as e:
                    logger.warning(f"清理臨時檔案失敗 {temp_path}: {e}")
                    continue
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理臨時檔案失敗: {e}")
            return 0
    
    def get_video_file_info(self, video_path: Path) -> Dict:
        """
        獲取影片檔案資訊
        
        Args:
            video_path: 影片檔案路徑
            
        Returns:
            Dict: 影片檔案資訊字典
        """
        try:
            if not video_path.exists():
                raise FileNotFoundError(f"影片檔案不存在: {video_path}")
            
            # 獲取基本檔案資訊
            file_info = self.get_file_info(video_path)
            
            # 添加影片特定資訊
            file_info.update({
                'is_video': True,
                'video_format': video_path.suffix.lower().lstrip('.'),
                'estimated_duration': None,  # 可以後續使用 ffprobe 獲取
                'estimated_resolution': None  # 可以後續使用 ffprobe 獲取
            })
            
            return file_info
            
        except Exception as e:
            logger.error(f"獲取影片檔案資訊失敗: {e}")
            return {
                'file_name': video_path.name if video_path else 'unknown',
                'file_path': str(video_path) if video_path else '',
                'file_size': 0,
                'size_mb': 0,
                'is_video': True,
                'error': str(e)
            }
    
    def cleanup_empty_folders(self) -> int:
        """
        清理空的任務資料夾
        
        Returns:
            int: 清理的資料夾數量
        """
        try:
            cleaned_count = 0
            
            for folder in self.base_path.iterdir():
                if folder.is_dir():
                    # 檢查資料夾是否為空或只包含 .task_info
                    files = list(folder.iterdir())
                    non_info_files = [f for f in files if f.name != '.task_info']
                    
                    if len(non_info_files) == 0:
                        logger.info(f"清理空資料夾: {folder}")
                        shutil.rmtree(folder)
                        cleaned_count += 1
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理空資料夾失敗: {e}")
            return 0
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理檔案名稱，移除不適合的字元
        
        Args:
            filename: 原始檔案名稱
            
        Returns:
            str: 清理後的檔案名稱
        """
        # 移除或替換不適合檔案名稱的字元
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # 移除多餘的空格和點
        filename = filename.strip(' .')
        
        # 如果名稱為空，使用預設名稱
        if not filename:
            filename = 'untitled'
        
        return filename
    
    def _determine_file_type(self, file_path: Path) -> str:
        """
        根據檔案副檔名判斷檔案類型
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            str: 檔案類型 ('audio', 'video', 'thumbnail', 'srt', 'txt', 'other')
        """
        ext = file_path.suffix.lower()
        filename = file_path.name.lower()
        
        # 檢查是否為縮圖檔案
        if 'thumbnail' in filename and ext in ['.jpg', '.jpeg', '.png', '.webp']:
            return 'thumbnail'
        
        # 檢查檔案類型
        if ext in ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac']:
            return 'audio'
        elif ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
            return 'video'
        elif ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            return 'image'
        elif ext == '.srt':
            return 'srt'
        elif ext == '.txt':
            return 'txt'
        else:
            return 'other'
    
    def _generate_srt_content(self, segments: List[Dict]) -> str:
        """
        生成 SRT 字幕檔案內容
        
        Args:
            segments: 轉錄段落列表
            
        Returns:
            str: SRT 格式內容
        """
        srt_content = ""
        
        for idx, segment in enumerate(segments, 1):
            start_time = segment.get("start", 0)
            end_time = segment.get("end", 0)
            text = segment.get("text", "")
            speaker = segment.get("speaker", "")
            
            # 將秒數轉換為 SRT 時間格式
            start_formatted = self._format_srt_time(start_time)
            end_formatted = self._format_srt_time(end_time)
            
            # 添加說話者標籤（如果有）
            if speaker:
                text = f"{speaker}: {text}"
            
            # 生成 SRT 項目
            srt_content += f"{idx}\n{start_formatted} --> {end_formatted}\n{text}\n\n"
        
        return srt_content
    
    def _format_srt_time(self, seconds: float) -> str:
        """
        將秒數轉換為 SRT 時間格式 (HH:MM:SS,mmm)
        
        Args:
            seconds: 秒數
            
        Returns:
            str: SRT 時間格式字串
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
    
    def _calculate_file_hash(self, file_path: Path, algorithm: str = 'md5') -> str:
        """
        計算檔案的雜湊值
        
        Args:
            file_path: 檔案路徑
            algorithm: 雜湊演算法 ('md5', 'sha1', 'sha256')
            
        Returns:
            str: 檔案雜湊值
        """
        try:
            hash_obj = hashlib.new(algorithm)
            
            with open(file_path, 'rb') as f:
                # 分塊讀取以處理大檔案
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            logger.error(f"計算檔案雜湊值失敗: {e}")
            return ""


# 全域檔案管理器實例
_file_manager_instance: Optional[TaskFileManager] = None

def get_file_manager() -> TaskFileManager:
    """
    取得檔案管理器實例（單例模式）
    
    Returns:
        TaskFileManager: 檔案管理器實例
    """
    global _file_manager_instance
    if _file_manager_instance is None:
        _file_manager_instance = TaskFileManager()
    return _file_manager_instance


if __name__ == "__main__":
    # 測試檔案管理功能
    import tempfile
    import json
    
    def test_file_manager():
        """測試檔案管理器基本功能"""
        print("開始測試檔案管理器功能...")
        
        # 使用臨時目錄進行測試
        with tempfile.TemporaryDirectory() as temp_dir:
            fm = TaskFileManager(base_path=temp_dir)
            
            # 測試建立任務資料夾
            task_id = str(uuid.uuid4())
            task_name = "測試音訊轉錄任務"
            task_folder = fm.create_task_folder(task_id, task_name, "file")
            print(f"✓ 建立任務資料夾: {task_folder}")
            
            # 測試建立測試檔案
            test_audio_file = Path(temp_dir) / "test.mp3"
            test_audio_file.write_text("fake audio content")
            
            # 測試保存原始檔案
            saved_file = fm.save_original_file(task_folder, test_audio_file, "file", "test.mp3")
            print(f"✓ 保存原始檔案: {saved_file}")
            
            # 測試保存轉錄檔案
            test_segments = [
                {"start": 0.0, "end": 5.0, "text": "這是第一段測試文字", "speaker": "SPEAKER_00"},
                {"start": 5.0, "end": 10.0, "text": "這是第二段測試文字", "speaker": "SPEAKER_01"}
            ]
            full_text = "這是第一段測試文字 這是第二段測試文字"
            
            srt_path, txt_path = fm.save_transcript_files(task_folder, test_segments, full_text, "測試")
            print(f"✓ 保存轉錄檔案: {srt_path}, {txt_path}")
            
            # 測試取得檔案列表
            files = fm.get_task_files(task_folder)
            print(f"✓ 取得檔案列表: {len(files)} 個檔案")
            for file_info in files:
                print(f"  - {file_info['file_name']} ({file_info['file_type']}, {file_info['size_mb']:.3f} MB)")
            
            # 測試根據 ID 尋找資料夾
            found_folder = fm.get_task_folder_by_id(task_id)
            print(f"✓ 根據 ID 尋找資料夾: {found_folder == task_folder}")
            
            # 測試驗證資料夾完整性
            integrity = fm.validate_task_folder_integrity(task_folder)
            print(f"✓ 驗證資料夾完整性: {integrity['is_valid']}")
            if integrity['warnings']:
                print(f"  警告: {integrity['warnings']}")
            
            # 測試刪除任務資料夾
            success = fm.delete_task_folder(task_folder)
            print(f"✓ 刪除任務資料夾: {success}")
            
        print("✓ 檔案管理器測試完成")
    
    # 執行測試
    test_file_manager()