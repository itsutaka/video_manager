"""
磁碟空間管理系統
提供磁碟空間監控、自動清理和管理功能
"""

import os
import shutil
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
import psutil

logger = logging.getLogger(__name__)

class DiskSpaceManager:
    """磁碟空間管理類別"""
    
    def __init__(self, base_path: str = "history/tasks", 
                 max_usage_percent: float = 80.0,
                 cleanup_threshold_days: int = 30):
        """
        初始化磁碟空間管理器
        
        Args:
            base_path: 監控的基礎路徑
            max_usage_percent: 磁碟使用率警告閾值 (%)
            cleanup_threshold_days: 自動清理檔案的天數閾值
        """
        self.base_path = Path(base_path)
        self.max_usage_percent = max_usage_percent
        self.cleanup_threshold_days = cleanup_threshold_days
        
        # 確保基礎路徑存在
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"磁碟空間管理器初始化，監控路徑: {self.base_path}")
        logger.info(f"使用率警告閾值: {self.max_usage_percent}%")
        logger.info(f"自動清理閾值: {self.cleanup_threshold_days} 天")
    
    def get_disk_usage(self, path: Optional[Path] = None) -> Dict:
        """
        獲取磁碟使用情況
        
        Args:
            path: 要檢查的路徑，預設為基礎路徑
            
        Returns:
            Dict: 磁碟使用情況資訊
        """
        try:
            target_path = path or self.base_path
            
            # 使用 psutil 獲取磁碟使用情況
            disk_usage = psutil.disk_usage(str(target_path))
            
            total_gb = disk_usage.total / (1024**3)
            used_gb = disk_usage.used / (1024**3)
            free_gb = disk_usage.free / (1024**3)
            usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            # 計算任務資料夾使用的空間
            tasks_usage = self._calculate_directory_size(self.base_path)
            tasks_usage_gb = tasks_usage / (1024**3)
            
            return {
                'total_gb': round(total_gb, 2),
                'used_gb': round(used_gb, 2),
                'free_gb': round(free_gb, 2),
                'usage_percent': round(usage_percent, 2),
                'tasks_usage_gb': round(tasks_usage_gb, 2),
                'tasks_usage_mb': round(tasks_usage / (1024**2), 2),
                'is_warning': usage_percent > self.max_usage_percent,
                'warning_threshold': self.max_usage_percent,
                'checked_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"獲取磁碟使用情況失敗: {e}")
            return {
                'total_gb': 0,
                'used_gb': 0,
                'free_gb': 0,
                'usage_percent': 0,
                'tasks_usage_gb': 0,
                'tasks_usage_mb': 0,
                'is_warning': False,
                'error': str(e),
                'checked_at': datetime.now().isoformat()
            }
    
    async def cleanup_old_video_files(self, days_old: int = None) -> Dict:
        """
        清理超過指定天數的影片檔案
        
        Args:
            days_old: 清理天數閾值，預設使用初始化時的設定
            
        Returns:
            Dict: 清理結果統計
        """
        try:
            cleanup_days = days_old or self.cleanup_threshold_days
            cutoff_date = datetime.now() - timedelta(days=cleanup_days)
            
            result = {
                'cleaned_files': 0,
                'cleaned_size_mb': 0,
                'cleaned_folders': 0,
                'errors': [],
                'cleanup_date': cutoff_date.isoformat(),
                'cleanup_days': cleanup_days
            }
            
            if not self.base_path.exists():
                logger.warning(f"基礎路徑不存在: {self.base_path}")
                return result
            
            # 遍歷所有任務資料夾
            for task_folder in self.base_path.iterdir():
                if not task_folder.is_dir():
                    continue
                
                try:
                    # 檢查資料夾的修改時間
                    folder_mtime = datetime.fromtimestamp(task_folder.stat().st_mtime)
                    
                    if folder_mtime < cutoff_date:
                        # 統計要清理的檔案
                        folder_size = 0
                        video_files = []
                        
                        for file_path in task_folder.iterdir():
                            if file_path.is_file():
                                file_ext = file_path.suffix.lower()
                                
                                # 只清理影片檔案和縮圖，保留音訊和轉錄檔案
                                if file_ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
                                    video_files.append(file_path)
                                    folder_size += file_path.stat().st_size
                                elif 'thumbnail' in file_path.name.lower() and file_ext in ['.jpg', '.jpeg', '.png', '.webp']:
                                    video_files.append(file_path)
                                    folder_size += file_path.stat().st_size
                        
                        # 清理影片檔案
                        for video_file in video_files:
                            try:
                                video_file.unlink()
                                result['cleaned_files'] += 1
                                logger.info(f"清理舊影片檔案: {video_file}")
                            except Exception as e:
                                error_msg = f"清理檔案失敗 {video_file}: {e}"
                                result['errors'].append(error_msg)
                                logger.error(error_msg)
                        
                        result['cleaned_size_mb'] += folder_size / (1024**2)
                        
                        # 如果資料夾只剩下 .task_info 檔案，考慮清理整個資料夾
                        remaining_files = [f for f in task_folder.iterdir() 
                                         if f.is_file() and f.name != '.task_info']
                        
                        if len(remaining_files) == 0:
                            try:
                                shutil.rmtree(task_folder)
                                result['cleaned_folders'] += 1
                                logger.info(f"清理空任務資料夾: {task_folder}")
                            except Exception as e:
                                error_msg = f"清理資料夾失敗 {task_folder}: {e}"
                                result['errors'].append(error_msg)
                                logger.error(error_msg)
                
                except Exception as e:
                    error_msg = f"處理任務資料夾失敗 {task_folder}: {e}"
                    result['errors'].append(error_msg)
                    logger.error(error_msg)
                    continue
            
            result['cleaned_size_mb'] = round(result['cleaned_size_mb'], 2)
            logger.info(f"清理完成: {result['cleaned_files']} 個檔案, "
                       f"{result['cleaned_size_mb']} MB, "
                       f"{result['cleaned_folders']} 個資料夾")
            
            return result
            
        except Exception as e:
            logger.error(f"清理舊影片檔案失敗: {e}")
            return {
                'cleaned_files': 0,
                'cleaned_size_mb': 0,
                'cleaned_folders': 0,
                'errors': [str(e)],
                'cleanup_date': cutoff_date.isoformat() if 'cutoff_date' in locals() else '',
                'cleanup_days': cleanup_days if 'cleanup_days' in locals() else 0
            }
    
    async def check_space_and_cleanup(self, force_cleanup: bool = False) -> Dict:
        """
        檢查磁碟空間並在必要時執行清理
        
        Args:
            force_cleanup: 是否強制執行清理
            
        Returns:
            Dict: 檢查和清理結果
        """
        try:
            # 獲取當前磁碟使用情況
            disk_info = self.get_disk_usage()
            
            result = {
                'disk_info': disk_info,
                'cleanup_triggered': False,
                'cleanup_result': None,
                'recommendations': []
            }
            
            # 判斷是否需要清理
            needs_cleanup = (
                force_cleanup or 
                disk_info['is_warning'] or 
                disk_info['tasks_usage_gb'] > 5.0  # 任務檔案超過 5GB
            )
            
            if needs_cleanup:
                logger.info("觸發自動清理機制")
                result['cleanup_triggered'] = True
                
                # 執行清理
                cleanup_result = await self.cleanup_old_video_files()
                result['cleanup_result'] = cleanup_result
                
                # 重新檢查磁碟使用情況
                result['disk_info_after'] = self.get_disk_usage()
            
            # 提供建議
            if disk_info['usage_percent'] > 90:
                result['recommendations'].append('磁碟使用率超過 90%，建議立即清理或擴展儲存空間')
            elif disk_info['usage_percent'] > self.max_usage_percent:
                result['recommendations'].append(f'磁碟使用率超過 {self.max_usage_percent}%，建議清理舊檔案')
            
            if disk_info['tasks_usage_gb'] > 10:
                result['recommendations'].append('任務檔案佔用超過 10GB，建議清理舊的影片檔案')
            
            return result
            
        except Exception as e:
            logger.error(f"檢查空間和清理失敗: {e}")
            return {
                'disk_info': self.get_disk_usage(),
                'cleanup_triggered': False,
                'cleanup_result': None,
                'recommendations': [],
                'error': str(e)
            }
    
    def get_large_files(self, min_size_mb: float = 100.0, limit: int = 20) -> List[Dict]:
        """
        獲取大檔案列表
        
        Args:
            min_size_mb: 最小檔案大小 (MB)
            limit: 返回檔案數量限制
            
        Returns:
            List[Dict]: 大檔案資訊列表
        """
        try:
            large_files = []
            min_size_bytes = min_size_mb * 1024 * 1024
            
            if not self.base_path.exists():
                return large_files
            
            # 遍歷所有檔案
            for task_folder in self.base_path.iterdir():
                if not task_folder.is_dir():
                    continue
                
                for file_path in task_folder.rglob('*'):
                    if file_path.is_file():
                        try:
                            file_size = file_path.stat().st_size
                            
                            if file_size >= min_size_bytes:
                                file_info = {
                                    'file_path': str(file_path),
                                    'file_name': file_path.name,
                                    'size_mb': round(file_size / (1024**2), 2),
                                    'size_bytes': file_size,
                                    'file_type': self._determine_file_type(file_path),
                                    'modified_at': datetime.fromtimestamp(
                                        file_path.stat().st_mtime
                                    ).isoformat(),
                                    'task_folder': task_folder.name
                                }
                                large_files.append(file_info)
                        
                        except Exception as e:
                            logger.warning(f"無法獲取檔案資訊 {file_path}: {e}")
                            continue
            
            # 按檔案大小排序
            large_files.sort(key=lambda x: x['size_bytes'], reverse=True)
            
            return large_files[:limit]
            
        except Exception as e:
            logger.error(f"獲取大檔案列表失敗: {e}")
            return []
    
    def get_storage_statistics(self) -> Dict:
        """
        獲取儲存統計資訊
        
        Returns:
            Dict: 儲存統計資訊
        """
        try:
            stats = {
                'total_tasks': 0,
                'total_files': 0,
                'file_types': {
                    'audio': {'count': 0, 'size_mb': 0},
                    'video': {'count': 0, 'size_mb': 0},
                    'thumbnail': {'count': 0, 'size_mb': 0},
                    'srt': {'count': 0, 'size_mb': 0},
                    'txt': {'count': 0, 'size_mb': 0},
                    'other': {'count': 0, 'size_mb': 0}
                },
                'oldest_task': None,
                'newest_task': None,
                'total_size_mb': 0
            }
            
            if not self.base_path.exists():
                return stats
            
            oldest_time = None
            newest_time = None
            
            # 遍歷所有任務資料夾
            for task_folder in self.base_path.iterdir():
                if not task_folder.is_dir():
                    continue
                
                stats['total_tasks'] += 1
                folder_mtime = datetime.fromtimestamp(task_folder.stat().st_mtime)
                
                # 更新最舊和最新任務時間
                if oldest_time is None or folder_mtime < oldest_time:
                    oldest_time = folder_mtime
                    stats['oldest_task'] = {
                        'folder': task_folder.name,
                        'modified_at': folder_mtime.isoformat()
                    }
                
                if newest_time is None or folder_mtime > newest_time:
                    newest_time = folder_mtime
                    stats['newest_task'] = {
                        'folder': task_folder.name,
                        'modified_at': folder_mtime.isoformat()
                    }
                
                # 統計檔案
                for file_path in task_folder.iterdir():
                    if file_path.is_file() and not file_path.name.startswith('.'):
                        try:
                            file_size = file_path.stat().st_size
                            file_size_mb = file_size / (1024**2)
                            file_type = self._determine_file_type(file_path)
                            
                            stats['total_files'] += 1
                            stats['total_size_mb'] += file_size_mb
                            
                            if file_type in stats['file_types']:
                                stats['file_types'][file_type]['count'] += 1
                                stats['file_types'][file_type]['size_mb'] += file_size_mb
                            else:
                                stats['file_types']['other']['count'] += 1
                                stats['file_types']['other']['size_mb'] += file_size_mb
                        
                        except Exception as e:
                            logger.warning(f"統計檔案失敗 {file_path}: {e}")
                            continue
            
            # 四捨五入數值
            stats['total_size_mb'] = round(stats['total_size_mb'], 2)
            for file_type in stats['file_types']:
                stats['file_types'][file_type]['size_mb'] = round(
                    stats['file_types'][file_type]['size_mb'], 2
                )
            
            return stats
            
        except Exception as e:
            logger.error(f"獲取儲存統計失敗: {e}")
            return {
                'total_tasks': 0,
                'total_files': 0,
                'file_types': {},
                'oldest_task': None,
                'newest_task': None,
                'total_size_mb': 0,
                'error': str(e)
            }
    
    def _calculate_directory_size(self, directory: Path) -> int:
        """
        計算目錄總大小
        
        Args:
            directory: 目錄路徑
            
        Returns:
            int: 目錄大小（位元組）
        """
        try:
            total_size = 0
            
            if not directory.exists():
                return 0
            
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                    except Exception as e:
                        logger.warning(f"無法獲取檔案大小 {file_path}: {e}")
                        continue
            
            return total_size
            
        except Exception as e:
            logger.error(f"計算目錄大小失敗: {e}")
            return 0
    
    def _determine_file_type(self, file_path: Path) -> str:
        """
        根據檔案副檔名判斷檔案類型
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            str: 檔案類型
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
        elif ext == '.srt':
            return 'srt'
        elif ext == '.txt':
            return 'txt'
        else:
            return 'other'


# 全域磁碟空間管理器實例
_disk_manager_instance: Optional[DiskSpaceManager] = None

def get_disk_manager() -> DiskSpaceManager:
    """
    取得磁碟空間管理器實例（單例模式）
    
    Returns:
        DiskSpaceManager: 磁碟空間管理器實例
    """
    global _disk_manager_instance
    if _disk_manager_instance is None:
        _disk_manager_instance = DiskSpaceManager()
    return _disk_manager_instance


if __name__ == "__main__":
    # 測試磁碟空間管理功能
    import asyncio
    import tempfile
    
    async def test_disk_manager():
        """測試磁碟空間管理器功能"""
        print("開始測試磁碟空間管理器功能...")
        
        # 使用臨時目錄進行測試
        with tempfile.TemporaryDirectory() as temp_dir:
            dm = DiskSpaceManager(base_path=temp_dir, cleanup_threshold_days=0)
            
            # 測試獲取磁碟使用情況
            disk_usage = dm.get_disk_usage()
            print(f"✓ 磁碟使用情況: {disk_usage['usage_percent']:.1f}% "
                  f"({disk_usage['used_gb']:.1f}GB / {disk_usage['total_gb']:.1f}GB)")
            
            # 建立測試檔案結構
            test_task_folder = Path(temp_dir) / "20240101_120000_youtube_test_12345678"
            test_task_folder.mkdir()
            
            # 建立測試檔案
            (test_task_folder / "original.mp3").write_text("fake audio content")
            (test_task_folder / "test_video.mp4").write_text("fake video content" * 1000)
            (test_task_folder / "test_thumbnail.jpg").write_text("fake thumbnail")
            (test_task_folder / "transcript.srt").write_text("fake subtitle")
            (test_task_folder / "transcript.txt").write_text("fake transcript")
            
            # 測試儲存統計
            stats = dm.get_storage_statistics()
            print(f"✓ 儲存統計: {stats['total_tasks']} 個任務, "
                  f"{stats['total_files']} 個檔案, "
                  f"{stats['total_size_mb']:.2f} MB")
            
            # 測試大檔案列表
            large_files = dm.get_large_files(min_size_mb=0.001)  # 很小的閾值用於測試
            print(f"✓ 大檔案列表: {len(large_files)} 個檔案")
            
            # 測試清理功能
            cleanup_result = await dm.cleanup_old_video_files(days_old=0)
            print(f"✓ 清理結果: {cleanup_result['cleaned_files']} 個檔案, "
                  f"{cleanup_result['cleaned_size_mb']:.2f} MB")
            
            # 測試檢查空間和清理
            check_result = await dm.check_space_and_cleanup()
            print(f"✓ 空間檢查: 清理觸發={check_result['cleanup_triggered']}")
            
        print("✓ 磁碟空間管理器測試完成")
    
    # 執行測試
    asyncio.run(test_disk_manager())