"""
效能最佳化模組

此模組提供下載最佳化、快取系統和效能監控功能，
用於提升 YouTube 影片處理和系統整體效能。

作者: AI Assistant
日期: 2025-01-06
"""

import asyncio
import logging
import time
import hashlib
import json
import os
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import aiofiles
import aiofiles.os

# 設定日誌
logger = logging.getLogger(__name__)


@dataclass
class DownloadStats:
    """下載統計資料"""
    total_downloads: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0
    total_bytes: int = 0
    total_time: float = 0.0
    average_speed: float = 0.0
    retry_count: int = 0
    
    def update_success(self, bytes_downloaded: int, download_time: float):
        """更新成功下載統計"""
        self.successful_downloads += 1
        self.total_downloads += 1
        self.total_bytes += bytes_downloaded
        self.total_time += download_time
        self.average_speed = self.total_bytes / self.total_time if self.total_time > 0 else 0
    
    def update_failure(self):
        """更新失敗下載統計"""
        self.failed_downloads += 1
        self.total_downloads += 1
    
    def update_retry(self):
        """更新重試統計"""
        self.retry_count += 1
    
    def get_success_rate(self) -> float:
        """獲取成功率"""
        return (self.successful_downloads / self.total_downloads * 100) if self.total_downloads > 0 else 0


@dataclass
class CacheEntry:
    """快取項目"""
    key: str
    data: Any
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """檢查是否過期"""
        return datetime.now() > self.expires_at
    
    def access(self):
        """記錄存取"""
        self.access_count += 1
        self.last_accessed = datetime.now()


