"""
資料庫初始化腳本
提供資料庫建立、初始化和設定功能
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional
import logging

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 匯入相關模組
from database_migration import DatabaseMigration, DatabaseInitializer
from database import ConversionHistoryDB


class DatabaseSetup:
    """資料庫設定管理類別"""
    
    def __init__(self, db_path: str = "history/conversion_history.db"):
        """
        初始化資料庫設定管理器
        
        Args:
            db_path: 資料庫檔案路徑
        """
        self.db_path = Path(db_path)
        self.migration_manager = DatabaseMigration(db_path)
        self.initializer = DatabaseInitializer(db_path)
        self.db = ConversionHistoryDB(db_path)
    
    async def setup_database(self, force_recreate: bool = False) -> bool:
        """
        設定資料庫（檢查是否存在，如不存在則建立）
        
        Args:
            force_recreate: 是否強制重新建立資料庫
            
        Returns:
            bool: 設定是否成功
        """
        try:
            # 檢查資料庫是否存在
            db_exists = self.db_path.exists()
            
            if force_recreate and db_exists:
                logger.info("強制重新建立資料庫...")
                # 建立備份
                backup_path = await self.migration_manager.create_backup("before_recreate")
                logger.info(f"已備份現有資料庫: {backup_path}")
                
                # 刪除現有資料庫
                self.db_path.unlink()
                db_exists = False
            
            if not db_exists:
                logger.info("資料庫不存在，開始建立新資料庫...")
                success = await self.initializer.initialize_fresh_database()
                
                if success:
                    logger.info("✓ 新資料庫建立完成")
                else:
                    logger.error("✗ 新資料庫建立失敗")
                    return False
            else:
                logger.info("資料庫已存在，檢查結構...")
                
                # 初始化遷移系統（如果尚未初始化）
                await self.migration_manager.initialize_migration_system()
                
                # 驗證資料庫完整性
                is_valid, errors = await self.migration_manager.verify_database_integrity()
                
                if not is_valid:
                    logger.warning("資料庫完整性檢查發現問題:")
                    for error in errors:
                        logger.warning(f"  - {error}")
                    
                    # 嘗試修復或重新初始化
                    logger.info("嘗試修復資料庫...")
                    await self.db.initialize_database()
                else:
                    logger.info("✓ 資料庫結構正常")
            
            # 最終驗證
            final_check, final_errors = await self.migration_manager.verify_database_integrity()
            
            if final_check:
                logger.info("✓ 資料庫設定完成")
                return True
            else:
                logger.error("✗ 資料庫設定失敗")
                for error in final_errors:
                    logger.error(f"  - {error}")
                return False
                
        except Exception as e:
            logger.error(f"資料庫設定過程發生錯誤: {e}")
            return False
    
    async def migrate_database(self, target_version: Optional[str] = None) -> bool:
        """
        執行資料庫遷移
        
        Args:
            target_version: 目標版本，如果未指定則遷移到最新版本
            
        Returns:
            bool: 遷移是否成功
        """
        try:
            current_version = await self.migration_manager.get_current_version()
            logger.info(f"當前資料庫版本: {current_version}")
            
            # 這裡可以定義需要的遷移
            available_migrations = [
                {
                    "version": "1.0.1",
                    "description": "新增任務標籤功能",
                    "sql": """
                        ALTER TABLE conversion_tasks ADD COLUMN tags TEXT;
                        CREATE INDEX IF NOT EXISTS idx_tasks_tags ON conversion_tasks (tags);
                    """,
                    "rollback": """
                        DROP INDEX IF EXISTS idx_tasks_tags;
                        ALTER TABLE conversion_tasks DROP COLUMN tags;
                    """
                },
                {
                    "version": "1.0.2", 
                    "description": "新增使用者偏好設定",
                    "sql": """
                        CREATE TABLE IF NOT EXISTS user_preferences (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """,
                    "rollback": """
                        DROP TABLE IF EXISTS user_preferences;
                    """
                },
                {
                    "version": "1.0.3",
                    "description": "新增 YouTube 元資料欄位到 conversion_tasks 表",
                    "sql": """
                        ALTER TABLE conversion_tasks ADD COLUMN video_title TEXT;
                        ALTER TABLE conversion_tasks ADD COLUMN video_description TEXT;
                        ALTER TABLE conversion_tasks ADD COLUMN video_uploader TEXT;
                        ALTER TABLE conversion_tasks ADD COLUMN video_upload_date TEXT;
                        ALTER TABLE conversion_tasks ADD COLUMN video_duration INTEGER;
                        ALTER TABLE conversion_tasks ADD COLUMN video_thumbnail_url TEXT;
                        ALTER TABLE conversion_tasks ADD COLUMN video_view_count INTEGER;
                        CREATE INDEX IF NOT EXISTS idx_video_title ON conversion_tasks (video_title);
                        CREATE INDEX IF NOT EXISTS idx_video_uploader ON conversion_tasks (video_uploader);
                        CREATE INDEX IF NOT EXISTS idx_source_type_created ON conversion_tasks (source_type, created_at);
                    """,
                    "rollback": """
                        DROP INDEX IF EXISTS idx_source_type_created;
                        DROP INDEX IF EXISTS idx_video_uploader;
                        DROP INDEX IF EXISTS idx_video_title;
                        CREATE TABLE conversion_tasks_temp (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            source_type TEXT NOT NULL,
                            source_info TEXT,
                            model_used TEXT NOT NULL,
                            language TEXT,
                            status TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            completed_at TIMESTAMP,
                            task_folder TEXT NOT NULL,
                            file_size INTEGER,
                            duration REAL,
                            has_diarization BOOLEAN DEFAULT FALSE,
                            error_message TEXT,
                            tags TEXT
                        );
                        INSERT INTO conversion_tasks_temp (
                            id, name, source_type, source_info, model_used, language, status,
                            created_at, completed_at, task_folder, file_size, duration,
                            has_diarization, error_message, tags
                        )
                        SELECT 
                            id, name, source_type, source_info, model_used, language, status,
                            created_at, completed_at, task_folder, file_size, duration,
                            has_diarization, error_message, tags
                        FROM conversion_tasks;
                        DROP TABLE conversion_tasks;
                        ALTER TABLE conversion_tasks_temp RENAME TO conversion_tasks;
                        CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON conversion_tasks (created_at);
                        CREATE INDEX IF NOT EXISTS idx_tasks_status ON conversion_tasks (status);
                        CREATE INDEX IF NOT EXISTS idx_tasks_tags ON conversion_tasks (tags);
                    """
                }
            ]
            
            # 套用需要的遷移
            applied_migrations = await self.migration_manager.get_applied_migrations()
            
            for migration in available_migrations:
                if migration["version"] not in applied_migrations:
                    if target_version is None or migration["version"] <= target_version:
                        logger.info(f"套用遷移 {migration['version']}: {migration['description']}")
                        
                        success = await self.migration_manager.apply_migration(
                            version=migration["version"],
                            description=migration["description"],
                            migration_sql=migration["sql"],
                            rollback_sql=migration["rollback"]
                        )
                        
                        if not success:
                            logger.error(f"遷移 {migration['version']} 失敗")
                            return False
            
            final_version = await self.migration_manager.get_current_version()
            logger.info(f"遷移完成，當前版本: {final_version}")
            return True
            
        except Exception as e:
            logger.error(f"資料庫遷移失敗: {e}")
            return False
    
    async def backup_database(self, backup_name: Optional[str] = None) -> Optional[Path]:
        """
        備份資料庫
        
        Args:
            backup_name: 備份名稱
            
        Returns:
            Optional[Path]: 備份檔案路徑，失敗時回傳 None
        """
        try:
            backup_path = await self.migration_manager.create_backup(backup_name)
            logger.info(f"✓ 資料庫備份完成: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"資料庫備份失敗: {e}")
            return None
    
    async def restore_database(self, backup_path: str) -> bool:
        """
        恢復資料庫備份
        
        Args:
            backup_path: 備份檔案路徑
            
        Returns:
            bool: 恢復是否成功
        """
        try:
            backup_file = Path(backup_path)
            success = await self.migration_manager.restore_backup(backup_file)
            
            if success:
                logger.info(f"✓ 資料庫恢復完成: {backup_path}")
            else:
                logger.error(f"✗ 資料庫恢復失敗: {backup_path}")
            
            return success
        except Exception as e:
            logger.error(f"資料庫恢復失敗: {e}")
            return False
    
    async def list_backups(self) -> None:
        """列出所有可用的備份"""
        try:
            backups = await self.migration_manager.list_backups()
            
            if not backups:
                logger.info("沒有找到任何備份")
                return
            
            logger.info(f"找到 {len(backups)} 個備份:")
            for backup in backups:
                status = "✓" if backup['exists'] else "✗"
                size_mb = backup.get('current_size', 0) / (1024 * 1024)
                logger.info(f"  {status} {backup['backup_name']} - {backup['created_at']} ({size_mb:.2f} MB)")
                
        except Exception as e:
            logger.error(f"列出備份失敗: {e}")
    
    async def cleanup_old_backups(self, keep_count: int = 10) -> None:
        """
        清理舊備份
        
        Args:
            keep_count: 保留的備份數量
        """
        try:
            deleted_count = await self.migration_manager.cleanup_old_backups(keep_count)
            logger.info(f"✓ 清理了 {deleted_count} 個舊備份")
        except Exception as e:
            logger.error(f"清理舊備份失敗: {e}")
    
    async def check_database_status(self) -> None:
        """檢查資料庫狀態"""
        try:
            logger.info("=== 資料庫狀態檢查 ===")
            
            # 檢查檔案是否存在
            exists = self.db_path.exists()
            logger.info(f"資料庫檔案存在: {'是' if exists else '否'}")
            
            if exists:
                # 檢查檔案大小
                size_mb = self.db_path.stat().st_size / (1024 * 1024)
                logger.info(f"資料庫檔案大小: {size_mb:.2f} MB")
                
                # 檢查版本
                version = await self.migration_manager.get_current_version()
                logger.info(f"資料庫版本: {version}")
                
                # 檢查已套用的遷移
                migrations = await self.migration_manager.get_applied_migrations()
                logger.info(f"已套用遷移: {len(migrations)} 個")
                for migration in migrations:
                    logger.info(f"  - {migration}")
                
                # 檢查完整性
                is_valid, errors = await self.migration_manager.verify_database_integrity()
                logger.info(f"資料庫完整性: {'正常' if is_valid else '有問題'}")
                
                if errors:
                    logger.warning("發現的問題:")
                    for error in errors:
                        logger.warning(f"  - {error}")
                
                # 檢查任務數量
                task_count = await self.db.get_task_count()
                logger.info(f"任務記錄數量: {task_count}")
            
            logger.info("=== 檢查完成 ===")
            
        except Exception as e:
            logger.error(f"檢查資料庫狀態失敗: {e}")


async def main():
    """主要執行函數"""
    if len(sys.argv) < 2:
        print("使用方式:")
        print("  python database_init.py setup [--force]     # 設定資料庫")
        print("  python database_init.py migrate [version]   # 執行遷移")
        print("  python database_init.py backup [name]       # 建立備份")
        print("  python database_init.py restore <path>      # 恢復備份")
        print("  python database_init.py list-backups        # 列出備份")
        print("  python database_init.py cleanup [count]     # 清理舊備份")
        print("  python database_init.py status              # 檢查狀態")
        return
    
    command = sys.argv[1]
    setup = DatabaseSetup()
    
    try:
        if command == "setup":
            force = "--force" in sys.argv
            success = await setup.setup_database(force_recreate=force)
            sys.exit(0 if success else 1)
            
        elif command == "migrate":
            target_version = sys.argv[2] if len(sys.argv) > 2 else None
            success = await setup.migrate_database(target_version)
            sys.exit(0 if success else 1)
            
        elif command == "backup":
            backup_name = sys.argv[2] if len(sys.argv) > 2 else None
            backup_path = await setup.backup_database(backup_name)
            sys.exit(0 if backup_path else 1)
            
        elif command == "restore":
            if len(sys.argv) < 3:
                logger.error("請指定備份檔案路徑")
                sys.exit(1)
            backup_path = sys.argv[2]
            success = await setup.restore_database(backup_path)
            sys.exit(0 if success else 1)
            
        elif command == "list-backups":
            await setup.list_backups()
            
        elif command == "cleanup":
            keep_count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            await setup.cleanup_old_backups(keep_count)
            
        elif command == "status":
            await setup.check_database_status()
            
        else:
            logger.error(f"未知的命令: {command}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"執行命令失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())