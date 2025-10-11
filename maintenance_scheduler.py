"""
自動清理和維護功能模組
提供過期任務清理、磁碟空間監控和資料庫最佳化功能
"""

import asyncio
import logging
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

# 嘗試匯入 psutil，如果失敗則使用替代方案
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("psutil 未安裝，將使用基本的磁碟空間檢查功能")

logger = logging.getLogger(__name__)

class MaintenanceLevel(Enum):
    """維護等級"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class MaintenanceConfig:
    """維護配置"""
    # 清理設定
    cleanup_enabled: bool = True
    cleanup_interval_hours: int = 24  # 清理檢查間隔（小時）
    task_retention_days: int = 30     # 任務保留天數
    failed_task_retention_days: int = 7  # 失敗任務保留天數
    
    # 磁碟空間監控設定
    disk_monitor_enabled: bool = True
    disk_monitor_interval_minutes: int = 30  # 磁碟監控間隔（分鐘）
    disk_warning_threshold_percent: float = 80.0  # 磁碟空間警告閾值（%）
    disk_critical_threshold_percent: float = 90.0  # 磁碟空間危險閾值（%）
    auto_cleanup_on_critical: bool = True  # 危險時自動清理
    
    # 資料庫最佳化設定
    db_optimize_enabled: bool = True
    db_optimize_interval_hours: int = 168  # 資料庫最佳化間隔（小時，預設一週）
    vacuum_threshold_mb: int = 100  # 執行 VACUUM 的資料庫大小閾值（MB）

@dataclass
class MaintenanceReport:
    """維護報告"""
    timestamp: str
    maintenance_type: str
    level: MaintenanceLevel
    actions_taken: List[str]
    files_cleaned: int
    space_freed_mb: float
    errors: List[str]
    duration_seconds: float

class MaintenanceScheduler:
    """維護排程器"""
    
    def __init__(self, config: Optional[MaintenanceConfig] = None):
        """
        初始化維護排程器
        
        Args:
            config: 維護配置，如果未提供則使用預設配置
        """
        self.config = config or MaintenanceConfig()
        self.is_running = False
        self.tasks: List[asyncio.Task] = []
        self.last_cleanup = None
        self.last_db_optimize = None
        self.reports: List[MaintenanceReport] = []
        
        # 匯入相關模組
        try:
            from database import get_db
            from file_manager import get_file_manager
            self.get_db = get_db
            self.get_file_manager = get_file_manager
        except ImportError as e:
            logger.error(f"無法匯入必要模組: {e}")
            raise
        
        logger.info("維護排程器初始化完成")
    
    async def start(self) -> None:
        """啟動維護排程器"""
        if self.is_running:
            logger.warning("維護排程器已在運行中")
            return
        
        self.is_running = True
        logger.info("啟動維護排程器")
        
        # 啟動各種維護任務
        if self.config.cleanup_enabled:
            cleanup_task = asyncio.create_task(self._cleanup_scheduler())
            self.tasks.append(cleanup_task)
        
        if self.config.disk_monitor_enabled:
            monitor_task = asyncio.create_task(self._disk_monitor_scheduler())
            self.tasks.append(monitor_task)
        
        if self.config.db_optimize_enabled:
            optimize_task = asyncio.create_task(self._db_optimize_scheduler())
            self.tasks.append(optimize_task)
        
        logger.info(f"啟動了 {len(self.tasks)} 個維護任務")
    
    async def stop(self) -> None:
        """停止維護排程器"""
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("停止維護排程器")
        
        # 取消所有任務
        for task in self.tasks:
            task.cancel()
        
        # 等待任務完成
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
        logger.info("維護排程器已停止")
    
    async def force_cleanup(self, retention_days: Optional[int] = None) -> MaintenanceReport:
        """
        強制執行清理操作
        
        Args:
            retention_days: 自訂保留天數，如果未提供則使用配置值
            
        Returns:
            MaintenanceReport: 清理報告
        """
        start_time = datetime.now()
        actions_taken = []
        files_cleaned = 0
        space_freed_mb = 0.0
        errors = []
        
        try:
            logger.info("開始強制清理操作")
            
            retention_days = retention_days or self.config.task_retention_days
            failed_retention_days = self.config.failed_task_retention_days
            
            # 清理過期任務
            db = await self.get_db()
            file_manager = self.get_file_manager()
            
            # 取得過期的已完成任務
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            expired_tasks = await self._get_expired_tasks(db, cutoff_date, 'completed')
            
            # 取得過期的失敗任務
            failed_cutoff_date = datetime.now() - timedelta(days=failed_retention_days)
            expired_failed_tasks = await self._get_expired_tasks(db, failed_cutoff_date, 'failed')
            
            all_expired_tasks = expired_tasks + expired_failed_tasks
            
            for task in all_expired_tasks:
                try:
                    task_id = task['id']
                    task_folder = file_manager.get_task_folder_by_id(task_id)
                    
                    if task_folder and task_folder.exists():
                        # 計算資料夾大小
                        folder_size = self._calculate_folder_size(task_folder)
                        
                        # 刪除任務資料夾
                        if file_manager.delete_task_folder(task_folder):
                            space_freed_mb += folder_size / (1024 * 1024)
                            files_cleaned += 1
                            actions_taken.append(f"刪除過期任務資料夾: {task_folder.name}")
                    
                    # 從資料庫刪除任務記錄
                    if await db.delete_task(task_id):
                        actions_taken.append(f"刪除過期任務記錄: {task_id}")
                
                except Exception as e:
                    error_msg = f"清理任務 {task.get('id', 'unknown')} 失敗: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 清理影片檔案（YouTube 增強功能）
            video_cleaned, video_space_freed = await self._cleanup_video_files(retention_days)
            if video_cleaned > 0:
                actions_taken.append(f"清理過期影片檔案: {video_cleaned} 個")
                space_freed_mb += video_space_freed
            
            # 清理空資料夾
            empty_folders_cleaned = file_manager.cleanup_empty_folders()
            if empty_folders_cleaned > 0:
                actions_taken.append(f"清理空資料夾: {empty_folders_cleaned} 個")
            
            # 清理臨時檔案
            temp_cleaned = await self._cleanup_temp_files()
            if temp_cleaned > 0:
                actions_taken.append(f"清理臨時檔案: {temp_cleaned} 個")
                space_freed_mb += temp_cleaned * 0.1  # 估算臨時檔案大小
            
            self.last_cleanup = datetime.now()
            
        except Exception as e:
            error_msg = f"強制清理操作失敗: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
        
        # 生成報告
        duration = (datetime.now() - start_time).total_seconds()
        level = MaintenanceLevel.HIGH if files_cleaned > 10 else MaintenanceLevel.MEDIUM
        
        report = MaintenanceReport(
            timestamp=start_time.isoformat(),
            maintenance_type="cleanup",
            level=level,
            actions_taken=actions_taken,
            files_cleaned=files_cleaned,
            space_freed_mb=space_freed_mb,
            errors=errors,
            duration_seconds=duration
        )
        
        self.reports.append(report)
        logger.info(f"清理完成: 清理 {files_cleaned} 個任務，釋放 {space_freed_mb:.2f} MB 空間")
        
        return report
    
    async def check_disk_space(self) -> Dict:
        """
        檢查磁碟空間狀態
        
        Returns:
            Dict: 磁碟空間資訊
        """
        try:
            # 取得歷史資料夾所在磁碟的使用情況
            history_path = Path("history")
            if not history_path.exists():
                history_path = Path(".")
            
            disk_usage = shutil.disk_usage(history_path)
            total_gb = disk_usage.total / (1024**3)
            used_gb = (disk_usage.total - disk_usage.free) / (1024**3)
            free_gb = disk_usage.free / (1024**3)
            used_percent = (used_gb / total_gb) * 100
            
            # 判斷警告等級
            if used_percent >= self.config.disk_critical_threshold_percent:
                level = MaintenanceLevel.CRITICAL
            elif used_percent >= self.config.disk_warning_threshold_percent:
                level = MaintenanceLevel.HIGH
            else:
                level = MaintenanceLevel.LOW
            
            return {
                'total_gb': round(total_gb, 2),
                'used_gb': round(used_gb, 2),
                'free_gb': round(free_gb, 2),
                'used_percent': round(used_percent, 2),
                'level': level.value,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"檢查磁碟空間失敗: {e}")
            return {
                'error': str(e),
                'level': MaintenanceLevel.CRITICAL.value,
                'timestamp': datetime.now().isoformat()
            }
    
    async def optimize_database(self) -> MaintenanceReport:
        """
        執行資料庫最佳化
        
        Returns:
            MaintenanceReport: 最佳化報告
        """
        start_time = datetime.now()
        actions_taken = []
        errors = []
        
        try:
            logger.info("開始資料庫最佳化")
            
            db = await self.get_db()
            db_path = Path(db.db_path)
            
            if not db_path.exists():
                raise FileNotFoundError(f"資料庫檔案不存在: {db_path}")
            
            # 檢查資料庫大小
            db_size_mb = db_path.stat().st_size / (1024 * 1024)
            actions_taken.append(f"資料庫大小: {db_size_mb:.2f} MB")
            
            # 執行 VACUUM 操作（如果資料庫夠大）
            if db_size_mb >= self.config.vacuum_threshold_mb:
                await self._vacuum_database(db)
                actions_taken.append("執行 VACUUM 操作")
            
            # 重建索引
            await self._rebuild_indexes(db)
            actions_taken.append("重建資料庫索引")
            
            # 分析資料庫統計資訊
            await self._analyze_database(db)
            actions_taken.append("更新資料庫統計資訊")
            
            # 檢查資料庫完整性
            integrity_ok = await self._check_database_integrity(db)
            if integrity_ok:
                actions_taken.append("資料庫完整性檢查通過")
            else:
                errors.append("資料庫完整性檢查失敗")
            
            self.last_db_optimize = datetime.now()
            
        except Exception as e:
            error_msg = f"資料庫最佳化失敗: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
        
        # 生成報告
        duration = (datetime.now() - start_time).total_seconds()
        level = MaintenanceLevel.MEDIUM
        
        report = MaintenanceReport(
            timestamp=start_time.isoformat(),
            maintenance_type="database_optimization",
            level=level,
            actions_taken=actions_taken,
            files_cleaned=0,
            space_freed_mb=0.0,
            errors=errors,
            duration_seconds=duration
        )
        
        self.reports.append(report)
        logger.info(f"資料庫最佳化完成，耗時 {duration:.2f} 秒")
        
        return report
    
    async def get_maintenance_status(self) -> Dict:
        """
        取得維護狀態資訊
        
        Returns:
            Dict: 維護狀態
        """
        try:
            disk_info = await self.check_disk_space()
            
            # 統計任務數量
            db = await self.get_db()
            total_tasks = await db.get_task_count()
            completed_tasks = await db.get_tasks_by_status('completed')
            failed_tasks = await db.get_tasks_by_status('failed')
            
            # YouTube 任務統計
            youtube_tasks = await db.get_youtube_tasks(limit=100)  # 取得最近的 YouTube 任務
            
            # 計算歷史資料夾大小
            history_path = Path("history")
            history_size_mb = 0
            if history_path.exists():
                history_size_mb = self._calculate_folder_size(history_path) / (1024 * 1024)
            
            # 影片檔案統計
            video_stats = await self.check_video_storage_usage()
            
            return {
                'scheduler_running': self.is_running,
                'last_cleanup': self.last_cleanup.isoformat() if self.last_cleanup else None,
                'last_db_optimize': self.last_db_optimize.isoformat() if self.last_db_optimize else None,
                'disk_info': disk_info,
                'task_stats': {
                    'total': total_tasks,
                    'completed': len(completed_tasks),
                    'failed': len(failed_tasks),
                    'youtube_tasks': len(youtube_tasks)
                },
                'video_stats': video_stats,
                'history_size_mb': round(history_size_mb, 2),
                'recent_reports': len([r for r in self.reports if 
                    datetime.fromisoformat(r.timestamp) > datetime.now() - timedelta(days=7)]),
                'config': {
                    'cleanup_enabled': self.config.cleanup_enabled,
                    'disk_monitor_enabled': self.config.disk_monitor_enabled,
                    'db_optimize_enabled': self.config.db_optimize_enabled,
                    'task_retention_days': self.config.task_retention_days
                }
            }
            
        except Exception as e:
            logger.error(f"取得維護狀態失敗: {e}")
            return {'error': str(e)}
    
    async def _cleanup_scheduler(self) -> None:
        """清理排程任務"""
        while self.is_running:
            try:
                # 檢查是否需要執行清理
                if (self.last_cleanup is None or 
                    datetime.now() - self.last_cleanup > timedelta(hours=self.config.cleanup_interval_hours)):
                    
                    await self.force_cleanup()
                
                # 等待下次檢查
                await asyncio.sleep(3600)  # 每小時檢查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理排程任務錯誤: {e}")
                await asyncio.sleep(300)  # 錯誤時等待5分鐘再重試
    
    async def _disk_monitor_scheduler(self) -> None:
        """磁碟監控排程任務"""
        while self.is_running:
            try:
                disk_info = await self.check_disk_space()
                
                # 檢查是否需要警告或自動清理
                if disk_info.get('level') == 'critical':
                    logger.warning(f"磁碟空間危險: {disk_info.get('used_percent', 0):.1f}% 已使用")
                    
                    if self.config.auto_cleanup_on_critical:
                        logger.info("磁碟空間不足，執行自動清理")
                        await self.force_cleanup(retention_days=7)  # 使用更短的保留期間
                
                elif disk_info.get('level') == 'high':
                    logger.warning(f"磁碟空間警告: {disk_info.get('used_percent', 0):.1f}% 已使用")
                
                # 等待下次檢查
                await asyncio.sleep(self.config.disk_monitor_interval_minutes * 60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"磁碟監控任務錯誤: {e}")
                await asyncio.sleep(300)
    
    async def _db_optimize_scheduler(self) -> None:
        """資料庫最佳化排程任務"""
        while self.is_running:
            try:
                # 檢查是否需要執行最佳化
                if (self.last_db_optimize is None or 
                    datetime.now() - self.last_db_optimize > timedelta(hours=self.config.db_optimize_interval_hours)):
                    
                    await self.optimize_database()
                
                # 等待下次檢查（每天檢查一次）
                await asyncio.sleep(86400)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"資料庫最佳化排程任務錯誤: {e}")
                await asyncio.sleep(3600)  # 錯誤時等待1小時再重試
    
    async def _get_expired_tasks(self, db, cutoff_date: datetime, status: str) -> List[Dict]:
        """取得過期任務"""
        try:
            tasks = await db.get_tasks_by_status(status)
            expired_tasks = []
            
            for task in tasks:
                created_at = datetime.fromisoformat(task['created_at'])
                if created_at < cutoff_date:
                    expired_tasks.append(task)
            
            return expired_tasks
            
        except Exception as e:
            logger.error(f"取得過期任務失敗: {e}")
            return []
    
    def _calculate_folder_size(self, folder_path: Path) -> int:
        """計算資料夾大小（位元組）"""
        total_size = 0
        try:
            for file_path in folder_path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.error(f"計算資料夾大小失敗: {e}")
        return total_size
    
    async def _cleanup_temp_files(self) -> int:
        """清理臨時檔案"""
        cleaned_count = 0
        try:
            temp_path = Path("temp")
            if temp_path.exists():
                # 清理超過1天的臨時檔案
                cutoff_time = datetime.now() - timedelta(days=1)
                
                for file_path in temp_path.iterdir():
                    if file_path.is_file():
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < cutoff_time:
                            try:
                                file_path.unlink()
                                cleaned_count += 1
                            except Exception as e:
                                logger.warning(f"刪除臨時檔案失敗: {file_path}, {e}")
        
        except Exception as e:
            logger.error(f"清理臨時檔案失敗: {e}")
        
        return cleaned_count
    
    async def _vacuum_database(self, db) -> None:
        """執行資料庫 VACUUM 操作"""
        try:
            import aiosqlite
            async with aiosqlite.connect(db.db_path) as conn:
                await conn.execute("VACUUM")
                await conn.commit()
            logger.info("資料庫 VACUUM 操作完成")
        except Exception as e:
            logger.error(f"資料庫 VACUUM 操作失敗: {e}")
            raise
    
    async def _rebuild_indexes(self, db) -> None:
        """重建資料庫索引"""
        try:
            import aiosqlite
            async with aiosqlite.connect(db.db_path) as conn:
                await conn.execute("REINDEX")
                await conn.commit()
            logger.info("資料庫索引重建完成")
        except Exception as e:
            logger.error(f"重建資料庫索引失敗: {e}")
            raise
    
    async def _analyze_database(self, db) -> None:
        """分析資料庫統計資訊"""
        try:
            import aiosqlite
            async with aiosqlite.connect(db.db_path) as conn:
                await conn.execute("ANALYZE")
                await conn.commit()
            logger.info("資料庫統計資訊更新完成")
        except Exception as e:
            logger.error(f"更新資料庫統計資訊失敗: {e}")
            raise
    
    async def _check_database_integrity(self, db) -> bool:
        """檢查資料庫完整性"""
        try:
            import aiosqlite
            async with aiosqlite.connect(db.db_path) as conn:
                cursor = await conn.execute("PRAGMA integrity_check")
                result = await cursor.fetchone()
                return result and result[0] == "ok"
        except Exception as e:
            logger.error(f"檢查資料庫完整性失敗: {e}")
            return False
    
    async def _cleanup_video_files(self, retention_days: int) -> Tuple[int, float]:
        """
        清理過期的影片檔案（YouTube 增強功能）
        
        Args:
            retention_days: 保留天數
            
        Returns:
            Tuple[int, float]: (清理的檔案數量, 釋放的空間 MB)
        """
        cleaned_count = 0
        space_freed_mb = 0.0
        
        try:
            logger.info("開始清理過期影片檔案")
            
            # 取得磁碟空間管理器
            try:
                from disk_space_manager import DiskSpaceManager
                disk_manager = DiskSpaceManager()
                
                # 使用磁碟空間管理器清理舊影片檔案
                result = await disk_manager.cleanup_old_video_files(days_old=retention_days)
                cleaned_count = result.get('cleaned_files', 0)
                space_freed_mb = result.get('cleaned_size_mb', 0.0)
                
                logger.info(f"透過磁碟空間管理器清理了 {cleaned_count} 個影片檔案")
                
            except ImportError:
                logger.warning("磁碟空間管理器不可用，使用基本清理方式")
                # 基本清理方式：直接掃描任務資料夾中的影片檔案
                cleaned_count, space_freed_mb = await self._basic_video_cleanup(retention_days)
            
        except Exception as e:
            logger.error(f"清理影片檔案失敗: {e}")
        
        return cleaned_count, space_freed_mb
    
    async def _basic_video_cleanup(self, retention_days: int) -> Tuple[int, float]:
        """
        基本的影片檔案清理方式
        
        Args:
            retention_days: 保留天數
            
        Returns:
            Tuple[int, float]: (清理的檔案數量, 釋放的空間 MB)
        """
        cleaned_count = 0
        space_freed_mb = 0.0
        
        try:
            history_path = Path("history/tasks")
            if not history_path.exists():
                return cleaned_count, space_freed_mb
            
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            video_extensions = {'.mp4', '.webm', '.mkv', '.avi', '.mov'}
            
            for task_folder in history_path.iterdir():
                if not task_folder.is_dir():
                    continue
                
                try:
                    # 檢查資料夾的修改時間
                    folder_time = datetime.fromtimestamp(task_folder.stat().st_mtime)
                    if folder_time > cutoff_time:
                        continue
                    
                    # 掃描資料夾中的影片檔案
                    for file_path in task_folder.iterdir():
                        if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                            try:
                                file_size = file_path.stat().st_size
                                file_path.unlink()
                                
                                cleaned_count += 1
                                space_freed_mb += file_size / (1024 * 1024)
                                
                                logger.debug(f"刪除過期影片檔案: {file_path}")
                                
                            except Exception as e:
                                logger.warning(f"刪除影片檔案失敗: {file_path}, {e}")
                
                except Exception as e:
                    logger.warning(f"處理任務資料夾失敗: {task_folder}, {e}")
        
        except Exception as e:
            logger.error(f"基本影片清理失敗: {e}")
        
        return cleaned_count, space_freed_mb
    
    async def check_video_storage_usage(self) -> Dict:
        """
        檢查影片檔案的儲存使用情況（YouTube 增強功能）
        
        Returns:
            Dict: 影片儲存使用情況
        """
        try:
            logger.info("檢查影片檔案儲存使用情況")
            
            history_path = Path("history/tasks")
            if not history_path.exists():
                return {
                    'total_video_files': 0,
                    'total_video_size_mb': 0.0,
                    'average_file_size_mb': 0.0,
                    'oldest_video_date': None,
                    'newest_video_date': None
                }
            
            video_extensions = {'.mp4', '.webm', '.mkv', '.avi', '.mov'}
            video_files = []
            total_size = 0
            
            # 掃描所有任務資料夾
            for task_folder in history_path.iterdir():
                if not task_folder.is_dir():
                    continue
                
                for file_path in task_folder.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                        try:
                            stat = file_path.stat()
                            video_files.append({
                                'path': str(file_path),
                                'size': stat.st_size,
                                'modified': datetime.fromtimestamp(stat.st_mtime)
                            })
                            total_size += stat.st_size
                        except Exception as e:
                            logger.warning(f"讀取影片檔案資訊失敗: {file_path}, {e}")
            
            # 計算統計資訊
            total_count = len(video_files)
            total_size_mb = total_size / (1024 * 1024)
            average_size_mb = total_size_mb / total_count if total_count > 0 else 0.0
            
            oldest_date = None
            newest_date = None
            if video_files:
                dates = [f['modified'] for f in video_files]
                oldest_date = min(dates).isoformat()
                newest_date = max(dates).isoformat()
            
            return {
                'total_video_files': total_count,
                'total_video_size_mb': round(total_size_mb, 2),
                'average_file_size_mb': round(average_size_mb, 2),
                'oldest_video_date': oldest_date,
                'newest_video_date': newest_date,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"檢查影片儲存使用情況失敗: {e}")
            return {'error': str(e)}
    
    async def generate_maintenance_report(self) -> Dict:
        """
        生成詳細的維護報告（包含 YouTube 增強功能統計）
        
        Returns:
            Dict: 詳細維護報告
        """
        try:
            logger.info("生成維護報告")
            
            # 基本系統狀態
            status = await self.get_maintenance_status()
            
            # 影片檔案統計
            video_stats = await self.check_video_storage_usage()
            
            # 資料庫統計
            db = await self.get_db()
            
            # YouTube 任務統計
            youtube_tasks = await db.get_youtube_tasks(limit=1000)  # 取得所有 YouTube 任務
            youtube_with_video = len([t for t in youtube_tasks if any(f['file_type'] == 'video' for f in t.get('files', []))])
            
            # 最近的維護報告
            recent_reports = [r for r in self.reports if 
                            datetime.fromisoformat(r.timestamp) > datetime.now() - timedelta(days=30)]
            
            # 計算維護效果
            total_space_freed = sum(r.space_freed_mb for r in recent_reports)
            total_files_cleaned = sum(r.files_cleaned for r in recent_reports)
            
            return {
                'report_timestamp': datetime.now().isoformat(),
                'system_status': status,
                'video_statistics': video_stats,
                'youtube_tasks': {
                    'total_youtube_tasks': len(youtube_tasks),
                    'tasks_with_video_files': youtube_with_video,
                    'video_download_rate': round(youtube_with_video / len(youtube_tasks) * 100, 1) if youtube_tasks else 0
                },
                'maintenance_summary': {
                    'reports_last_30_days': len(recent_reports),
                    'total_space_freed_mb': round(total_space_freed, 2),
                    'total_files_cleaned': total_files_cleaned,
                    'average_cleanup_size_mb': round(total_space_freed / len(recent_reports), 2) if recent_reports else 0
                },
                'recommendations': await self._generate_maintenance_recommendations(status, video_stats)
            }
            
        except Exception as e:
            logger.error(f"生成維護報告失敗: {e}")
            return {'error': str(e)}
    
    async def _generate_maintenance_recommendations(self, status: Dict, video_stats: Dict) -> List[str]:
        """
        生成維護建議
        
        Args:
            status: 系統狀態
            video_stats: 影片統計資訊
            
        Returns:
            List[str]: 維護建議列表
        """
        recommendations = []
        
        try:
            # 磁碟空間建議
            disk_info = status.get('disk_info', {})
            used_percent = disk_info.get('used_percent', 0)
            
            if used_percent > 90:
                recommendations.append("磁碟空間嚴重不足，建議立即清理過期檔案")
            elif used_percent > 80:
                recommendations.append("磁碟空間不足，建議清理舊的影片檔案")
            
            # 影片檔案建議
            total_video_size = video_stats.get('total_video_size_mb', 0)
            total_video_files = video_stats.get('total_video_files', 0)
            
            if total_video_size > 10000:  # 超過 10GB
                recommendations.append("影片檔案佔用空間過大，建議調整保留策略")
            
            if total_video_files > 100:
                recommendations.append("影片檔案數量較多，建議定期清理舊檔案")
            
            # 維護頻率建議
            if not status.get('scheduler_running'):
                recommendations.append("維護排程器未運行，建議啟用自動維護")
            
            last_cleanup = status.get('last_cleanup')
            if last_cleanup:
                last_cleanup_time = datetime.fromisoformat(last_cleanup)
                if datetime.now() - last_cleanup_time > timedelta(days=7):
                    recommendations.append("距離上次清理時間較長，建議執行手動清理")
            else:
                recommendations.append("尚未執行過清理操作，建議執行初始清理")
            
            # 資料庫建議
            last_optimize = status.get('last_db_optimize')
            if last_optimize:
                last_optimize_time = datetime.fromisoformat(last_optimize)
                if datetime.now() - last_optimize_time > timedelta(days=30):
                    recommendations.append("資料庫長時間未最佳化，建議執行資料庫維護")
            else:
                recommendations.append("尚未執行過資料庫最佳化，建議執行資料庫維護")
            
            if not recommendations:
                recommendations.append("系統狀態良好，維護正常運行")
            
        except Exception as e:
            logger.error(f"生成維護建議失敗: {e}")
            recommendations.append("無法生成維護建議，請檢查系統狀態")
        
        return recommendations


# 全域維護排程器實例
_maintenance_scheduler_instance: Optional[MaintenanceScheduler] = None

def get_maintenance_scheduler(config: Optional[MaintenanceConfig] = None) -> MaintenanceScheduler:
    """
    取得維護排程器實例（單例模式）
    
    Args:
        config: 維護配置
        
    Returns:
        MaintenanceScheduler: 維護排程器實例
    """
    global _maintenance_scheduler_instance
    if _maintenance_scheduler_instance is None:
        _maintenance_scheduler_instance = MaintenanceScheduler(config)
    return _maintenance_scheduler_instance


if __name__ == "__main__":
    # 測試維護功能
    async def test_maintenance():
        """測試維護功能"""
        print("開始測試維護功能...")
        
        # 建立測試配置
        config = MaintenanceConfig(
            cleanup_interval_hours=1,
            task_retention_days=1,
            disk_monitor_interval_minutes=1,
            db_optimize_interval_hours=1
        )
        
        scheduler = MaintenanceScheduler(config)
        
        # 測試磁碟空間檢查
        disk_info = await scheduler.check_disk_space()
        print(f"✓ 磁碟空間檢查: {disk_info.get('used_percent', 0):.1f}% 已使用")
        
        # 測試強制清理
        cleanup_report = await scheduler.force_cleanup()
        print(f"✓ 強制清理: 清理 {cleanup_report.files_cleaned} 個檔案，釋放 {cleanup_report.space_freed_mb:.2f} MB")
        
        # 測試資料庫最佳化
        optimize_report = await scheduler.optimize_database()
        print(f"✓ 資料庫最佳化: 執行 {len(optimize_report.actions_taken)} 個操作")
        
        # 測試維護狀態
        status = await scheduler.get_maintenance_status()
        print(f"✓ 維護狀態: 總任務數 {status.get('task_stats', {}).get('total', 0)}")
        
        print("✓ 維護功能測試完成")
    
    # 執行測試
    asyncio.run(test_maintenance())