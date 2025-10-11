"""
配置管理模組
處理所有環境變數和系統配置
"""

import os
from typing import List, Optional, Union
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """伺服器基本配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"


@dataclass
class WhisperConfig:
    """Whisper 模型配置"""
    device: str = "cuda"
    compute_type: str = "float16"
    model_size: str = "medium"
    cache_dir: str = "./models"


@dataclass
class DiarizationConfig:
    """說話者辨識配置"""
    device: str = "cuda"
    huggingface_token: Optional[str] = None


@dataclass
class DatabaseConfig:
    """資料庫配置"""
    path: str = "history/conversion_history.db"
    backup_dir: str = "database_backups"
    backup_interval: int = 24  # 小時


@dataclass
class FileStorageConfig:
    """檔案儲存配置"""
    tasks_root_dir: str = "history/tasks"
    temp_dir: str = "temp"
    max_file_size_mb: int = 500
    supported_audio_formats: List[str] = None
    
    def __post_init__(self):
        if self.supported_audio_formats is None:
            self.supported_audio_formats = ["mp3", "wav", "m4a", "flac", "ogg", "webm"]


@dataclass
class YouTubeConfig:
    """YouTube 下載配置"""
    enable_video_download: bool = True
    max_video_size_mb: int = 1000
    video_quality: str = "1080p"
    audio_quality: str = "best"
    max_concurrent_downloads: int = 3
    download_timeout: int = 300
    download_retry_count: int = 3
    enable_thumbnail_download: bool = True
    thumbnail_max_size: int = 1280


@dataclass
class CacheConfig:
    """快取系統配置"""
    enable_cache: bool = True
    metadata_cache_ttl: int = 86400  # 24小時
    thumbnail_cache_ttl: int = 604800  # 7天
    query_cache_ttl: int = 3600  # 1小時
    cache_max_items: int = 1000


@dataclass
class PerformanceConfig:
    """效能監控配置"""
    enable_performance_monitoring: bool = True
    cpu_warning_threshold: float = 80.0
    memory_warning_threshold: float = 85.0
    gpu_memory_warning_threshold: float = 90.0
    performance_monitor_interval: int = 60


@dataclass
class DiskSpaceConfig:
    """磁碟空間管理配置"""
    disk_warning_threshold: float = 80.0
    disk_cleanup_threshold: float = 85.0
    auto_cleanup_days: int = 30
    video_cleanup_days: int = 7
    temp_cleanup_interval: int = 6  # 小時


@dataclass
class MaintenanceConfig:
    """維護排程配置"""
    enable_auto_maintenance: bool = True
    maintenance_time: str = "02:00"
    maintenance_level: str = "standard"
    database_optimize_interval: int = 7  # 天


@dataclass
class SecurityConfig:
    """安全性配置"""
    enable_cors: bool = True
    cors_origins: List[str] = None
    enable_request_logging: bool = True
    max_request_size_mb: int = 100
    
    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ["http://localhost:3000", "http://localhost:8080"]


@dataclass
class LoggingConfig:
    """日誌配置"""
    log_file_path: str = "app.log"
    log_max_size_mb: int = 50
    log_backup_count: int = 5
    enable_structured_logging: bool = True


@dataclass
class WebSocketConfig:
    """WebSocket 配置"""
    websocket_timeout: int = 300
    max_websocket_connections: int = 100
    websocket_heartbeat_interval: int = 30


@dataclass
class DevelopmentConfig:
    """開發和除錯配置"""
    development_mode: bool = False
    enable_api_docs: bool = True
    enable_verbose_errors: bool = False
    test_mode: bool = False


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.server = self._load_server_config()
        self.whisper = self._load_whisper_config()
        self.diarization = self._load_diarization_config()
        self.database = self._load_database_config()
        self.file_storage = self._load_file_storage_config()
        self.youtube = self._load_youtube_config()
        self.cache = self._load_cache_config()
        self.performance = self._load_performance_config()
        self.disk_space = self._load_disk_space_config()
        self.maintenance = self._load_maintenance_config()
        self.security = self._load_security_config()
        self.logging = self._load_logging_config()
        self.websocket = self._load_websocket_config()
        self.development = self._load_development_config()
        
        # 驗證配置
        self._validate_config()
        
        # 建立必要目錄
        self._create_directories()
    
    def _get_env_bool(self, key: str, default: bool = False) -> bool:
        """獲取布林型環境變數"""
        value = os.environ.get(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def _get_env_int(self, key: str, default: int) -> int:
        """獲取整數型環境變數"""
        try:
            return int(os.environ.get(key, str(default)))
        except ValueError:
            logger.warning(f"無效的整數環境變數 {key}，使用預設值 {default}")
            return default
    
    def _get_env_float(self, key: str, default: float) -> float:
        """獲取浮點數型環境變數"""
        try:
            return float(os.environ.get(key, str(default)))
        except ValueError:
            logger.warning(f"無效的浮點數環境變數 {key}，使用預設值 {default}")
            return default
    
    def _get_env_list(self, key: str, default: List[str], separator: str = ",") -> List[str]:
        """獲取列表型環境變數"""
        value = os.environ.get(key)
        if value:
            return [item.strip() for item in value.split(separator) if item.strip()]
        return default
    
    def _load_server_config(self) -> ServerConfig:
        """載入伺服器配置"""
        return ServerConfig(
            host=os.environ.get("HOST", "0.0.0.0"),
            port=self._get_env_int("PORT", 8000),
            debug=self._get_env_bool("DEBUG", False),
            log_level=os.environ.get("LOG_LEVEL", "INFO")
        )
    
    def _load_whisper_config(self) -> WhisperConfig:
        """載入 Whisper 配置"""
        return WhisperConfig(
            device=os.environ.get("WHISPER_DEVICE", "cuda"),
            compute_type=os.environ.get("WHISPER_COMPUTE_TYPE", "float16"),
            model_size=os.environ.get("WHISPER_MODEL_SIZE", "medium"),
            cache_dir=os.environ.get("WHISPER_CACHE_DIR", "./models")
        )
    
    def _load_diarization_config(self) -> DiarizationConfig:
        """載入說話者辨識配置"""
        return DiarizationConfig(
            device=os.environ.get("DIARIZATION_DEVICE", "cuda"),
            huggingface_token=os.environ.get("HUGGINGFACE_TOKEN")
        )
    
    def _load_database_config(self) -> DatabaseConfig:
        """載入資料庫配置"""
        return DatabaseConfig(
            path=os.environ.get("DATABASE_PATH", "history/conversion_history.db"),
            backup_dir=os.environ.get("DATABASE_BACKUP_DIR", "database_backups"),
            backup_interval=self._get_env_int("DATABASE_BACKUP_INTERVAL", 24)
        )
    
    def _load_file_storage_config(self) -> FileStorageConfig:
        """載入檔案儲存配置"""
        return FileStorageConfig(
            tasks_root_dir=os.environ.get("TASKS_ROOT_DIR", "history/tasks"),
            temp_dir=os.environ.get("TEMP_DIR", "temp"),
            max_file_size_mb=self._get_env_int("MAX_FILE_SIZE_MB", 500),
            supported_audio_formats=self._get_env_list(
                "SUPPORTED_AUDIO_FORMATS", 
                ["mp3", "wav", "m4a", "flac", "ogg", "webm"]
            )
        )
    
    def _load_youtube_config(self) -> YouTubeConfig:
        """載入 YouTube 配置"""
        return YouTubeConfig(
            enable_video_download=self._get_env_bool("ENABLE_VIDEO_DOWNLOAD", True),
            max_video_size_mb=self._get_env_int("MAX_VIDEO_SIZE_MB", 1000),
            video_quality=os.environ.get("VIDEO_QUALITY", "1080p"),
            audio_quality=os.environ.get("AUDIO_QUALITY", "best"),
            max_concurrent_downloads=self._get_env_int("MAX_CONCURRENT_DOWNLOADS", 3),
            download_timeout=self._get_env_int("DOWNLOAD_TIMEOUT", 300),
            download_retry_count=self._get_env_int("DOWNLOAD_RETRY_COUNT", 3),
            enable_thumbnail_download=self._get_env_bool("ENABLE_THUMBNAIL_DOWNLOAD", True),
            thumbnail_max_size=self._get_env_int("THUMBNAIL_MAX_SIZE", 1280)
        )
    
    def _load_cache_config(self) -> CacheConfig:
        """載入快取配置"""
        return CacheConfig(
            enable_cache=self._get_env_bool("ENABLE_CACHE", True),
            metadata_cache_ttl=self._get_env_int("METADATA_CACHE_TTL", 86400),
            thumbnail_cache_ttl=self._get_env_int("THUMBNAIL_CACHE_TTL", 604800),
            query_cache_ttl=self._get_env_int("QUERY_CACHE_TTL", 3600),
            cache_max_items=self._get_env_int("CACHE_MAX_ITEMS", 1000)
        )
    
    def _load_performance_config(self) -> PerformanceConfig:
        """載入效能配置"""
        return PerformanceConfig(
            enable_performance_monitoring=self._get_env_bool("ENABLE_PERFORMANCE_MONITORING", True),
            cpu_warning_threshold=self._get_env_float("CPU_WARNING_THRESHOLD", 80.0),
            memory_warning_threshold=self._get_env_float("MEMORY_WARNING_THRESHOLD", 85.0),
            gpu_memory_warning_threshold=self._get_env_float("GPU_MEMORY_WARNING_THRESHOLD", 90.0),
            performance_monitor_interval=self._get_env_int("PERFORMANCE_MONITOR_INTERVAL", 60)
        )
    
    def _load_disk_space_config(self) -> DiskSpaceConfig:
        """載入磁碟空間配置"""
        return DiskSpaceConfig(
            disk_warning_threshold=self._get_env_float("DISK_WARNING_THRESHOLD", 80.0),
            disk_cleanup_threshold=self._get_env_float("DISK_CLEANUP_THRESHOLD", 85.0),
            auto_cleanup_days=self._get_env_int("AUTO_CLEANUP_DAYS", 30),
            video_cleanup_days=self._get_env_int("VIDEO_CLEANUP_DAYS", 7),
            temp_cleanup_interval=self._get_env_int("TEMP_CLEANUP_INTERVAL", 6)
        )
    
    def _load_maintenance_config(self) -> MaintenanceConfig:
        """載入維護配置"""
        return MaintenanceConfig(
            enable_auto_maintenance=self._get_env_bool("ENABLE_AUTO_MAINTENANCE", True),
            maintenance_time=os.environ.get("MAINTENANCE_TIME", "02:00"),
            maintenance_level=os.environ.get("MAINTENANCE_LEVEL", "standard"),
            database_optimize_interval=self._get_env_int("DATABASE_OPTIMIZE_INTERVAL", 7)
        )
    
    def _load_security_config(self) -> SecurityConfig:
        """載入安全性配置"""
        return SecurityConfig(
            enable_cors=self._get_env_bool("ENABLE_CORS", True),
            cors_origins=self._get_env_list(
                "CORS_ORIGINS", 
                ["http://localhost:3000", "http://localhost:8080"]
            ),
            enable_request_logging=self._get_env_bool("ENABLE_REQUEST_LOGGING", True),
            max_request_size_mb=self._get_env_int("MAX_REQUEST_SIZE_MB", 100)
        )
    
    def _load_logging_config(self) -> LoggingConfig:
        """載入日誌配置"""
        return LoggingConfig(
            log_file_path=os.environ.get("LOG_FILE_PATH", "app.log"),
            log_max_size_mb=self._get_env_int("LOG_MAX_SIZE_MB", 50),
            log_backup_count=self._get_env_int("LOG_BACKUP_COUNT", 5),
            enable_structured_logging=self._get_env_bool("ENABLE_STRUCTURED_LOGGING", True)
        )
    
    def _load_websocket_config(self) -> WebSocketConfig:
        """載入 WebSocket 配置"""
        return WebSocketConfig(
            websocket_timeout=self._get_env_int("WEBSOCKET_TIMEOUT", 300),
            max_websocket_connections=self._get_env_int("MAX_WEBSOCKET_CONNECTIONS", 100),
            websocket_heartbeat_interval=self._get_env_int("WEBSOCKET_HEARTBEAT_INTERVAL", 30)
        )
    
    def _load_development_config(self) -> DevelopmentConfig:
        """載入開發配置"""
        return DevelopmentConfig(
            development_mode=self._get_env_bool("DEVELOPMENT_MODE", False),
            enable_api_docs=self._get_env_bool("ENABLE_API_DOCS", True),
            enable_verbose_errors=self._get_env_bool("ENABLE_VERBOSE_ERRORS", False),
            test_mode=self._get_env_bool("TEST_MODE", False)
        )
    
    def _validate_config(self):
        """驗證配置的有效性"""
        # 驗證埠號範圍
        if not (1 <= self.server.port <= 65535):
            raise ValueError(f"無效的埠號: {self.server.port}")
        
        # 驗證 Whisper 裝置
        if self.whisper.device not in ["cuda", "cpu", "auto"]:
            logger.warning(f"未知的 Whisper 裝置: {self.whisper.device}，將使用 auto")
            self.whisper.device = "auto"
        
        # 驗證計算精度
        if self.whisper.compute_type not in ["float16", "int8", "float32"]:
            logger.warning(f"未知的計算精度: {self.whisper.compute_type}，將使用 float16")
            self.whisper.compute_type = "float16"
        
        # 驗證影片品質設定
        valid_qualities = ["best", "worst", "720p", "1080p", "480p", "360p"]
        if self.youtube.video_quality not in valid_qualities:
            logger.warning(f"未知的影片品質: {self.youtube.video_quality}，將使用 1080p")
            self.youtube.video_quality = "1080p"
        
        # 驗證維護時間格式
        try:
            hour, minute = map(int, self.maintenance.maintenance_time.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except (ValueError, AttributeError):
            logger.warning(f"無效的維護時間格式: {self.maintenance.maintenance_time}，將使用 02:00")
            self.maintenance.maintenance_time = "02:00"
    
    def _create_directories(self):
        """建立必要的目錄"""
        directories = [
            self.whisper.cache_dir,
            self.database.backup_dir,
            self.file_storage.tasks_root_dir,
            self.file_storage.temp_dir,
            Path(self.database.path).parent,
            Path(self.logging.log_file_path).parent
        ]
        
        for directory in directories:
            if directory:  # 避免空字串
                Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_ydl_opts_audio(self) -> dict:
        """獲取 yt-dlp 音訊下載選項"""
        return {
            'format': f'bestaudio[filesize<{self.youtube.max_video_size_mb}M]/best[filesize<{self.youtube.max_video_size_mb}M]',
            'outtmpl': '%(title)s.%(ext)s',
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': self.youtube.audio_quality,
            'socket_timeout': self.youtube.download_timeout,
            'retries': self.youtube.download_retry_count,
            'quiet': not self.development.development_mode,
            'no_warnings': not self.development.development_mode,
        }
    
    def get_ydl_opts_video(self) -> dict:
        """獲取 yt-dlp 影片下載選項"""
        format_selector = self._get_video_format_selector()
        
        return {
            'format': format_selector,
            'outtmpl': '%(title)s.%(ext)s',
            'socket_timeout': self.youtube.download_timeout,
            'retries': self.youtube.download_retry_count,
            'quiet': not self.development.development_mode,
            'no_warnings': not self.development.development_mode,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
    
    def _get_video_format_selector(self) -> str:
        """根據配置生成影片格式選擇器"""
        max_size = self.youtube.max_video_size_mb
        quality = self.youtube.video_quality
        
        if quality == "best":
            return f'best[filesize<{max_size}M]/best'
        elif quality == "worst":
            return f'worst[filesize<{max_size}M]/worst'
        elif quality.endswith('p'):
            height = quality[:-1]
            return f'best[height<={height}][filesize<{max_size}M]/best[filesize<{max_size}M]'
        else:
            return f'best[filesize<{max_size}M]/best'
    
    def to_dict(self) -> dict:
        """將配置轉換為字典格式"""
        return {
            'server': self.server.__dict__,
            'whisper': self.whisper.__dict__,
            'diarization': self.diarization.__dict__,
            'database': self.database.__dict__,
            'file_storage': self.file_storage.__dict__,
            'youtube': self.youtube.__dict__,
            'cache': self.cache.__dict__,
            'performance': self.performance.__dict__,
            'disk_space': self.disk_space.__dict__,
            'maintenance': self.maintenance.__dict__,
            'security': self.security.__dict__,
            'logging': self.logging.__dict__,
            'websocket': self.websocket.__dict__,
            'development': self.development.__dict__,
        }


# 全域配置實例
config = ConfigManager()


def get_config() -> ConfigManager:
    """獲取配置管理器實例"""
    return config