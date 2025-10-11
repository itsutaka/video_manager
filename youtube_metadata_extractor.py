"""
YouTube 元資料提取模組

此模組提供 YouTube 影片元資料提取功能，使用 yt-dlp 獲取影片資訊，
並實作標題清理功能以處理特殊字元。整合快取系統以提升效能。

作者: AI Assistant
日期: 2025-01-06
"""

import asyncio
import logging
import re
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from pathlib import Path

import yt_dlp

# 匯入效能最佳化模組
try:
    from performance_optimizer import get_cache_manager, CacheManager
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    logger.warning("效能最佳化模組不可用，將不使用快取功能")

# 設定日誌
logger = logging.getLogger(__name__)


@dataclass
class YouTubeMetadata:
    """YouTube 影片元資料資料類別"""
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


class YouTubeMetadataExtractor:
    """YouTube 元資料提取器
    
    使用 yt-dlp 獲取 YouTube 影片的元資料資訊，包括標題、描述、
    上傳者、時長等資訊，並提供標題清理功能。
    """
    
    def __init__(self):
        """初始化 YouTube 元資料提取器"""
        self.ydl_opts_metadata = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writeinfojson': False,
            'skip_download': True,  # 只提取元資料，不下載檔案
            'ignoreerrors': True,   # 忽略錯誤繼續處理
        }
        
        # 特殊字元清理規則
        self.title_cleanup_patterns = [
            # 移除檔案系統不支援的字元
            (r'[<>:"/\\|?*]', '_'),
            # 移除控制字元
            (r'[\x00-\x1f\x7f-\x9f]', ''),
            # 移除多餘的空白字元
            (r'\s+', ' '),
            # 移除開頭和結尾的空白
            (r'^\s+|\s+$', ''),
        ]
    
    async def extract_metadata(self, youtube_url: str) -> YouTubeMetadata:
        """提取 YouTube 影片元資料
        
        Args:
            youtube_url: YouTube 影片 URL
            
        Returns:
            YouTubeMetadata: 影片元資料物件
            
        Raises:
            Exception: 當元資料提取失敗時
        """
        try:
            logger.info(f"開始提取 YouTube 元資料: {youtube_url}")
            
            # 嘗試從快取獲取元資料
            if CACHE_AVAILABLE:
                cache_manager = get_cache_manager()
                cached_metadata = await cache_manager.get_metadata_cache(youtube_url)
                if cached_metadata:
                    logger.info(f"從快取獲取元資料: {cached_metadata.get('title', '未知')}")
                    return YouTubeMetadata(**cached_metadata)
            
            # 在執行緒池中執行 yt-dlp 操作以避免阻塞
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, 
                self._extract_info_sync, 
                youtube_url
            )
            
            if not info:
                raise Exception("無法獲取影片資訊")
            
            # 建立元資料物件
            metadata = YouTubeMetadata.from_ydl_info(info)
            
            # 清理標題
            if metadata.title:
                metadata.title = self.sanitize_title(metadata.title)
            
            # 快取元資料
            if CACHE_AVAILABLE:
                cache_manager = get_cache_manager()
                await cache_manager.set_metadata_cache(youtube_url, metadata.to_dict())
            
            logger.info(f"成功提取元資料: {metadata.title}")
            return metadata
            
        except Exception as e:
            logger.error(f"提取 YouTube 元資料失敗: {e}")
            raise Exception(f"元資料提取失敗: {str(e)}")
    
    def _extract_info_sync(self, youtube_url: str) -> Optional[Dict[str, Any]]:
        """同步提取影片資訊（在執行緒池中執行）"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts_metadata) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                return info
        except Exception as e:
            logger.error(f"yt-dlp 提取資訊失敗: {e}")
            return None
    
    async def get_video_info(self, youtube_url: str) -> Dict[str, Any]:
        """獲取影片基本資訊
        
        Args:
            youtube_url: YouTube 影片 URL
            
        Returns:
            Dict[str, Any]: 包含基本影片資訊的字典
        """
        try:
            metadata = await self.extract_metadata(youtube_url)
            
            return {
                'title': metadata.title,
                'uploader': metadata.uploader,
                'duration': metadata.duration,
                'view_count': metadata.view_count,
                'upload_date': metadata.upload_date,
                'thumbnail_url': metadata.thumbnail_url,
                'webpage_url': metadata.webpage_url
            }
            
        except Exception as e:
            logger.error(f"獲取影片基本資訊失敗: {e}")
            return {
                'title': '無法獲取標題',
                'uploader': None,
                'duration': None,
                'view_count': None,
                'upload_date': None,
                'thumbnail_url': None,
                'webpage_url': youtube_url
            }
    
    def sanitize_title(self, title: str) -> str:
        """清理影片標題，移除不適合檔案名稱的字元
        
        Args:
            title: 原始標題
            
        Returns:
            str: 清理後的標題
        """
        if not title:
            return "未知標題"
        
        sanitized = title
        
        # 應用清理規則
        for pattern, replacement in self.title_cleanup_patterns:
            sanitized = re.sub(pattern, replacement, sanitized)
        
        # 限制標題長度（避免檔案名稱過長）
        max_length = 100
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip()
        
        # 確保標題不為空
        if not sanitized.strip():
            sanitized = "未知標題"
        
        return sanitized.strip()
    
    def validate_youtube_url(self, url: str) -> bool:
        """驗證 YouTube URL 格式
        
        Args:
            url: 要驗證的 URL
            
        Returns:
            bool: URL 是否有效
        """
        youtube_patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://youtu\.be/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/embed/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/v/[\w-]+',
            r'https?://(?:m\.)?youtube\.com/watch\?v=[\w-]+'
        ]
        
        return any(re.match(pattern, url) for pattern in youtube_patterns)
    
    async def extract_video_id(self, youtube_url: str) -> Optional[str]:
        """從 YouTube URL 提取影片 ID
        
        Args:
            youtube_url: YouTube 影片 URL
            
        Returns:
            Optional[str]: 影片 ID，如果提取失敗則返回 None
        """
        try:
            # 使用正規表達式提取影片 ID
            patterns = [
                r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([^&\n?#]+)',
                r'youtube\.com/watch\?.*v=([^&\n?#]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, youtube_url)
                if match:
                    return match.group(1)
            
            # 如果正規表達式失敗，嘗試使用 yt-dlp 提取
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                self._extract_info_sync,
                youtube_url
            )
            
            if info and 'id' in info:
                return info['id']
            
            return None
            
        except Exception as e:
            logger.error(f"提取影片 ID 失敗: {e}")
            return None


# 全域實例
_metadata_extractor = None


def get_youtube_metadata_extractor() -> YouTubeMetadataExtractor:
    """獲取 YouTube 元資料提取器的全域實例"""
    global _metadata_extractor
    if _metadata_extractor is None:
        _metadata_extractor = YouTubeMetadataExtractor()
    return _metadata_extractor


# 便利函數
async def extract_youtube_metadata(youtube_url: str) -> YouTubeMetadata:
    """便利函數：提取 YouTube 影片元資料
    
    Args:
        youtube_url: YouTube 影片 URL
        
    Returns:
        YouTubeMetadata: 影片元資料物件
    """
    extractor = get_youtube_metadata_extractor()
    return await extractor.extract_metadata(youtube_url)


async def get_youtube_video_info(youtube_url: str) -> Dict[str, Any]:
    """便利函數：獲取 YouTube 影片基本資訊
    
    Args:
        youtube_url: YouTube 影片 URL
        
    Returns:
        Dict[str, Any]: 影片基本資訊字典
    """
    extractor = get_youtube_metadata_extractor()
    return await extractor.get_video_info(youtube_url)


def sanitize_youtube_title(title: str) -> str:
    """便利函數：清理 YouTube 影片標題
    
    Args:
        title: 原始標題
        
    Returns:
        str: 清理後的標題
    """
    extractor = get_youtube_metadata_extractor()
    return extractor.sanitize_title(title)