
"""
資料庫遷移管理模組
處理資料庫結構的初始化、版本控制和遷移
"""

import asyncio
import sqlite3
import aiosqlite
import logging
from pathlib import Path
from datetime import datetime
import shutil
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# 預期的資料庫結構
EXPECTED_TABLES = {
    'conversion_tasks': [
        'id', 'name', 'source_type', 'source_info', 'model_used', 'language',
        'status', 'created_at', 'completed_at', 'task_folder', 'file_size',
        'duration', 'has_diarization', 'error_message', 'tags', 'video_title',
        'video_description', 'video_uploader', 'video_upload_date', 'video_duration',
        'video_thumbnail_url', 'video_view_count', 'mp4_file_size'
    ],
    'task_files': [
        'id', 'task_id', 'file_type', 'file_name', 'file_path', 'file_size', 'created_at'
    ],
    'migrations': [
        'id', 'version', 'description', 'applied_at'
    ]
}

class DatabaseInitializer:
    """負責全新資料庫的初始化"""
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)

    async def initialize_fresh_database(self) -> bool:
        """建立一個全新的資料庫和所有必要的資料表"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 建立轉換任務主表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS conversion_tasks (
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
                        error_message TEXT
                    )
                """)
                
                # 建立任務檔案關聯表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS task_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        file_type TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (task_id) REFERENCES conversion_tasks (id) ON DELETE CASCADE
                    )
                """)
                
                # 建立索引
                await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON conversion_tasks (created_at)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON conversion_tasks (status)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_files_task_id ON task_files (task_id)")
                
                # 建立遷移紀錄表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version TEXT NOT NULL UNIQUE,
                        description TEXT,
                        applied_at TIMESTAMP NOT NULL
                    )
                """)
                
                await db.commit()
            logger.info("全新資料庫初始化成功")
            return True
        except Exception as e:
            logger.error(f"全新資料庫初始化失敗: {e}")
            return False

class DatabaseMigration:
    """資料庫遷移管理類別"""
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.backup_dir = self.db_path.parent / "database_backups"
        self.backup_dir.mkdir(exist_ok=True)

    async def initialize_migration_system(self):
        """確保遷移紀錄表存在"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL UNIQUE,
                    description TEXT,
                    applied_at TIMESTAMP NOT NULL
                )
            """)
            await db.commit()

    async def get_current_version(self) -> str:
        """取得當前的資料庫版本"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT version FROM migrations ORDER BY id DESC LIMIT 1")
            row = await cursor.fetchone()
            return row[0] if row else "0.0.0"

    async def get_applied_migrations(self) -> List[str]:
        """取得所有已套用的遷移版本"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT version FROM migrations ORDER BY version")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def apply_migration(self, version: str, description: str, migration_sql: str, rollback_sql: str) -> bool:
        """套用一個遷移"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript(migration_sql)
                await db.execute(
                    "INSERT INTO migrations (version, description, applied_at) VALUES (?, ?, ?)",
                    (version, description, datetime.now().isoformat())
                )
                await db.commit()
            logger.info(f"成功套用遷移 {version}")
            return True
        except Exception as e:
            logger.error(f"套用遷移 {version} 失敗: {e}")
            # 嘗試回滾
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.executescript(rollback_sql)
                    await db.commit()
                logger.info(f"成功回滾遷移 {version}")
            except Exception as rb_e:
                logger.error(f"回滾遷移 {version} 失敗: {rb_e}")
            return False

    async def verify_database_integrity(self) -> Tuple[bool, List[str]]:
        """驗證資料庫的完整性，檢查預期的資料表和欄位是否存在"""
        errors = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                for table, expected_columns in EXPECTED_TABLES.items():
                    cursor = await db.execute(f"PRAGMA table_info({table})")
                    rows = await cursor.fetchall()
                    if not rows:
                        errors.append(f"資料表遺失: {table}")
                        continue
                    
                    existing_columns = [row[1] for row in rows]
                    for col in expected_columns:
                        if col not in existing_columns:
                            errors.append(f"資料表 '{table}' 遺失欄位: {col}")
            return not errors, errors
        except Exception as e:
            errors.append(f"資料庫完整性檢查失敗: {e}")
            return False, errors

    async def create_backup(self, backup_name: Optional[str] = None) -> Path:
        """建立資料庫備份"""
        if not backup_name:
            backup_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{self.db_path.stem}_{backup_name}.db.bak"
        
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"資料庫已備份至: {backup_path}")
        return backup_path

    async def restore_backup(self, backup_path: Path) -> bool:
        """從備份還原資料庫"""
        if not backup_path.exists():
            logger.error(f"備份檔案不存在: {backup_path}")
            return False
        shutil.copy2(backup_path, self.db_path)
        logger.info(f"資料庫已從 {backup_path} 還原")
        return True

    async def list_backups(self) -> List[Dict]:
        """列出所有備份"""
        backups = []
        for f in self.backup_dir.glob("*.db.bak"):
            stat = f.stat()
            backups.append({
                'backup_name': f.name,
                'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'current_size': stat.st_size,
                'exists': True
            })
        return sorted(backups, key=lambda x: x['created_at'], reverse=True)

    async def cleanup_old_backups(self, keep_count: int) -> int:
        """清理舊的備份"""
        backups = await self.list_backups()
        deleted_count = 0
        if len(backups) > keep_count:
            for backup_info in backups[keep_count:]:
                backup_file = self.backup_dir / backup_info['backup_name']
                if backup_file.exists():
                    backup_file.unlink()
                    deleted_count += 1
        return deleted_count

# 單例模式，確保全域只有一個遷移管理器實例
_migration_manager_instance: Optional[DatabaseMigration] = None

def get_migration_manager(db_path: str = "history/conversion_history.db") -> DatabaseMigration:
    """
    取得遷移管理器實例
    """
    global _migration_manager_instance
    if _migration_manager_instance is None:
        _migration_manager_instance = DatabaseMigration(db_path)
    return _migration_manager_instance
