"""
錯誤處理和驗證模組
提供 API 錯誤處理中介軟體、檔案存取權限驗證和輸入驗證功能
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
import uuid

logger = logging.getLogger(__name__)

# ==================== 錯誤代碼定義 ====================

class ErrorCodes:
    """系統錯誤代碼定義"""
    
    # 通用錯誤
    INVALID_INPUT = "INVALID_INPUT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    
    # 任務相關錯誤
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_CREATION_FAILED = "TASK_CREATION_FAILED"
    TASK_UPDATE_FAILED = "TASK_UPDATE_FAILED"
    TASK_DELETE_FAILED = "TASK_DELETE_FAILED"
    
    # 檔案相關錯誤
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_ACCESS_DENIED = "FILE_ACCESS_DENIED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_CORRUPTED = "FILE_CORRUPTED"
    
    # 資料庫相關錯誤
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_CONNECTION_FAILED = "DATABASE_CONNECTION_FAILED"
    
    # 權限相關錯誤
    PERMISSION_DENIED = "PERMISSION_DENIED"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    
    # 系統資源錯誤
    DISK_FULL = "DISK_FULL"
    MEMORY_INSUFFICIENT = "MEMORY_INSUFFICIENT"
    
    # 網路相關錯誤
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    
    # YouTube 相關錯誤
    YOUTUBE_URL_INVALID = "YOUTUBE_URL_INVALID"
    YOUTUBE_VIDEO_UNAVAILABLE = "YOUTUBE_VIDEO_UNAVAILABLE"
    YOUTUBE_METADATA_FAILED = "YOUTUBE_METADATA_FAILED"
    YOUTUBE_DOWNLOAD_FAILED = "YOUTUBE_DOWNLOAD_FAILED"
    VIDEO_DOWNLOAD_FAILED = "VIDEO_DOWNLOAD_FAILED"
    THUMBNAIL_DOWNLOAD_FAILED = "THUMBNAIL_DOWNLOAD_FAILED"
    VIDEO_FILE_TOO_LARGE = "VIDEO_FILE_TOO_LARGE"
    UNSUPPORTED_VIDEO_FORMAT = "UNSUPPORTED_VIDEO_FORMAT"
    YOUTUBE_RATE_LIMITED = "YOUTUBE_RATE_LIMITED"
    YOUTUBE_REGION_BLOCKED = "YOUTUBE_REGION_BLOCKED"
    YOUTUBE_AGE_RESTRICTED = "YOUTUBE_AGE_RESTRICTED"
    YOUTUBE_PRIVATE_VIDEO = "YOUTUBE_PRIVATE_VIDEO"

# ==================== 自訂例外類別 ====================

class HistoryAPIException(HTTPException):
    """歷史紀錄 API 自訂例外"""
    
    def __init__(
        self, 
        status_code: int, 
        detail: str, 
        error_code: str = None,
        context: Dict[str, Any] = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code or ErrorCodes.INTERNAL_ERROR
        self.context = context or {}
        self.timestamp = datetime.now().isoformat()

class ValidationException(HistoryAPIException):
    """輸入驗證例外"""
    
    def __init__(self, detail: str, field: str = None, value: Any = None):
        context = {}
        if field:
            context['field'] = field
        if value is not None:
            context['invalid_value'] = str(value)
            
        super().__init__(
            status_code=400,
            detail=detail,
            error_code=ErrorCodes.VALIDATION_ERROR,
            context=context
        )

class FileAccessException(HistoryAPIException):
    """檔案存取例外"""
    
    def __init__(self, detail: str, file_path: str = None, operation: str = None):
        context = {}
        if file_path:
            context['file_path'] = file_path
        if operation:
            context['operation'] = operation
            
        super().__init__(
            status_code=403,
            detail=detail,
            error_code=ErrorCodes.FILE_ACCESS_DENIED,
            context=context
        )

class TaskNotFoundException(HistoryAPIException):
    """任務不存在例外"""
    
    def __init__(self, task_id: str):
        super().__init__(
            status_code=404,
            detail=f"任務不存在: {task_id}",
            error_code=ErrorCodes.TASK_NOT_FOUND,
            context={'task_id': task_id}
        )

# ==================== YouTube 相關例外類別 ====================

class YouTubeException(HistoryAPIException):
    """YouTube 相關例外基礎類別"""
    
    def __init__(self, detail: str, error_code: str, youtube_url: str = None, status_code: int = 400):
        context = {}
        if youtube_url:
            context['youtube_url'] = youtube_url
            
        super().__init__(
            status_code=status_code,
            detail=detail,
            error_code=error_code,
            context=context
        )

class YouTubeURLInvalidException(YouTubeException):
    """YouTube URL 無效例外"""
    
    def __init__(self, url: str):
        super().__init__(
            detail=f"無效的 YouTube URL: {url}",
            error_code=ErrorCodes.YOUTUBE_URL_INVALID,
            youtube_url=url,
            status_code=400
        )

class YouTubeVideoUnavailableException(YouTubeException):
    """YouTube 影片無法取得例外"""
    
    def __init__(self, url: str, reason: str = None):
        detail = f"YouTube 影片無法取得: {url}"
        if reason:
            detail += f" - {reason}"
            
        super().__init__(
            detail=detail,
            error_code=ErrorCodes.YOUTUBE_VIDEO_UNAVAILABLE,
            youtube_url=url,
            status_code=404
        )

class YouTubeMetadataException(YouTubeException):
    """YouTube 元資料提取例外"""
    
    def __init__(self, url: str, reason: str = None):
        detail = f"無法獲取 YouTube 影片資訊: {url}"
        if reason:
            detail += f" - {reason}"
            
        super().__init__(
            detail=detail,
            error_code=ErrorCodes.YOUTUBE_METADATA_FAILED,
            youtube_url=url,
            status_code=500
        )

class YouTubeDownloadException(YouTubeException):
    """YouTube 下載例外"""
    
    def __init__(self, url: str, download_type: str = "音訊", reason: str = None):
        detail = f"YouTube {download_type}下載失敗: {url}"
        if reason:
            detail += f" - {reason}"
            
        error_code = ErrorCodes.YOUTUBE_DOWNLOAD_FAILED
        if download_type == "影片":
            error_code = ErrorCodes.VIDEO_DOWNLOAD_FAILED
        elif download_type == "縮圖":
            error_code = ErrorCodes.THUMBNAIL_DOWNLOAD_FAILED
            
        super().__init__(
            detail=detail,
            error_code=error_code,
            youtube_url=url,
            status_code=500
        )

class VideoProcessingException(YouTubeException):
    """影片處理例外"""
    
    def __init__(self, detail: str, file_path: str = None, operation: str = None):
        context = {}
        if file_path:
            context['file_path'] = file_path
        if operation:
            context['operation'] = operation
            
        super().__init__(
            detail=detail,
            error_code=ErrorCodes.VIDEO_DOWNLOAD_FAILED,
            status_code=500
        )
        self.context.update(context)

class VideoFileTooLargeException(YouTubeException):
    """影片檔案過大例外"""
    
    def __init__(self, url: str, file_size: int, max_size: int):
        detail = f"影片檔案過大 ({file_size / 1024 / 1024:.1f}MB)，超過限制 ({max_size / 1024 / 1024}MB)"
        
        super().__init__(
            detail=detail,
            error_code=ErrorCodes.VIDEO_FILE_TOO_LARGE,
            youtube_url=url,
            status_code=413
        )
        self.context.update({
            'file_size': file_size,
            'max_size': max_size
        })

class UnsupportedVideoFormatException(YouTubeException):
    """不支援的影片格式例外"""
    
    def __init__(self, url: str, format_info: str = None):
        detail = f"不支援的影片格式: {url}"
        if format_info:
            detail += f" - {format_info}"
            
        super().__init__(
            detail=detail,
            error_code=ErrorCodes.UNSUPPORTED_VIDEO_FORMAT,
            youtube_url=url,
            status_code=415
        )

class YouTubeRateLimitedException(YouTubeException):
    """YouTube 速率限制例外"""
    
    def __init__(self, url: str):
        super().__init__(
            detail=f"YouTube API 速率限制，請稍後再試: {url}",
            error_code=ErrorCodes.YOUTUBE_RATE_LIMITED,
            youtube_url=url,
            status_code=429
        )

class YouTubeRegionBlockedException(YouTubeException):
    """YouTube 地區封鎖例外"""
    
    def __init__(self, url: str):
        super().__init__(
            detail=f"此 YouTube 影片在您的地區無法觀看: {url}",
            error_code=ErrorCodes.YOUTUBE_REGION_BLOCKED,
            youtube_url=url,
            status_code=403
        )

class YouTubeAgeRestrictedException(YouTubeException):
    """YouTube 年齡限制例外"""
    
    def __init__(self, url: str):
        super().__init__(
            detail=f"此 YouTube 影片有年齡限制，無法處理: {url}",
            error_code=ErrorCodes.YOUTUBE_AGE_RESTRICTED,
            youtube_url=url,
            status_code=403
        )

class YouTubePrivateVideoException(YouTubeException):
    """YouTube 私人影片例外"""
    
    def __init__(self, url: str):
        super().__init__(
            detail=f"此 YouTube 影片為私人影片，無法存取: {url}",
            error_code=ErrorCodes.YOUTUBE_PRIVATE_VIDEO,
            youtube_url=url,
            status_code=403
        )

# ==================== 輸入驗證模型 ====================

class TaskSearchRequest(BaseModel):
    """任務搜尋請求驗證模型"""
    
    q: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    file_type: Optional[str] = None
    status: Optional[str] = None
    limit: Optional[int] = 50
    offset: Optional[int] = 0
    
    @validator('q')
    def validate_query(cls, v):
        if v is not None:
            # 移除危險字元，防止 SQL 注入
            if len(v.strip()) == 0:
                return None
            if len(v) > 200:
                raise ValueError("搜尋關鍵字長度不能超過 200 字元")
            # 移除特殊字元，只保留中英文、數字、空格和常見標點
            cleaned = re.sub(r'[^\w\s\u4e00-\u9fff\-_.,!?()]', '', v)
            return cleaned.strip()
        return v
    
    @validator('date_from', 'date_to')
    def validate_date(cls, v):
        if v is not None:
            try:
                # 驗證 ISO 日期格式
                datetime.fromisoformat(v.replace('Z', '+00:00'))
                return v
            except ValueError:
                raise ValueError("日期格式無效，請使用 ISO 格式 (例: 2024-01-01)")
        return v
    
    @validator('file_type')
    def validate_file_type(cls, v):
        if v is not None:
            allowed_types = ['audio', 'srt', 'txt']
            if v not in allowed_types:
                raise ValueError(f"無效的檔案類型，允許的類型: {', '.join(allowed_types)}")
        return v
    
    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            allowed_statuses = ['processing', 'completed', 'failed']
            if v not in allowed_statuses:
                raise ValueError(f"無效的任務狀態，允許的狀態: {', '.join(allowed_statuses)}")
        return v
    
    @validator('limit')
    def validate_limit(cls, v):
        if v is not None:
            if v < 1 or v > 100:
                raise ValueError("限制數量必須在 1-100 之間")
        return v
    
    @validator('offset')
    def validate_offset(cls, v):
        if v is not None:
            if v < 0:
                raise ValueError("偏移量不能為負數")
        return v

class TaskCreateRequest(BaseModel):
    """任務建立請求驗證模型"""
    
    name: str
    source_type: str
    source_info: Optional[str] = None
    model_used: str = "whisper-1"
    language: Optional[str] = None
    has_diarization: bool = False
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("任務名稱不能為空")
        if len(v) > 200:
            raise ValueError("任務名稱長度不能超過 200 字元")
        # 清理檔案名稱中的危險字元
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', v.strip())
        return cleaned
    
    @validator('source_type')
    def validate_source_type(cls, v):
        allowed_types = ['file', 'youtube']
        if v not in allowed_types:
            raise ValueError(f"無效的來源類型，允許的類型: {', '.join(allowed_types)}")
        return v
    
    @validator('source_info')
    def validate_source_info(cls, v):
        if v is not None and len(v) > 500:
            raise ValueError("來源資訊長度不能超過 500 字元")
        return v
    
    @validator('model_used')
    def validate_model(cls, v):
        allowed_models = ['whisper-1']  # 可擴展支援更多模型
        if v not in allowed_models:
            raise ValueError(f"無效的模型，允許的模型: {', '.join(allowed_models)}")
        return v
    
    @validator('language')
    def validate_language(cls, v):
        if v is not None:
            # 簡單的語言代碼驗證
            if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', v):
                raise ValueError("無效的語言代碼格式")
        return v

# ==================== 檔案存取權限驗證 ====================

class FileAccessValidator:
    """檔案存取權限驗證器"""
    
    def __init__(self, base_paths: List[str] = None):
        """
        初始化檔案存取驗證器
        
        Args:
            base_paths: 允許存取的基礎路徑列表
        """
        self.base_paths = [Path(p).resolve() for p in (base_paths or ["history/tasks"])]
        self.max_file_size = 500 * 1024 * 1024  # 500MB
        self.allowed_extensions = {
            # 音訊格式
            '.mp3', '.wav', '.m4a', '.flac', '.ogg',
            # 字幕和文字格式
            '.srt', '.txt',
            # 影片格式
            '.mp4', '.webm', '.mkv', '.avi',
            # 圖片格式（縮圖）
            '.jpg', '.jpeg', '.png', '.webp', '.gif'
        }
    
    def validate_file_path(self, file_path: Union[str, Path]) -> Path:
        """
        驗證檔案路徑是否安全且在允許的範圍內
        
        Args:
            file_path: 要驗證的檔案路徑
            
        Returns:
            Path: 驗證後的路徑物件
            
        Raises:
            FileAccessException: 檔案路徑不安全或不在允許範圍內
        """
        try:
            path = Path(file_path).resolve()
            
            # 檢查路徑遍歷攻擊
            if '..' in str(file_path):
                raise FileAccessException(
                    "檔案路徑包含不安全的字元",
                    file_path=str(file_path),
                    operation="path_validation"
                )
            
            # 檢查是否在允許的基礎路徑內
            is_allowed = False
            for base_path in self.base_paths:
                try:
                    path.relative_to(base_path)
                    is_allowed = True
                    break
                except ValueError:
                    continue
            
            if not is_allowed:
                raise FileAccessException(
                    "檔案路徑不在允許的存取範圍內",
                    file_path=str(path),
                    operation="path_validation"
                )
            
            return path
            
        except Exception as e:
            if isinstance(e, FileAccessException):
                raise
            raise FileAccessException(
                f"檔案路徑驗證失敗: {str(e)}",
                file_path=str(file_path),
                operation="path_validation"
            )
    
    def validate_file_access(self, file_path: Union[str, Path], operation: str = "read") -> bool:
        """
        驗證檔案存取權限
        
        Args:
            file_path: 檔案路徑
            operation: 操作類型 ('read', 'write', 'delete')
            
        Returns:
            bool: 是否有權限
            
        Raises:
            FileAccessException: 沒有存取權限
        """
        try:
            validated_path = self.validate_file_path(file_path)
            
            # 檢查檔案是否存在（對於讀取和刪除操作）
            if operation in ['read', 'delete'] and not validated_path.exists():
                raise FileAccessException(
                    "檔案不存在",
                    file_path=str(validated_path),
                    operation=operation
                )
            
            # 檢查檔案大小（對於讀取操作）
            if operation == 'read' and validated_path.exists():
                file_size = validated_path.stat().st_size
                if file_size > self.max_file_size:
                    raise FileAccessException(
                        f"檔案過大 ({file_size / 1024 / 1024:.1f}MB)，超過限制 ({self.max_file_size / 1024 / 1024}MB)",
                        file_path=str(validated_path),
                        operation=operation
                    )
            
            # 檢查檔案副檔名
            if validated_path.suffix.lower() not in self.allowed_extensions:
                raise FileAccessException(
                    f"不允許的檔案類型: {validated_path.suffix}",
                    file_path=str(validated_path),
                    operation=operation
                )
            
            # 檢查系統權限
            if operation == 'read' and not os.access(validated_path, os.R_OK):
                raise FileAccessException(
                    "沒有檔案讀取權限",
                    file_path=str(validated_path),
                    operation=operation
                )
            
            if operation == 'write':
                parent_dir = validated_path.parent
                if not os.access(parent_dir, os.W_OK):
                    raise FileAccessException(
                        "沒有目錄寫入權限",
                        file_path=str(parent_dir),
                        operation=operation
                    )
            
            if operation == 'delete' and not os.access(validated_path, os.W_OK):
                raise FileAccessException(
                    "沒有檔案刪除權限",
                    file_path=str(validated_path),
                    operation=operation
                )
            
            return True
            
        except FileAccessException:
            raise
        except Exception as e:
            raise FileAccessException(
                f"檔案權限驗證失敗: {str(e)}",
                file_path=str(file_path),
                operation=operation
            )
    
    def validate_disk_space(self, required_space: int = None) -> bool:
        """
        檢查磁碟空間是否足夠
        
        Args:
            required_space: 需要的空間大小（位元組）
            
        Returns:
            bool: 磁碟空間是否足夠
            
        Raises:
            FileAccessException: 磁碟空間不足
        """
        try:
            # 檢查第一個基礎路徑的磁碟空間
            base_path = self.base_paths[0] if self.base_paths else Path(".")
            
            # 確保路徑存在
            base_path.mkdir(parents=True, exist_ok=True)
            
            # 取得磁碟使用情況（跨平台支援）
            if hasattr(os, 'statvfs'):
                # Unix/Linux 系統
                stat = os.statvfs(base_path)
                free_space = stat.f_bavail * stat.f_frsize
            else:
                # Windows 系統
                import shutil
                _, _, free_space = shutil.disk_usage(base_path)
            
            # 保留至少 100MB 的緩衝空間
            buffer_space = 100 * 1024 * 1024
            available_space = free_space - buffer_space
            
            if required_space and required_space > available_space:
                raise FileAccessException(
                    f"磁碟空間不足，需要 {required_space / 1024 / 1024:.1f}MB，可用 {available_space / 1024 / 1024:.1f}MB",
                    operation="disk_space_check"
                )
            
            # 如果可用空間少於 500MB，發出警告
            if available_space < 500 * 1024 * 1024:
                logger.warning(f"磁碟空間不足，剩餘 {available_space / 1024 / 1024:.1f}MB")
            
            return True
            
        except FileAccessException:
            raise
        except Exception as e:
            raise FileAccessException(
                f"磁碟空間檢查失敗: {str(e)}",
                operation="disk_space_check"
            )

# ==================== 輸入清理和驗證工具 ====================

class InputSanitizer:
    """輸入清理和驗證工具"""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理檔案名稱，移除危險字元
        
        Args:
            filename: 原始檔案名稱
            
        Returns:
            str: 清理後的檔案名稱
        """
        if not filename:
            return "untitled"
        
        # 移除危險字元
        dangerous_chars = '<>:"/\\|?*'
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # 移除控制字元
        filename = ''.join(char for char in filename if ord(char) >= 32)
        
        # 限制長度
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        # 移除前後空格和點
        filename = filename.strip(' .')
        
        return filename or "untitled"
    
    @staticmethod
    def sanitize_search_query(query: str) -> str:
        """
        清理搜尋查詢，防止注入攻擊
        
        Args:
            query: 原始查詢字串
            
        Returns:
            str: 清理後的查詢字串
        """
        if not query:
            return ""
        
        # 移除 SQL 注入相關字元
        dangerous_patterns = [
            r"[';\"\\]",  # 引號和反斜線
            r"--",        # SQL 註解
            r"/\*.*?\*/", # 多行註解
            r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|EXEC|UNION|SELECT)\b"  # SQL 關鍵字
        ]
        
        cleaned = query
        for pattern in dangerous_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
        # 只保留安全字元
        cleaned = re.sub(r'[^\w\s\u4e00-\u9fff\-_.,!?()]', '', cleaned)
        
        return cleaned.strip()
    
    @staticmethod
    def validate_uuid(uuid_string: str) -> bool:
        """
        驗證 UUID 格式
        
        Args:
            uuid_string: UUID 字串
            
        Returns:
            bool: 是否為有效的 UUID
        """
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_task_id(task_id: str) -> str:
        """
        驗證和清理任務 ID
        
        Args:
            task_id: 任務 ID
            
        Returns:
            str: 驗證後的任務 ID
            
        Raises:
            ValidationException: 任務 ID 格式無效
        """
        if not task_id or not isinstance(task_id, str):
            raise ValidationException("任務 ID 不能為空", field="task_id", value=task_id)
        
        # 移除前後空格
        task_id = task_id.strip()
        
        # 驗證 UUID 格式
        if not InputSanitizer.validate_uuid(task_id):
            raise ValidationException("任務 ID 格式無效", field="task_id", value=task_id)
        
        return task_id
    
    @staticmethod
    def validate_youtube_url(url: str) -> str:
        """
        驗證和清理 YouTube URL
        
        Args:
            url: YouTube URL
            
        Returns:
            str: 驗證後的 YouTube URL
            
        Raises:
            YouTubeURLInvalidException: YouTube URL 格式無效
        """
        if not url or not isinstance(url, str):
            raise YouTubeURLInvalidException("YouTube URL 不能為空")
        
        # 移除前後空格
        url = url.strip()
        
        # 驗證 YouTube URL 格式
        youtube_patterns = [
            r'^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'^https?://(?:www\.)?youtu\.be/[\w-]+',
            r'^https?://(?:www\.)?youtube\.com/embed/[\w-]+',
            r'^https?://(?:m\.)?youtube\.com/watch\?v=[\w-]+',
        ]
        
        is_valid = False
        for pattern in youtube_patterns:
            if re.match(pattern, url):
                is_valid = True
                break
        
        if not is_valid:
            raise YouTubeURLInvalidException(url)
        
        return url
    
    @staticmethod
    def extract_youtube_video_id(url: str) -> str:
        """
        從 YouTube URL 提取影片 ID
        
        Args:
            url: YouTube URL
            
        Returns:
            str: 影片 ID
            
        Raises:
            YouTubeURLInvalidException: 無法提取影片 ID
        """
        # 先驗證 URL
        validated_url = InputSanitizer.validate_youtube_url(url)
        
        # 提取影片 ID 的正則表達式
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            r'youtube\.com/watch\?.*v=([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, validated_url)
            if match:
                video_id = match.group(1)
                # 驗證影片 ID 格式（YouTube 影片 ID 通常是 11 個字元）
                if re.match(r'^[\w-]{11}$', video_id):
                    return video_id
        
        raise YouTubeURLInvalidException(f"無法從 URL 提取影片 ID: {url}")