class DownloadOptimizer:
    """下載最佳化器
    
    提供並發下載限制、重試機制和錯誤恢復功能。
    """
    
    def __init__(
        self, 
        max_concurrent_downloads: int = 3,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 300.0,
        max_file_size: int = 500 * 1024 * 1024  # 500MB
    ):
        """初始化下載最佳化器
        
        Args:
            max_concurrent_downloads: 最大並發下載數
            max_retries: 最大重試次數
            retry_delay: 重試延遲（秒）
            timeout: 下載超時時間（秒）
            max_file_size: 最大檔案大小（位元組）
        """
        self.max_concurrent_downloads = max_concurrent_downloads
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.max_file_size = max_file_size
        
        # 並發控制
        self.download_semaphore = asyncio.Semaphore(max_concurrent_downloads)
        self.active_downloads: Dict[str, asyncio.Task] = {}
        
        # 統計資料
        self.stats = DownloadStats()
        
        # 錯誤追蹤
        self.error_history: List[Dict[str, Any]] = []
        
        # 執行緒池
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_downloads)
        
        logger.info(f"下載最佳化器初始化完成 - 最大並發: {max_concurrent_downloads}, 最大重試: {max_retries}")
    
    async def optimized_download(
        self, 
        download_func: Callable,
        download_id: str,
        *args,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """最佳化的下載流程
        
        Args:
            download_func: 下載函數
            download_id: 下載唯一識別碼
            *args: 下載函數參數
            progress_callback: 進度回調函數
            **kwargs: 下載函數關鍵字參數
            
        Returns:
            Any: 下載結果
        """
        async with self.download_semaphore:
            return await self._download_with_retry(
                download_func, download_id, *args, 
                progress_callback=progress_callback, **kwargs
            )
    
    async def _download_with_retry(
        self, 
        download_func: Callable,
        download_id: str,
        *args,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """帶重試機制的下載
        
        Args:
            download_func: 下載函數
            download_id: 下載唯一識別碼
            *args: 下載函數參數
            progress_callback: 進度回調函數
            **kwargs: 下載函數關鍵字參數
            
        Returns:
            Any: 下載結果
        """
        last_exception = None
        start_time = time.time()
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"開始下載 {download_id} (嘗試 {attempt + 1}/{self.max_retries + 1})")
                
                # 建立下載任務
                download_task = asyncio.create_task(
                    self._execute_download(download_func, *args, **kwargs)
                )
                
                # 記錄活躍下載
                self.active_downloads[download_id] = download_task
                
                try:
                    # 等待下載完成或超時
                    result = await asyncio.wait_for(download_task, timeout=self.timeout)
                    
                    # 計算下載時間和統計
                    download_time = time.time() - start_time
                    
                    # 估算下載大小（如果結果是檔案路徑）
                    bytes_downloaded = 0
                    if isinstance(result, Path) and result.exists():
                        bytes_downloaded = result.stat().st_size
                    elif isinstance(result, tuple):
                        # 處理多個檔案的情況
                        for item in result:
                            if isinstance(item, Path) and item and item.exists():
                                bytes_downloaded += item.stat().st_size
                    
                    # 更新統計
                    self.stats.update_success(bytes_downloaded, download_time)
                    
                    logger.info(f"下載成功 {download_id} - 大小: {bytes_downloaded} 位元組, 時間: {download_time:.2f} 秒")
                    return result
                    
                except asyncio.TimeoutError:
                    logger.warning(f"下載超時 {download_id} (嘗試 {attempt + 1})")
                    download_task.cancel()
                    last_exception = TimeoutError(f"下載超時: {self.timeout} 秒")
                    
                finally:
                    # 清理活躍下載記錄
                    self.active_downloads.pop(download_id, None)
                
            except Exception as e:
                logger.error(f"下載失敗 {download_id} (嘗試 {attempt + 1}): {e}")
                last_exception = e
                
                # 記錄錯誤
                self._record_error(download_id, attempt + 1, e)
            
            # 如果不是最後一次嘗試，等待後重試
            if attempt < self.max_retries:
                self.stats.update_retry()
                retry_delay = self.retry_delay * (2 ** attempt)  # 指數退避
                logger.info(f"等待 {retry_delay:.2f} 秒後重試 {download_id}")
                await asyncio.sleep(retry_delay)
        
        # 所有重試都失敗
        self.stats.update_failure()
        logger.error(f"下載最終失敗 {download_id}: {last_exception}")
        
        if progress_callback:
            try:
                await progress_callback("error", f"下載失敗: {last_exception}")
            except Exception as e:
                logger.error(f"進度回調失敗: {e}")
        
        raise last_exception or Exception("下載失敗")
    
    async def _execute_download(self, download_func: Callable, *args, **kwargs) -> Any:
        """執行下載函數"""
        if asyncio.iscoroutinefunction(download_func):
            return await download_func(*args, **kwargs)
        else:
            # 在執行緒池中執行同步函數
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self.executor, download_func, *args, **kwargs)
    
    def _record_error(self, download_id: str, attempt: int, error: Exception):
        """記錄錯誤資訊"""
        error_info = {
            'download_id': download_id,
            'attempt': attempt,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat()
        }
        
        self.error_history.append(error_info)
        
        # 保持錯誤歷史記錄在合理範圍內
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-500:]
    
    async def cancel_download(self, download_id: str) -> bool:
        """取消指定的下載
        
        Args:
            download_id: 下載唯一識別碼
            
        Returns:
            bool: 是否成功取消
        """
        if download_id in self.active_downloads:
            task = self.active_downloads[download_id]
            task.cancel()
            self.active_downloads.pop(download_id, None)
            logger.info(f"已取消下載: {download_id}")
            return True
        return False
    
    async def cancel_all_downloads(self):
        """取消所有活躍的下載"""
        for download_id in list(self.active_downloads.keys()):
            await self.cancel_download(download_id)
        logger.info("已取消所有下載")
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取下載統計資料"""
        return {
            'stats': asdict(self.stats),
            'active_downloads': len(self.active_downloads),
            'recent_errors': self.error_history[-10:] if self.error_history else []
        }
    
    def reset_stats(self):
        """重置統計資料"""
        self.stats = DownloadStats()
        self.error_history.clear()
        logger.info("下載統計資料已重置")


class CacheManager:
    """快取管理器
    
    提供元資料快取、縮圖檔案快取和快取清理功能。
    """
    
    def __init__(
        self,
        cache_dir: Path,
        metadata_ttl: int = 86400,  # 24 小時
        thumbnail_ttl: int = 604800,  # 7 天
        max_cache_size: int = 1024 * 1024 * 1024,  # 1GB
        cleanup_interval: int = 3600  # 1 小時
    ):
        """初始化快取管理器
        
        Args:
            cache_dir: 快取目錄
            metadata_ttl: 元資料快取存活時間（秒）
            thumbnail_ttl: 縮圖快取存活時間（秒）
            max_cache_size: 最大快取大小（位元組）
            cleanup_interval: 清理間隔（秒）
        """
        self.cache_dir = Path(cache_dir)
        self.metadata_ttl = metadata_ttl
        self.thumbnail_ttl = thumbnail_ttl
        self.max_cache_size = max_cache_size
        self.cleanup_interval = cleanup_interval
        
        # 建立快取目錄
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir = self.cache_dir / "metadata"
        self.thumbnail_dir = self.cache_dir / "thumbnails"
        self.metadata_dir.mkdir(exist_ok=True)
        self.thumbnail_dir.mkdir(exist_ok=True)
        
        # 記憶體快取
        self.memory_cache: Dict[str, CacheEntry] = {}
        
        # 清理任務
        self.cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(f"快取管理器初始化完成 - 目錄: {cache_dir}")
    
    def _generate_cache_key(self, data: str) -> str:
        """生成快取鍵值"""
        return hashlib.md5(data.encode()).hexdigest()
    
    async def get_metadata_cache(self, url: str) -> Optional[Dict[str, Any]]:
        """獲取元資料快取
        
        Args:
            url: YouTube URL
            
        Returns:
            Optional[Dict[str, Any]]: 快取的元資料，如果不存在或過期則返回 None
        """
        cache_key = self._generate_cache_key(url)
        
        # 先檢查記憶體快取
        if cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]
            if not entry.is_expired():
                entry.access()
                logger.debug(f"記憶體快取命中: {url}")
                return entry.data
            else:
                # 過期的快取項目
                del self.memory_cache[cache_key]
        
        # 檢查檔案快取
        cache_file = self.metadata_dir / f"{cache_key}.json"
        try:
            if cache_file.exists():
                async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.loads(await f.read())
                
                expires_at = datetime.fromisoformat(cache_data['expires_at'])
                if datetime.now() < expires_at:
                    # 載入到記憶體快取
                    entry = CacheEntry(
                        key=cache_key,
                        data=cache_data['data'],
                        created_at=datetime.fromisoformat(cache_data['created_at']),
                        expires_at=expires_at
                    )
                    entry.access()
                    self.memory_cache[cache_key] = entry
                    
                    logger.debug(f"檔案快取命中: {url}")
                    return cache_data['data']
                else:
                    # 刪除過期的快取檔案
                    await aiofiles.os.remove(cache_file)
        
        except Exception as e:
            logger.error(f"讀取元資料快取失敗: {e}")
        
        return None
    
    async def set_metadata_cache(self, url: str, metadata: Dict[str, Any]):
        """設定元資料快取
        
        Args:
            url: YouTube URL
            metadata: 元資料
        """
        cache_key = self._generate_cache_key(url)
        created_at = datetime.now()
        expires_at = created_at + timedelta(seconds=self.metadata_ttl)
        
        # 儲存到記憶體快取
        entry = CacheEntry(
            key=cache_key,
            data=metadata,
            created_at=created_at,
            expires_at=expires_at
        )
        self.memory_cache[cache_key] = entry
        
        # 儲存到檔案快取
        cache_data = {
            'data': metadata,
            'created_at': created_at.isoformat(),
            'expires_at': expires_at.isoformat()
        }
        
        cache_file = self.metadata_dir / f"{cache_key}.json"
        try:
            async with aiofiles.open(cache_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(cache_data, ensure_ascii=False, indent=2))
            
            logger.debug(f"元資料快取已儲存: {url}")
        except Exception as e:
            logger.error(f"儲存元資料快取失敗: {e}")
    
    async def get_thumbnail_cache(self, url: str) -> Optional[Path]:
        """獲取縮圖快取
        
        Args:
            url: YouTube URL
            
        Returns:
            Optional[Path]: 快取的縮圖檔案路徑，如果不存在或過期則返回 None
        """
        cache_key = self._generate_cache_key(url)
        
        # 尋找快取的縮圖檔案
        for ext in ['.jpg', '.png', '.webp']:
            cache_file = self.thumbnail_dir / f"{cache_key}{ext}"
            if cache_file.exists():
                # 檢查檔案是否過期
                file_age = time.time() - cache_file.stat().st_mtime
                if file_age < self.thumbnail_ttl:
                    logger.debug(f"縮圖快取命中: {url}")
                    return cache_file
                else:
                    # 刪除過期的快取檔案
                    try:
                        await aiofiles.os.remove(cache_file)
                    except Exception as e:
                        logger.error(f"刪除過期縮圖快取失敗: {e}")
        
        return None
    
    async def set_thumbnail_cache(self, url: str, thumbnail_path: Path) -> Optional[Path]:
        """設定縮圖快取
        
        Args:
            url: YouTube URL
            thumbnail_path: 縮圖檔案路徑
            
        Returns:
            Optional[Path]: 快取的縮圖檔案路徑
        """
        if not thumbnail_path.exists():
            return None
        
        cache_key = self._generate_cache_key(url)
        cache_file = self.thumbnail_dir / f"{cache_key}{thumbnail_path.suffix}"
        
        try:
            # 複製縮圖到快取目錄
            async with aiofiles.open(thumbnail_path, 'rb') as src:
                async with aiofiles.open(cache_file, 'wb') as dst:
                    while True:
                        chunk = await src.read(8192)
                        if not chunk:
                            break
                        await dst.write(chunk)
            
            logger.debug(f"縮圖快取已儲存: {url}")
            return cache_file
            
        except Exception as e:
            logger.error(f"儲存縮圖快取失敗: {e}")
            return None
    
    async def cleanup_cache(self):
        """清理過期的快取"""
        logger.info("開始清理快取")
        
        # 清理記憶體快取
        expired_keys = [
            key for key, entry in self.memory_cache.items() 
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self.memory_cache[key]
        
        logger.info(f"清理了 {len(expired_keys)} 個過期的記憶體快取項目")
        
        # 清理檔案快取
        await self._cleanup_file_cache()
        
        # 檢查快取大小並清理
        await self._cleanup_by_size()
    
    async def _cleanup_file_cache(self):
        """清理過期的檔案快取"""
        current_time = time.time()
        
        # 清理元資料快取
        metadata_cleaned = 0
        for cache_file in self.metadata_dir.glob("*.json"):
            try:
                file_age = current_time - cache_file.stat().st_mtime
                if file_age > self.metadata_ttl:
                    await aiofiles.os.remove(cache_file)
                    metadata_cleaned += 1
            except Exception as e:
                logger.error(f"清理元資料快取檔案失敗 {cache_file}: {e}")
        
        # 清理縮圖快取
        thumbnail_cleaned = 0
        for cache_file in self.thumbnail_dir.glob("*"):
            try:
                file_age = current_time - cache_file.stat().st_mtime
                if file_age > self.thumbnail_ttl:
                    await aiofiles.os.remove(cache_file)
                    thumbnail_cleaned += 1
            except Exception as e:
                logger.error(f"清理縮圖快取檔案失敗 {cache_file}: {e}")
        
        logger.info(f"清理了 {metadata_cleaned} 個元資料快取檔案和 {thumbnail_cleaned} 個縮圖快取檔案")
    
    async def _cleanup_by_size(self):
        """根據大小清理快取"""
        try:
            # 計算快取目錄總大小
            total_size = 0
            cache_files = []
            
            for cache_file in self.cache_dir.rglob("*"):
                if cache_file.is_file():
                    size = cache_file.stat().st_size
                    mtime = cache_file.stat().st_mtime
                    total_size += size
                    cache_files.append((cache_file, size, mtime))
            
            if total_size > self.max_cache_size:
                logger.info(f"快取大小超過限制 ({total_size} > {self.max_cache_size})，開始清理")
                
                # 按修改時間排序（最舊的先刪除）
                cache_files.sort(key=lambda x: x[2])
                
                cleaned_size = 0
                cleaned_count = 0
                target_size = self.max_cache_size * 0.8  # 清理到 80% 的限制
                
                for cache_file, size, mtime in cache_files:
                    if total_size - cleaned_size <= target_size:
                        break
                    
                    try:
                        await aiofiles.os.remove(cache_file)
                        cleaned_size += size
                        cleaned_count += 1
                    except Exception as e:
                        logger.error(f"刪除快取檔案失敗 {cache_file}: {e}")
                
                logger.info(f"根據大小清理了 {cleaned_count} 個快取檔案，釋放了 {cleaned_size} 位元組")
        
        except Exception as e:
            logger.error(f"根據大小清理快取失敗: {e}")
    
    async def start_cleanup_task(self):
        """啟動定期清理任務"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.info("快取清理任務已啟動")
    
    async def stop_cleanup_task(self):
        """停止定期清理任務"""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("快取清理任務已停止")
    
    async def _periodic_cleanup(self):
        """定期清理任務"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_cache()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"定期清理任務失敗: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """獲取快取統計資料"""
        try:
            # 計算檔案快取統計
            metadata_files = list(self.metadata_dir.glob("*.json"))
            thumbnail_files = list(self.thumbnail_dir.glob("*"))
            
            total_size = 0
            for cache_file in self.cache_dir.rglob("*"):
                if cache_file.is_file():
                    total_size += cache_file.stat().st_size
            
            return {
                'memory_cache_entries': len(self.memory_cache),
                'metadata_cache_files': len(metadata_files),
                'thumbnail_cache_files': len(thumbnail_files),
                'total_cache_size': total_size,
                'max_cache_size': self.max_cache_size,
                'cache_usage_percent': (total_size / self.max_cache_size * 100) if self.max_cache_size > 0 else 0
            }
        except Exception as e:
            logger.error(f"獲取快取統計失敗: {e}")
            return {}
    
    async def clear_all_cache(self):
        """清空所有快取"""
        try:
            # 清空記憶體快取
            self.memory_cache.clear()
            
            # 刪除所有快取檔案
            import shutil
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self.metadata_dir.mkdir(exist_ok=True)
                self.thumbnail_dir.mkdir(exist_ok=True)
            
            logger.info("所有快取已清空")
        except Exception as e:
            logger.error(f"清空快取失敗: {e}")


# 全域實例
_download_optimizer = None
_cache_manager = None


def get_download_optimizer(**kwargs) -> DownloadOptimizer:
    """獲取下載最佳化器的全域實例"""
    global _download_optimizer
    if _download_optimizer is None:
        _download_optimizer = DownloadOptimizer(**kwargs)
    return _download_optimizer


def get_cache_manager(cache_dir: Optional[Path] = None, **kwargs) -> CacheManager:
    """獲取快取管理器的全域實例"""
    global _cache_manager
    if _cache_manager is None:
        if cache_dir is None:
            cache_dir = Path("temp") / "cache"
        _cache_manager = CacheManager(cache_dir, **kwargs)
    return _cache_manager


# 便利函數
async def optimized_download(
    download_func: Callable,
    download_id: str,
    *args,
    progress_callback: Optional[Callable] = None,
    **kwargs
) -> Any:
    """便利函數：執行最佳化下載
    
    Args:
        download_func: 下載函數
        download_id: 下載唯一識別碼
        *args: 下載函數參數
        progress_callback: 進度回調函數
        **kwargs: 下載函數關鍵字參數
        
    Returns:
        Any: 下載結果
    """
    optimizer = get_download_optimizer()
    return await optimizer.optimized_download(
        download_func, download_id, *args, 
        progress_callback=progress_callback, **kwargs
    )


async def get_cached_metadata(url: str) -> Optional[Dict[str, Any]]:
    """便利函數：獲取快取的元資料"""
    cache_manager = get_cache_manager()
    return await cache_manager.get_metadata_cache(url)


async def cache_metadata(url: str, metadata: Dict[str, Any]):
    """便利函數：快取元資料"""
    cache_manager = get_cache_manager()
    await cache_manager.set_metadata_cache(url, metadata)


async def get_cached_thumbnail(url: str) -> Optional[Path]:
    """便利函數：獲取快取的縮圖"""
    cache_manager = get_cache_manager()
    return await cache_manager.get_thumbnail_cache(url)


async def cache_thumbnail(url: str, thumbnail_path: Path) -> Optional[Path]:
    """便利函數：快取縮圖"""
    cache_manager = get_cache_manager()
    return await cache_manager.set_thumbnail_cache(url, thumbnail_path)



# ==================== 效能監控功能 ====================

class PerformanceMonitor:
    """效能監控器"""
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        self.start_time = time.time()
        
    def record_request(self, response_time: float, is_error: bool = False):
        """記錄請求"""
        self.request_count += 1
        self.total_response_time += response_time
        if is_error:
            self.error_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計資料"""
        uptime = time.time() - self.start_time
        avg_response_time = (
            self.total_response_time / self.request_count 
            if self.request_count > 0 else 0
        )
        
        # 獲取系統資源使用情況
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
        except Exception as e:
            logger.error(f"獲取系統資源失敗: {e}")
            cpu_percent = 0
            memory = None
            disk = None
        
        return {
            'uptime': uptime,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'error_rate': (self.error_count / self.request_count * 100) if self.request_count > 0 else 0,
            'avg_response_time': avg_response_time,
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent if memory else 0,
            'memory_available_mb': memory.available / (1024 * 1024) if memory else 0,
            'disk_percent': disk.percent if disk else 0,
            'disk_free_gb': disk.free / (1024 * 1024 * 1024) if disk else 0
        }


