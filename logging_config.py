"""
日誌配置模組
為 YouTube 處理和系統監控提供結構化日誌
"""

import logging
import logging.handlers
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from config import get_config


@dataclass
class LogEvent:
    """結構化日誌事件"""
    timestamp: str
    level: str
    module: str
    event_type: str
    message: str
    task_id: Optional[str] = None
    user_id: Optional[str] = None
    youtube_url: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {k: v for k, v in asdict(self).items() if v is not None}


class StructuredFormatter(logging.Formatter):
    """結構化日誌格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        # 基本日誌資訊
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'module': record.name,
            'message': record.getMessage(),
            'line': record.lineno,
            'function': record.funcName
        }
        
        # 添加額外的結構化資料
        if hasattr(record, 'event_type'):
            log_data['event_type'] = record.event_type
        if hasattr(record, 'task_id'):
            log_data['task_id'] = record.task_id
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'youtube_url'):
            log_data['youtube_url'] = record.youtube_url
        if hasattr(record, 'file_size'):
            log_data['file_size'] = record.file_size
        if hasattr(record, 'duration'):
            log_data['duration'] = record.duration
        if hasattr(record, 'error_code'):
            log_data['error_code'] = record.error_code
        if hasattr(record, 'metadata'):
            log_data['metadata'] = record.metadata
        
        # 異常資訊
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))


class YouTubeLogger:
    """YouTube 處理專用日誌器"""
    
    def __init__(self, name: str = "youtube_processor"):
        self.logger = logging.getLogger(name)
        self.config = get_config()
        
        if not self.logger.handlers:
            self._setup_logger()
    
    def _setup_logger(self):
        """設定日誌器"""
        self.logger.setLevel(logging.DEBUG)
        
        # 檔案處理器 - 結構化日誌
        if self.config.logging.enable_structured_logging:
            file_handler = logging.handlers.RotatingFileHandler(
                filename=f"logs/youtube_{datetime.now().strftime('%Y%m%d')}.log",
                maxBytes=self.config.logging.log_max_size_mb * 1024 * 1024,
                backupCount=self.config.logging.log_backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(StructuredFormatter())
            file_handler.setLevel(logging.INFO)
            self.logger.addHandler(file_handler)
        
        # 控制台處理器 - 人類可讀格式
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.DEBUG if self.config.development.development_mode else logging.INFO)
        self.logger.addHandler(console_handler)
    
    def log_download_start(self, task_id: str, youtube_url: str, video_title: str = None):
        """記錄下載開始"""
        self.logger.info(
            f"開始下載 YouTube 影片: {video_title or youtube_url}",
            extra={
                'event_type': 'youtube_download_start',
                'task_id': task_id,
                'youtube_url': youtube_url,
                'metadata': {'video_title': video_title}
            }
        )
    
    def log_download_progress(self, task_id: str, youtube_url: str, progress: float, speed: str = None):
        """記錄下載進度"""
        self.logger.debug(
            f"下載進度: {progress:.1f}%",
            extra={
                'event_type': 'youtube_download_progress',
                'task_id': task_id,
                'youtube_url': youtube_url,
                'metadata': {'progress': progress, 'speed': speed}
            }
        )
    
    def log_download_complete(self, task_id: str, youtube_url: str, file_path: str, file_size: int, duration: float):
        """記錄下載完成"""
        self.logger.info(
            f"YouTube 影片下載完成: {file_path}",
            extra={
                'event_type': 'youtube_download_complete',
                'task_id': task_id,
                'youtube_url': youtube_url,
                'file_size': file_size,
                'duration': duration,
                'metadata': {'file_path': file_path}
            }
        )
    
    def log_download_error(self, task_id: str, youtube_url: str, error: Exception, error_code: str = None):
        """記錄下載錯誤"""
        self.logger.error(
            f"YouTube 影片下載失敗: {str(error)}",
            extra={
                'event_type': 'youtube_download_error',
                'task_id': task_id,
                'youtube_url': youtube_url,
                'error_code': error_code or 'DOWNLOAD_FAILED',
                'metadata': {'error_type': type(error).__name__}
            },
            exc_info=True
        )
    
    def log_metadata_extraction(self, task_id: str, youtube_url: str, metadata: Dict[str, Any], duration: float):
        """記錄元資料提取"""
        self.logger.info(
            f"YouTube 元資料提取完成: {metadata.get('title', 'Unknown')}",
            extra={
                'event_type': 'youtube_metadata_extracted',
                'task_id': task_id,
                'youtube_url': youtube_url,
                'duration': duration,
                'metadata': {
                    'title': metadata.get('title'),
                    'uploader': metadata.get('uploader'),
                    'duration': metadata.get('duration'),
                    'view_count': metadata.get('view_count')
                }
            }
        )
    
    def log_metadata_error(self, task_id: str, youtube_url: str, error: Exception, error_code: str = None):
        """記錄元資料提取錯誤"""
        self.logger.error(
            f"YouTube 元資料提取失敗: {str(error)}",
            extra={
                'event_type': 'youtube_metadata_error',
                'task_id': task_id,
                'youtube_url': youtube_url,
                'error_code': error_code or 'METADATA_EXTRACTION_FAILED',
                'metadata': {'error_type': type(error).__name__}
            },
            exc_info=True
        )
    
    def log_thumbnail_download(self, task_id: str, youtube_url: str, thumbnail_path: str, file_size: int):
        """記錄縮圖下載"""
        self.logger.info(
            f"YouTube 縮圖下載完成: {thumbnail_path}",
            extra={
                'event_type': 'youtube_thumbnail_downloaded',
                'task_id': task_id,
                'youtube_url': youtube_url,
                'file_size': file_size,
                'metadata': {'thumbnail_path': thumbnail_path}
            }
        )
    
    def log_processing_complete(self, task_id: str, youtube_url: str, total_duration: float, files_created: list):
        """記錄完整處理完成"""
        self.logger.info(
            f"YouTube 處理完成，總耗時: {total_duration:.2f}秒",
            extra={
                'event_type': 'youtube_processing_complete',
                'task_id': task_id,
                'youtube_url': youtube_url,
                'duration': total_duration,
                'metadata': {
                    'files_created': files_created,
                    'file_count': len(files_created)
                }
            }
        )


class PerformanceLogger:
    """效能監控日誌器"""
    
    def __init__(self, name: str = "performance_monitor"):
        self.logger = logging.getLogger(name)
        self.config = get_config()
        
        if not self.logger.handlers:
            self._setup_logger()
    
    def _setup_logger(self):
        """設定日誌器"""
        self.logger.setLevel(logging.INFO)
        
        # 效能日誌檔案
        file_handler = logging.handlers.RotatingFileHandler(
            filename=f"logs/performance_{datetime.now().strftime('%Y%m%d')}.log",
            maxBytes=self.config.logging.log_max_size_mb * 1024 * 1024,
            backupCount=self.config.logging.log_backup_count,
            encoding='utf-8'
        )
        
        if self.config.logging.enable_structured_logging:
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            ))
        
        self.logger.addHandler(file_handler)
    
    def log_system_metrics(self, cpu_percent: float, memory_percent: float, disk_percent: float, 
                          gpu_memory_percent: float = None):
        """記錄系統指標"""
        self.logger.info(
            f"系統指標 - CPU: {cpu_percent:.1f}%, 記憶體: {memory_percent:.1f}%, 磁碟: {disk_percent:.1f}%",
            extra={
                'event_type': 'system_metrics',
                'metadata': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory_percent,
                    'disk_percent': disk_percent,
                    'gpu_memory_percent': gpu_memory_percent
                }
            }
        )
    
    def log_api_performance(self, endpoint: str, method: str, duration: float, status_code: int, 
                           task_id: str = None):
        """記錄 API 效能"""
        self.logger.info(
            f"API 請求 - {method} {endpoint} - {duration:.3f}s - {status_code}",
            extra={
                'event_type': 'api_performance',
                'task_id': task_id,
                'metadata': {
                    'endpoint': endpoint,
                    'method': method,
                    'duration': duration,
                    'status_code': status_code
                }
            }
        )
    
    def log_model_performance(self, model_name: str, operation: str, duration: float, 
                             input_size: int = None, task_id: str = None):
        """記錄模型效能"""
        self.logger.info(
            f"模型操作 - {model_name} {operation} - {duration:.3f}s",
            extra={
                'event_type': 'model_performance',
                'task_id': task_id,
                'metadata': {
                    'model_name': model_name,
                    'operation': operation,
                    'duration': duration,
                    'input_size': input_size
                }
            }
        )
    
    def log_cache_performance(self, cache_type: str, operation: str, hit: bool, duration: float = None):
        """記錄快取效能"""
        self.logger.debug(
            f"快取操作 - {cache_type} {operation} - {'命中' if hit else '未命中'}",
            extra={
                'event_type': 'cache_performance',
                'metadata': {
                    'cache_type': cache_type,
                    'operation': operation,
                    'hit': hit,
                    'duration': duration
                }
            }
        )
    
    def log_database_performance(self, operation: str, table: str, duration: float, rows_affected: int = None):
        """記錄資料庫效能"""
        self.logger.debug(
            f"資料庫操作 - {operation} {table} - {duration:.3f}s",
            extra={
                'event_type': 'database_performance',
                'metadata': {
                    'operation': operation,
                    'table': table,
                    'duration': duration,
                    'rows_affected': rows_affected
                }
            }
        )


class ErrorTracker:
    """錯誤追蹤器"""
    
    def __init__(self, name: str = "error_tracker"):
        self.logger = logging.getLogger(name)
        self.config = get_config()
        
        if not self.logger.handlers:
            self._setup_logger()
    
    def _setup_logger(self):
        """設定日誌器"""
        self.logger.setLevel(logging.WARNING)
        
        # 錯誤日誌檔案
        file_handler = logging.handlers.RotatingFileHandler(
            filename=f"logs/errors_{datetime.now().strftime('%Y%m%d')}.log",
            maxBytes=self.config.logging.log_max_size_mb * 1024 * 1024,
            backupCount=self.config.logging.log_backup_count,
            encoding='utf-8'
        )
        
        if self.config.logging.enable_structured_logging:
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s'
            ))
        
        self.logger.addHandler(file_handler)
    
    def track_error(self, error: Exception, context: Dict[str, Any] = None, 
                   task_id: str = None, error_code: str = None):
        """追蹤錯誤"""
        self.logger.error(
            f"錯誤發生: {str(error)}",
            extra={
                'event_type': 'error_occurred',
                'task_id': task_id,
                'error_code': error_code or 'UNKNOWN_ERROR',
                'metadata': {
                    'error_type': type(error).__name__,
                    'context': context or {}
                }
            },
            exc_info=True
        )
    
    def track_warning(self, message: str, context: Dict[str, Any] = None, 
                     task_id: str = None, warning_code: str = None):
        """追蹤警告"""
        self.logger.warning(
            message,
            extra={
                'event_type': 'warning_occurred',
                'task_id': task_id,
                'error_code': warning_code or 'WARNING',
                'metadata': context or {}
            }
        )


def setup_logging():
    """設定全域日誌配置"""
    config = get_config()
    
    # 建立日誌目錄
    Path("logs").mkdir(exist_ok=True)
    
    # 設定根日誌器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if config.development.development_mode else logging.INFO)
    
    # 避免重複添加處理器
    if not root_logger.handlers:
        # 主應用程式日誌
        main_handler = logging.handlers.RotatingFileHandler(
            filename=config.logging.log_file_path,
            maxBytes=config.logging.log_max_size_mb * 1024 * 1024,
            backupCount=config.logging.log_backup_count,
            encoding='utf-8'
        )
        
        if config.logging.enable_structured_logging:
            main_handler.setFormatter(StructuredFormatter())
        else:
            main_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        
        root_logger.addHandler(main_handler)
        
        # 控制台輸出
        if config.development.development_mode:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            root_logger.addHandler(console_handler)
    
    # 設定第三方庫的日誌級別
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('yt_dlp').setLevel(logging.WARNING)
    logging.getLogger('faster_whisper').setLevel(logging.INFO)
    logging.getLogger('whisperx').setLevel(logging.INFO)


# 全域日誌器實例
youtube_logger = YouTubeLogger()
performance_logger = PerformanceLogger()
error_tracker = ErrorTracker()


def get_youtube_logger() -> YouTubeLogger:
    """獲取 YouTube 日誌器"""
    return youtube_logger


def get_performance_logger() -> PerformanceLogger:
    """獲取效能日誌器"""
    return performance_logger


def get_error_tracker() -> ErrorTracker:
    """獲取錯誤追蹤器"""
    return error_tracker