# ==================== 全域檔案存取驗證器實例 ====================

# 建立全域檔案存取驗證器
file_access_validator = FileAccessValidator()

def get_file_access_validator() -> FileAccessValidator:
    """取得檔案存取驗證器實例"""
    return file_access_validator

# ==================== YouTube 錯誤處理策略 ====================

class YouTubeErrorHandler:
    """YouTube 錯誤處理策略類別"""
    
    @staticmethod
    def handle_ydl_error(error: Exception, youtube_url: str) -> YouTubeException:
        """
        處理 yt-dlp 錯誤並轉換為適當的例外
        
        Args:
            error: yt-dlp 拋出的原始錯誤
            youtube_url: YouTube URL
            
        Returns:
            YouTubeException: 轉換後的例外
        """
        error_msg = str(error).lower()
        
        # 影片不可用
        if any(keyword in error_msg for keyword in ['video unavailable', 'private video', 'deleted']):
            if 'private' in error_msg:
                return YouTubePrivateVideoException(youtube_url)
            else:
                return YouTubeVideoUnavailableException(youtube_url, str(error))
        
        # 地區封鎖
        if any(keyword in error_msg for keyword in ['not available in your country', 'blocked', 'region']):
            return YouTubeRegionBlockedException(youtube_url)
        
        # 年齡限制
        if any(keyword in error_msg for keyword in ['age restricted', 'sign in', 'confirm your age']):
            return YouTubeAgeRestrictedException(youtube_url)
        
        # 速率限制
        if any(keyword in error_msg for keyword in ['rate limit', 'too many requests', '429']):
            return YouTubeRateLimitedException(youtube_url)
        
        # 網路錯誤
        if any(keyword in error_msg for keyword in ['network', 'connection', 'timeout', 'unreachable']):
            return YouTubeException(
                detail=f"網路連線錯誤: {str(error)}",
                error_code=ErrorCodes.NETWORK_ERROR,
                youtube_url=youtube_url,
                status_code=503
            )
        
        # 格式不支援
        if any(keyword in error_msg for keyword in ['format', 'codec', 'unsupported']):
            return UnsupportedVideoFormatException(youtube_url, str(error))
        
        # 預設為一般 YouTube 錯誤
        return YouTubeException(
            detail=f"YouTube 處理錯誤: {str(error)}",
            error_code=ErrorCodes.YOUTUBE_DOWNLOAD_FAILED,
            youtube_url=youtube_url,
            status_code=500
        )
    
    @staticmethod
    def handle_download_error(error: Exception, youtube_url: str, download_type: str = "音訊") -> YouTubeDownloadException:
        """
        處理下載錯誤
        
        Args:
            error: 下載錯誤
            youtube_url: YouTube URL
            download_type: 下載類型（音訊、影片、縮圖）
            
        Returns:
            YouTubeDownloadException: 下載例外
        """
        error_msg = str(error)
        
        # 檢查是否為檔案過大錯誤
        if 'file too large' in error_msg.lower() or 'size limit' in error_msg.lower():
            # 嘗試從錯誤訊息中提取檔案大小
            import re
            size_match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|GB)', error_msg, re.IGNORECASE)
            if size_match:
                size_value = float(size_match.group(1))
                size_unit = size_match.group(2).upper()
                file_size = int(size_value * (1024**3 if size_unit == 'GB' else 1024**2))
                max_size = 500 * 1024 * 1024  # 500MB 預設限制
                return VideoFileTooLargeException(youtube_url, file_size, max_size)
        
        return YouTubeDownloadException(youtube_url, download_type, error_msg)
    
    @staticmethod
    def should_retry_error(error: Exception) -> bool:
        """
        判斷錯誤是否應該重試
        
        Args:
            error: 錯誤例外
            
        Returns:
            bool: 是否應該重試
        """
        if isinstance(error, (YouTubeRateLimitedException, YouTubeRegionBlockedException, 
                             YouTubeAgeRestrictedException, YouTubePrivateVideoException)):
            return False
        
        error_msg = str(error).lower()
        
        # 網路相關錯誤可以重試
        if any(keyword in error_msg for keyword in ['network', 'connection', 'timeout', 'unreachable']):
            return True
        
        # 暫時性錯誤可以重試
        if any(keyword in error_msg for keyword in ['temporary', 'retry', 'server error', '5']):
            return True
        
        return False
    
    @staticmethod
    def get_retry_delay(attempt: int) -> float:
        """
        取得重試延遲時間（指數退避）
        
        Args:
            attempt: 重試次數
            
        Returns:
            float: 延遲秒數
        """
        import random
        base_delay = 2.0
        max_delay = 60.0
        
        delay = min(base_delay * (2 ** attempt), max_delay)
        # 加入隨機抖動避免雷群效應
        jitter = random.uniform(0.1, 0.3) * delay
        
        return delay + jitter