class QueryOptimizer:
    """查詢最佳化器"""
    
    def __init__(self, cache_ttl: int = 300):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.cache_ttl = cache_ttl
    
    async def get_cached_query(self, query_key: str) -> Optional[Any]:
        """獲取快取的查詢結果"""
        if query_key in self.cache:
            result, timestamp = self.cache[query_key]
            if time.time() - timestamp < self.cache_ttl:
                return result
            else:
                del self.cache[query_key]
        return None
    
    async def cache_query_result(self, query_key: str, result: Any):
        """快取查詢結果"""
        self.cache[query_key] = (result, time.time())
    
    async def clear_cache(self):
        """清空快取"""
        self.cache.clear()
    
    async def optimize_history_query(
        self, 
        query_func: Callable, 
        limit: int, 
        offset: int, 
        filters: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """最佳化歷史紀錄查詢
        
        Args:
            query_func: 查詢函數
            limit: 每頁數量
            offset: 偏移量
            filters: 篩選條件
            
        Returns:
            (任務列表, 總數) 的元組
        """
        # 生成快取鍵
        cache_key = self._generate_cache_key(limit, offset, filters)
        
        # 嘗試從快取獲取
        cached_result = await self.get_cached_query(cache_key)
        if cached_result is not None:
            logger.debug(f"從快取獲取查詢結果: {cache_key}")
            return cached_result
        
        # 執行查詢
        try:
            tasks, total = await query_func(limit=limit, offset=offset, **filters)
            
            # 快取結果
            result = (tasks, total)
            await self.cache_query_result(cache_key, result)
            
            logger.debug(f"查詢完成並快取: {cache_key}, 結果數: {len(tasks)}/{total}")
            return result
            
        except Exception as e:
            logger.error(f"查詢執行失敗: {e}")
            raise
    
    def _generate_cache_key(self, limit: int, offset: int, filters: Dict[str, Any]) -> str:
        """生成快取鍵"""
        # 將參數序列化為字串
        params = {
            'limit': limit,
            'offset': offset,
            'filters': filters
        }
        params_str = json.dumps(params, sort_keys=True)
        
        # 使用 MD5 生成短鍵
        cache_key = hashlib.md5(params_str.encode()).hexdigest()
        return f"history_query:{cache_key}"


class PaginationHelper:
    """分頁輔助工具"""
    
    @staticmethod
    def calculate_pagination(total: int, page: int, limit: int) -> Dict[str, Any]:
        """計算分頁資訊
        
        Args:
            total: 總記錄數
            page: 當前頁碼（從 1 開始）
            limit: 每頁數量
            
        Returns:
            包含分頁資訊的字典
        """
        # 計算總頁數
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        
        # 確保頁碼有效
        page = max(1, min(page, total_pages if total_pages > 0 else 1))
        
        # 計算偏移量
        offset = (page - 1) * limit
        
        # 計算是否有上一頁/下一頁
        has_prev = page > 1
        has_next = page < total_pages
        
        # 計算當前頁的記錄範圍
        start_index = offset + 1 if total > 0 else 0
        end_index = min(offset + limit, total)
        
        return {
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': total_pages,
            'offset': offset,
            'has_prev': has_prev,
            'has_next': has_next,
            'start_index': start_index,
            'end_index': end_index
        }
    
    @staticmethod
    def get_page_range(current_page: int, total_pages: int, max_pages: int = 5) -> List[int]:
        """獲取頁碼範圍（用於分頁導航）
        
        Args:
            current_page: 當前頁碼
            total_pages: 總頁數
            max_pages: 最多顯示的頁碼數量
            
        Returns:
            頁碼列表
        """
        if total_pages <= max_pages:
            return list(range(1, total_pages + 1))
        
        # 計算起始和結束頁碼
        half = max_pages // 2
        start = max(1, current_page - half)
        end = min(total_pages, start + max_pages - 1)
        
        # 調整起始頁碼
        if end - start < max_pages - 1:
            start = max(1, end - max_pages + 1)
        
        return list(range(start, end + 1))


class PerformanceMiddleware(BaseHTTPMiddleware):
    """效能監控中介軟體"""
    
    def __init__(self, app, monitor: Optional[PerformanceMonitor] = None):
        super().__init__(app)
        self.monitor = monitor or get_performance_monitor()
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        is_error = False
        
        try:
            response = await call_next(request)
            is_error = response.status_code >= 400
            return response
        except Exception as e:
            is_error = True
            raise
        finally:
            response_time = time.time() - start_time
            self.monitor.record_request(response_time, is_error)


# 全域實例
_performance_monitor = None
_query_optimizer = None


def get_performance_monitor() -> PerformanceMonitor:
    """獲取效能監控器的全域實例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def get_query_optimizer(**kwargs) -> QueryOptimizer:
    """獲取查詢最佳化器的全域實例"""
    global _query_optimizer
    if _query_optimizer is None:
        _query_optimizer = QueryOptimizer(**kwargs)
    return _query_optimizer


def get_cache() -> CacheManager:
    """獲取快取管理器（別名函數）"""
    return get_cache_manager()


async def cache_cleanup_task():
    """快取清理任務"""
    cache_manager = get_cache_manager()
    await cache_manager.start_cleanup_task()


async def generate_performance_report() -> Dict[str, Any]:
    """生成效能報告"""
    monitor = get_performance_monitor()
    cache_manager = get_cache_manager()
    download_optimizer = get_download_optimizer()
    
    return {
        'timestamp': datetime.now().isoformat(),
        'performance': monitor.get_stats(),
        'cache': cache_manager.get_cache_stats(),
        'downloads': download_optimizer.get_stats()
    }
