"""
YouTube 下載管理模組

此模組提供 YouTube 影片和音訊下載功能，支援並行下載、縮圖下載，
以及最佳影片格式和品質選項設定。整合效能最佳化和快取系統。

作者: AI Assistant
日期: 2025-01-06
"""

import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
import aiofiles
from pydub import AudioSegment

# 匯入效能最佳化模組
try:
    from performance_optimizer import get_download_optimizer, get_cache_manager
    OPTIMIZATION_AVAILABLE = True
except ImportError:
    OPTIMIZATION_AVAILABLE = False
    logger.warning("效能最佳化模組不可用，將使用基本下載功能")

# 設定日誌
logger = logging.getLogger(__name__)


class YouTubeDownloadManager:
    """YouTube 下載管理器
    
    提供 YouTube 影片和音訊的下載功能，支援並行下載、
    縮圖下載以及最佳格式選擇。
    """
    
    def __init__(self, base_path: Path, max_concurrent_downloads: int = 3):
        """初始化 YouTube 下載管理器

        Args:
            base_path: 基礎下載路徑
            max_concurrent_downloads: 最大並行下載數量
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # 並行下載控制
        self.max_concurrent_downloads = max_concurrent_downloads
        self.download_semaphore = asyncio.Semaphore(max_concurrent_downloads)
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_downloads)

        # 使用最佳化方法初始化下載選項
        self.audio_opts = self.get_optimal_audio_format()
        self.video_opts = self.get_optimal_video_format()

        # 縮圖下載選項
        self.thumbnail_opts = {
            'writethumbnail': True,
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
        }
    
    async def download_audio_and_video(
        self, 
        youtube_url: str, 
        task_folder: Path,
        progress_callback: Optional[callable] = None
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """並行下載音訊和影片檔案
        
        Args:
            youtube_url: YouTube 影片 URL
            task_folder: 任務資料夾路徑
            progress_callback: 進度回調函數
            
        Returns:
            Tuple[Optional[Path], Optional[Path]]: (音訊檔案路徑, 影片檔案路徑)
        """
        try:
            logger.info(f"開始並行下載音訊和影片: {youtube_url}")
            
            # 確保任務資料夾存在
            task_folder.mkdir(parents=True, exist_ok=True)
            
            # 建立臨時下載目錄
            temp_dir = task_folder / "temp_download"
            temp_dir.mkdir(exist_ok=True)
            
            # 使用最佳化下載（如果可用）
            if OPTIMIZATION_AVAILABLE:
                optimizer = get_download_optimizer()
                
                # 並行執行音訊和影片下載（使用最佳化器）
                audio_download_id = f"audio_{uuid.uuid4().hex[:8]}"
                video_download_id = f"video_{uuid.uuid4().hex[:8]}"
                
                audio_task = asyncio.create_task(
                    optimizer.optimized_download(
                        self._download_audio_async,
                        audio_download_id,
                        youtube_url, temp_dir, progress_callback
                    )
                )
                video_task = asyncio.create_task(
                    optimizer.optimized_download(
                        self._download_video_async,
                        video_download_id,
                        youtube_url, temp_dir, progress_callback
                    )
                )
            else:
                # 並行執行音訊和影片下載（基本版本）
                audio_task = asyncio.create_task(
                    self._download_audio_async(youtube_url, temp_dir, progress_callback)
                )
                video_task = asyncio.create_task(
                    self._download_video_async(youtube_url, temp_dir, progress_callback)
                )
            
            # 等待兩個下載任務完成
            audio_path, video_path = await asyncio.gather(
                audio_task, video_task, return_exceptions=True
            )
            
            # 處理下載結果
            final_audio_path = None
            final_video_path = None
            
            if not isinstance(audio_path, Exception) and audio_path:
                # 移動音訊檔案到最終位置
                final_audio_path = task_folder / f"audio_{uuid.uuid4().hex[:8]}.mp3"
                await self._move_file_async(audio_path, final_audio_path)
                logger.info(f"音訊下載完成: {final_audio_path}")
            else:
                logger.error(f"音訊下載失敗: {audio_path}")
            
            if not isinstance(video_path, Exception) and video_path:
                # 移動影片檔案到最終位置
                video_ext = video_path.suffix or '.mp4'
                final_video_path = task_folder / f"video_{uuid.uuid4().hex[:8]}{video_ext}"
                await self._move_file_async(video_path, final_video_path)
                logger.info(f"影片下載完成: {final_video_path}")
            else:
                logger.error(f"影片下載失敗: {video_path}")
            
            # 清理臨時目錄
            await self._cleanup_temp_dir(temp_dir)
            
            return final_audio_path, final_video_path
            
        except Exception as e:
            logger.error(f"並行下載失敗: {e}")
            return None, None
    
    async def download_audio_only(
        self, 
        youtube_url: str, 
        output_path: Path,
        progress_callback: Optional[callable] = None
    ) -> Optional[Path]:
        """僅下載音訊檔案
        
        Args:
            youtube_url: YouTube 影片 URL
            output_path: 輸出檔案路徑
            progress_callback: 進度回調函數
            
        Returns:
            Optional[Path]: 音訊檔案路徑，失敗時返回 None
        """
        try:
            async with self.download_semaphore:
                return await self._download_audio_async(
                    youtube_url, 
                    output_path.parent, 
                    progress_callback
                )
        except Exception as e:
            logger.error(f"音訊下載失敗: {e}")
            return None
    
    async def download_video_only(
        self, 
        youtube_url: str, 
        output_path: Path,
        progress_callback: Optional[callable] = None
    ) -> Optional[Path]:
        """僅下載影片檔案
        
        Args:
            youtube_url: YouTube 影片 URL
            output_path: 輸出檔案路徑
            progress_callback: 進度回調函數
            
        Returns:
            Optional[Path]: 影片檔案路徑，失敗時返回 None
        """
        try:
            async with self.download_semaphore:
                return await self._download_video_async(
                    youtube_url, 
                    output_path.parent, 
                    progress_callback
                )
        except Exception as e:
            logger.error(f"影片下載失敗: {e}")
            return None
    
    async def download_thumbnail(
        self, 
        youtube_url: str, 
        output_path: Path
    ) -> Optional[Path]:
        """下載影片縮圖
        
        Args:
            youtube_url: YouTube 影片 URL
            output_path: 輸出檔案路徑
            
        Returns:
            Optional[Path]: 縮圖檔案路徑，失敗時返回 None
        """
        try:
            logger.info(f"開始下載縮圖: {youtube_url}")
            
            # 嘗試從快取獲取縮圖
            if OPTIMIZATION_AVAILABLE:
                cache_manager = get_cache_manager()
                cached_thumbnail = await cache_manager.get_thumbnail_cache(youtube_url)
                if cached_thumbnail and cached_thumbnail.exists():
                    logger.info(f"從快取獲取縮圖: {youtube_url}")
                    # 複製快取的縮圖到目標位置
                    final_thumbnail_path = output_path.with_suffix(cached_thumbnail.suffix)
                    await self._move_file_async(cached_thumbnail, final_thumbnail_path)
                    return final_thumbnail_path
            
            # 確保輸出目錄存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 建立臨時下載目錄
            temp_dir = output_path.parent / f"temp_thumb_{uuid.uuid4().hex[:8]}"
            temp_dir.mkdir(exist_ok=True)
            
            # 設定縮圖下載選項
            thumbnail_opts = self.thumbnail_opts.copy()
            thumbnail_opts['outtmpl'] = str(temp_dir / '%(title)s.%(ext)s')
            
            # 使用最佳化下載（如果可用）
            if OPTIMIZATION_AVAILABLE:
                optimizer = get_download_optimizer()
                download_id = f"thumbnail_{uuid.uuid4().hex[:8]}"
                await optimizer.optimized_download(
                    self._download_thumbnail_sync,
                    download_id,
                    youtube_url,
                    thumbnail_opts
                )
            else:
                # 在執行緒池中執行下載
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self.executor,
                    self._download_thumbnail_sync,
                    youtube_url,
                    thumbnail_opts
                )
            
            # 尋找下載的縮圖檔案
            thumbnail_files = list(temp_dir.glob('*.jpg')) + list(temp_dir.glob('*.png')) + list(temp_dir.glob('*.webp'))
            
            if thumbnail_files:
                # 移動縮圖到最終位置
                thumbnail_file = thumbnail_files[0]
                final_thumbnail_path = output_path.with_suffix(thumbnail_file.suffix)
                await self._move_file_async(thumbnail_file, final_thumbnail_path)
                
                # 快取縮圖
                if OPTIMIZATION_AVAILABLE:
                    cache_manager = get_cache_manager()
                    await cache_manager.set_thumbnail_cache(youtube_url, final_thumbnail_path)
                
                # 清理臨時目錄
                await self._cleanup_temp_dir(temp_dir)
                
                logger.info(f"縮圖下載完成: {final_thumbnail_path}")
                return final_thumbnail_path
            else:
                logger.warning("未找到下載的縮圖檔案")
                await self._cleanup_temp_dir(temp_dir)
                return None
                
        except Exception as e:
            logger.error(f"縮圖下載失敗: {e}")
            return None
    
    def get_optimal_video_format(self) -> Dict[str, Any]:
        """獲取最佳影片格式設定

        使用多層回退策略以確保下載成功率：
        1. 首選：1080p以下 mp4視訊 + m4a音訊（最佳品質）
        2. 次選：1080p以下完整 mp4 檔案
        3. 第三：任何1080p以下視訊 + 最佳音訊（合併）
        4. 第四：任何1080p以下完整檔案
        5. 回退：最佳可用格式

        Returns:
            Dict[str, Any]: 最佳影片格式選項
        """
        return {
            'format': 'bv*[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4][height<=1080]/bv*[height<=1080]+ba/b[height<=1080]/best',
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
        }
    
    def get_optimal_audio_format(self) -> Dict[str, Any]:
        """獲取最佳音訊格式設定

        使用多層回退策略以確保下載成功率：
        1. 首選：m4a 格式的最佳音訊
        2. 次選：mp3 格式的最佳音訊
        3. 第三：任何格式的最佳音訊
        4. 回退：最佳可用音訊

        Returns:
            Dict[str, Any]: 最佳音訊格式選項
        """
        return {
            'format': 'ba[ext=m4a]/ba[ext=mp3]/ba/bestaudio',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
        }
    
    async def _download_audio_async(
        self, 
        youtube_url: str, 
        output_dir: Path, 
        progress_callback: Optional[callable] = None
    ) -> Optional[Path]:
        """異步下載音訊檔案"""
        try:
            # 建立唯一的輸出檔案名稱
            output_template = output_dir / f"audio_{uuid.uuid4().hex[:8]}.%(ext)s"
            
            # 設定下載選項
            audio_opts = self.audio_opts.copy()
            audio_opts['outtmpl'] = str(output_template)
            
            if progress_callback:
                audio_opts['progress_hooks'] = [
                    lambda d: self._progress_hook(d, progress_callback, "audio")
                ]
            
            # 在執行緒池中執行下載
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self._download_sync,
                youtube_url,
                audio_opts
            )
            
            # 尋找下載的音訊檔案
            audio_files = list(output_dir.glob(f"audio_{output_template.stem.split('_')[-1]}.mp3"))
            if audio_files:
                return audio_files[0]
            
            # 如果沒有找到 mp3，尋找其他音訊格式
            audio_files = (
                list(output_dir.glob(f"audio_{output_template.stem.split('_')[-1]}.*")) +
                list(output_dir.glob("*.mp3")) +
                list(output_dir.glob("*.m4a")) +
                list(output_dir.glob("*.webm"))
            )
            
            return audio_files[0] if audio_files else None
            
        except Exception as e:
            logger.error(f"異步音訊下載失敗: {e}")
            return None
    
    async def _download_video_async(
        self, 
        youtube_url: str, 
        output_dir: Path, 
        progress_callback: Optional[callable] = None
    ) -> Optional[Path]:
        """異步下載影片檔案"""
        try:
            # 建立唯一的輸出檔案名稱
            output_template = output_dir / f"video_{uuid.uuid4().hex[:8]}.%(ext)s"
            
            # 設定下載選項
            video_opts = self.video_opts.copy()
            video_opts['outtmpl'] = str(output_template)
            
            if progress_callback:
                video_opts['progress_hooks'] = [
                    lambda d: self._progress_hook(d, progress_callback, "video")
                ]
            
            # 在執行緒池中執行下載
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self._download_sync,
                youtube_url,
                video_opts
            )
            
            # 尋找下載的影片檔案
            video_files = (
                list(output_dir.glob(f"video_{output_template.stem.split('_')[-1]}.*")) +
                list(output_dir.glob("*.mp4")) +
                list(output_dir.glob("*.webm")) +
                list(output_dir.glob("*.mkv"))
            )
            
            return video_files[0] if video_files else None
            
        except Exception as e:
            logger.error(f"異步影片下載失敗: {e}")
            return None
    
    def _download_sync(self, youtube_url: str, opts: Dict[str, Any]) -> None:
        """同步下載（在執行緒池中執行）"""
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([youtube_url])
    
    def _download_thumbnail_sync(self, youtube_url: str, opts: Dict[str, Any]) -> None:
        """同步下載縮圖（在執行緒池中執行）"""
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([youtube_url])
    
    def _progress_hook(self, d: Dict[str, Any], callback: callable, download_type: str) -> None:
        """下載進度回調處理"""
        try:
            if d['status'] == 'downloading':
                if 'total_bytes' in d and 'downloaded_bytes' in d:
                    progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    asyncio.create_task(callback(download_type, progress))
                elif '_percent_str' in d:
                    # 從百分比字串中提取數值
                    percent_str = d['_percent_str'].strip().replace('%', '')
                    try:
                        progress = float(percent_str)
                        asyncio.create_task(callback(download_type, progress))
                    except ValueError:
                        pass
        except Exception as e:
            logger.error(f"進度回調處理失敗: {e}")
    
    async def _move_file_async(self, source: Path, destination: Path) -> None:
        """異步移動檔案"""
        try:
            # 確保目標目錄存在
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用 aiofiles 進行異步檔案操作
            async with aiofiles.open(source, 'rb') as src:
                async with aiofiles.open(destination, 'wb') as dst:
                    while True:
                        chunk = await src.read(8192)  # 8KB chunks
                        if not chunk:
                            break
                        await dst.write(chunk)
            
            # 刪除原始檔案
            source.unlink()
            
        except Exception as e:
            logger.error(f"移動檔案失敗 {source} -> {destination}: {e}")
            # 如果異步移動失敗，嘗試同步移動
            try:
                import shutil
                shutil.move(str(source), str(destination))
            except Exception as e2:
                logger.error(f"同步移動檔案也失敗: {e2}")
    
    async def _cleanup_temp_dir(self, temp_dir: Path) -> None:
        """清理臨時目錄"""
        try:
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
                logger.debug(f"已清理臨時目錄: {temp_dir}")
        except Exception as e:
            logger.error(f"清理臨時目錄失敗: {e}")
    
    def get_download_info(self, youtube_url: str) -> Dict[str, Any]:
        """獲取下載資訊（不實際下載）
        
        Args:
            youtube_url: YouTube 影片 URL
            
        Returns:
            Dict[str, Any]: 下載資訊
        """
        try:
            opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                
                return {
                    'title': info.get('title', ''),
                    'duration': info.get('duration', 0),
                    'filesize': info.get('filesize', 0),
                    'formats': len(info.get('formats', [])),
                    'has_video': any(f.get('vcodec') != 'none' for f in info.get('formats', [])),
                    'has_audio': any(f.get('acodec') != 'none' for f in info.get('formats', [])),
                }
                
        except Exception as e:
            logger.error(f"獲取下載資訊失敗: {e}")
            return {}


# 全域實例
_download_manager = None


def get_youtube_download_manager(base_path: Optional[Path] = None) -> YouTubeDownloadManager:
    """獲取 YouTube 下載管理器的全域實例"""
    global _download_manager
    if _download_manager is None:
        if base_path is None:
            base_path = Path("temp")
        _download_manager = YouTubeDownloadManager(base_path)
    return _download_manager


# 便利函數
async def download_youtube_audio_and_video(
    youtube_url: str, 
    task_folder: Path,
    progress_callback: Optional[callable] = None
) -> Tuple[Optional[Path], Optional[Path]]:
    """便利函數：並行下載 YouTube 音訊和影片
    
    Args:
        youtube_url: YouTube 影片 URL
        task_folder: 任務資料夾路徑
        progress_callback: 進度回調函數
        
    Returns:
        Tuple[Optional[Path], Optional[Path]]: (音訊檔案路徑, 影片檔案路徑)
    """
    manager = get_youtube_download_manager()
    return await manager.download_audio_and_video(youtube_url, task_folder, progress_callback)


async def download_youtube_thumbnail(youtube_url: str, output_path: Path) -> Optional[Path]:
    """便利函數：下載 YouTube 影片縮圖
    
    Args:
        youtube_url: YouTube 影片 URL
        output_path: 輸出檔案路徑
        
    Returns:
        Optional[Path]: 縮圖檔案路徑，失敗時返回 None
    """
    manager = get_youtube_download_manager()
    return await manager.download_thumbnail(youtube_url, output_path)