# ==================== YouTube 驗證工具 ====================

class YouTubeValidator:
    """YouTube 相關驗證工具"""
    
    @staticmethod
    def validate_video_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        驗證和清理 YouTube 影片元資料
        
        Args:
            metadata: 原始元資料字典
            
        Returns:
            Dict[str, Any]: 清理後的元資料
        """
        cleaned = {}
        
        # 標題清理
        title = metadata.get('title', '')
        if title:
            # 移除控制字元和危險字元
            title = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', title)
            title = re.sub(r'[<>:"/\\|?*]', '', title)
            cleaned['title'] = title.strip()[:200]  # 限制長度
        
        # 描述清理
        description = metadata.get('description', '')
        if description:
            description = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', description)
            cleaned['description'] = description.strip()[:1000]  # 限制長度
        
        # 上傳者清理
        uploader = metadata.get('uploader', '')
        if uploader:
            uploader = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', uploader)
            cleaned['uploader'] = uploader.strip()[:100]
        
        # 數值驗證
        for field in ['duration', 'view_count', 'video_duration']:
            value = metadata.get(field)
            if value is not None:
                try:
                    cleaned[field] = int(value) if int(value) >= 0 else None
                except (ValueError, TypeError):
                    cleaned[field] = None
        
        # URL 驗證
        for url_field in ['thumbnail_url', 'webpage_url']:
            url = metadata.get(url_field, '')
            if url and url.startswith(('http://', 'https://')):
                cleaned[url_field] = url[:500]  # 限制長度
        
        # 日期驗證
        upload_date = metadata.get('upload_date', '')
        if upload_date:
            # 驗證日期格式 (YYYYMMDD)
            if re.match(r'^\d{8}$', upload_date):
                cleaned['upload_date'] = upload_date
        
        return cleaned
    
    @staticmethod
    def validate_file_size(file_path: Path, max_size: int = 500 * 1024 * 1024) -> bool:
        """
        驗證檔案大小
        
        Args:
            file_path: 檔案路徑
            max_size: 最大檔案大小（位元組）
            
        Returns:
            bool: 檔案大小是否符合限制
            
        Raises:
            VideoFileTooLargeException: 檔案過大
        """
        if not file_path.exists():
            return True
        
        file_size = file_path.stat().st_size
        if file_size > max_size:
            raise VideoFileTooLargeException("", file_size, max_size)
        
        return True
    
    @staticmethod
    def validate_video_format(file_path: Path) -> bool:
        """
        驗證影片格式
        
        Args:
            file_path: 影片檔案路徑
            
        Returns:
            bool: 格式是否支援
            
        Raises:
            UnsupportedVideoFormatException: 不支援的格式
        """
        if not file_path.exists():
            return True
        
        supported_extensions = {'.mp4', '.webm', '.mkv', '.avi', '.mov'}
        file_extension = file_path.suffix.lower()
        
        if file_extension not in supported_extensions:
            raise UnsupportedVideoFormatException("", f"不支援的檔案格式: {file_extension}")
        
        return True

# ==================== 全域 YouTube 錯誤處理器實例 ====================

# 建立全域 YouTube 錯誤處理器
youtube_error_handler = YouTubeErrorHandler()
youtube_validator = YouTubeValidator()

def get_youtube_error_handler() -> YouTubeErrorHandler:
    """取得 YouTube 錯誤處理器實例"""
    return youtube_error_handler

def get_youtube_validator() -> YouTubeValidator:
    """取得 YouTube 驗證器實例"""
    return youtube_validator