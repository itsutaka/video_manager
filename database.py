"""
轉換歷史紀錄資料庫管理模組
提供 SQLite 資料庫連線和 CRUD 操作功能
"""

import sqlite3
import aiosqlite
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)

# 匯入遷移管理器
try:
    from database_migration import get_migration_manager
    MIGRATION_AVAILABLE = True
except ImportError:
    MIGRATION_AVAILABLE = False
    logger.warning("遷移管理器不可用，將使用基本初始化")

class ConversionHistoryDB:
    """轉換歷史紀錄資料庫管理類別"""
    
    def __init__(self, db_path: str = "history/conversion_history.db"):
        """
        初始化資料庫管理器
        
        Args:
            db_path: 資料庫檔案路徑
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
    async def initialize_database(self) -> None:
        """初始化資料庫，建立必要的資料表"""
        # 如果有遷移管理器，優先使用遷移系統
        if MIGRATION_AVAILABLE:
            try:
                migration_manager = await get_migration_manager()
                await migration_manager.initialize_migration_system()
                logger.info("使用遷移系統初始化資料庫")
                return
            except Exception as e:
                logger.warning(f"遷移系統初始化失敗，使用基本初始化: {e}")
        
        # 基本初始化方式
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
            
            # 建立索引以提升查詢效能
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON conversion_tasks (created_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON conversion_tasks (status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_files_task_id ON task_files (task_id)")
            
            await db.commit()
            logger.info("資料庫初始化完成")
    
    async def create_task(self, task_data: Dict, task_id: Optional[str] = None) -> str:
        """
        建立新的轉換任務記錄
        
        Args:
            task_data: 任務資料字典，包含 name, source_type, source_info, model_used 等
            task_id: 指定的任務 ID，如果未提供則自動生成
            
        Returns:
            str: 新建立的任務 ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO conversion_tasks (
                    id, name, source_type, source_info, model_used, 
                    language, status, task_folder, file_size, has_diarization
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                task_data.get('name', ''),
                task_data.get('source_type', ''),
                task_data.get('source_info', ''),
                task_data.get('model_used', 'whisper-1'),
                task_data.get('language'),
                'processing',
                task_data.get('task_folder', ''),
                task_data.get('file_size'),
                task_data.get('has_diarization', False)
            ))
            await db.commit()
            
        logger.info(f"建立新任務記錄: {task_id}")
        return task_id
    
    async def update_task_status(self, task_id: str, status: str, **kwargs) -> bool:
        """
        更新任務狀態和相關資訊
        
        Args:
            task_id: 任務 ID
            status: 新狀態 ('processing', 'completed', 'failed')
            **kwargs: 其他要更新的欄位 (completed_at, duration, error_message 等)
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 建立動態更新語句
            update_fields = ['status = ?']
            values = [status]
            
            # 處理額外的更新欄位
            for key, value in kwargs.items():
                if key in ['completed_at', 'duration', 'error_message', 'file_size']:
                    update_fields.append(f"{key} = ?")
                    values.append(value)
            
            # 如果狀態是 completed，自動設定完成時間
            if status == 'completed' and 'completed_at' not in kwargs:
                update_fields.append("completed_at = ?")
                values.append(datetime.now().isoformat())
            
            values.append(task_id)  # WHERE 條件的參數
            
            async with aiosqlite.connect(self.db_path) as db:
                query = f"UPDATE conversion_tasks SET {', '.join(update_fields)} WHERE id = ?"
                cursor = await db.execute(query, values)
                await db.commit()
                
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"更新任務 {task_id} 狀態為 {status}")
                else:
                    logger.warning(f"任務 {task_id} 不存在，無法更新狀態")
                    
                return success
                
        except Exception as e:
            logger.error(f"更新任務狀態失敗: {e}")
            return False

    async def add_task_file(self, task_id: str, file_info: Dict) -> bool:
        """
        新增任務相關檔案記錄
        
        Args:
            task_id: 任務 ID
            file_info: 檔案資訊字典，包含 file_type, file_name, file_path, file_size
            
        Returns:
            bool: 新增是否成功
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO task_files (task_id, file_type, file_name, file_path, file_size)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    task_id,
                    file_info.get('file_type', ''),
                    file_info.get('file_name', ''),
                    file_info.get('file_path', ''),
                    file_info.get('file_size', 0)
                ))
                await db.commit()
                
            logger.info(f"新增檔案記錄到任務 {task_id}: {file_info.get('file_name')}")
            return True
            
        except Exception as e:
            logger.error(f"新增檔案記錄失敗: {e}")
            return False

    async def get_task_history(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        取得轉換歷史紀錄列表
        
        Args:
            limit: 限制回傳筆數
            offset: 偏移量（用於分頁）
            
        Returns:
            List[Dict]: 任務列表
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row  # 讓結果可以用字典方式存取
                
                cursor = await db.execute("""
                    SELECT * FROM conversion_tasks 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                
                rows = await cursor.fetchall()
                
                # 轉換為字典列表
                tasks = []
                for row in rows:
                    task = dict(row)
                    # 取得該任務的檔案列表
                    task['files'] = await self._get_task_files(db, task['id'])
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            logger.error(f"取得歷史紀錄失敗: {e}")
            return []

    async def get_task_by_id(self, task_id: str) -> Optional[Dict]:
        """
        根據 ID 取得特定任務詳情
        
        Args:
            task_id: 任務 ID
            
        Returns:
            Optional[Dict]: 任務詳情，如果不存在則回傳 None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute(
                    "SELECT * FROM conversion_tasks WHERE id = ?", 
                    (task_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    task = dict(row)
                    task['files'] = await self._get_task_files(db, task_id)
                    return task
                    
                return None
                
        except Exception as e:
            logger.error(f"取得任務詳情失敗: {e}")
            return None

    async def delete_task(self, task_id: str) -> bool:
        """
        刪除指定的轉換任務及其相關檔案記錄
        
        Args:
            task_id: 要刪除的任務 ID
            
        Returns:
            bool: 刪除是否成功
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 由於設定了 ON DELETE CASCADE，刪除任務時會自動刪除相關檔案記錄
                cursor = await db.execute(
                    "DELETE FROM conversion_tasks WHERE id = ?", 
                    (task_id,)
                )
                await db.commit()
                
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"刪除任務記錄: {task_id}")
                else:
                    logger.warning(f"任務 {task_id} 不存在，無法刪除")
                    
                return success
                
        except Exception as e:
            logger.error(f"刪除任務失敗: {e}")
            return False

    async def search_tasks(self, query: str, date_from: Optional[str] = None, 
                          date_to: Optional[str] = None, file_type: Optional[str] = None) -> List[Dict]:
        """
        搜尋和篩選轉換任務
        
        Args:
            query: 搜尋關鍵字（搜尋任務名稱和來源資訊）
            date_from: 開始日期 (ISO 格式)
            date_to: 結束日期 (ISO 格式)
            file_type: 檔案類型篩選
            
        Returns:
            List[Dict]: 符合條件的任務列表
        """
        try:
            conditions = []
            params = []
            
            # 關鍵字搜尋
            if query:
                conditions.append("(name LIKE ? OR source_info LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%"])
            
            # 日期範圍篩選
            if date_from:
                conditions.append("created_at >= ?")
                params.append(date_from)
                
            if date_to:
                conditions.append("created_at <= ?")
                params.append(date_to)
            
            # 建立查詢語句
            base_query = "SELECT * FROM conversion_tasks"
            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)
            base_query += " ORDER BY created_at DESC"
            
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute(base_query, params)
                rows = await cursor.fetchall()
                
                # 轉換為字典列表並加入檔案資訊
                tasks = []
                for row in rows:
                    task = dict(row)
                    task['files'] = await self._get_task_files(db, task['id'])
                    
                    # 如果有檔案類型篩選，檢查任務是否包含該類型檔案
                    if file_type:
                        has_file_type = any(f['file_type'] == file_type for f in task['files'])
                        if has_file_type:
                            tasks.append(task)
                    else:
                        tasks.append(task)
                
                return tasks
                
        except Exception as e:
            logger.error(f"搜尋任務失敗: {e}")
            return []

    async def _get_task_files(self, db: aiosqlite.Connection, task_id: str) -> List[Dict]:
        """
        取得指定任務的所有檔案記錄（內部輔助方法）
        
        Args:
            db: 資料庫連線
            task_id: 任務 ID
            
        Returns:
            List[Dict]: 檔案記錄列表
        """
        cursor = await db.execute(
            "SELECT * FROM task_files WHERE task_id = ? ORDER BY created_at",
            (task_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def get_task_count(self) -> int:
        """
        取得總任務數量
        
        Returns:
            int: 任務總數
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM conversion_tasks")
                result = await cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            logger.error(f"取得任務數量失敗: {e}")
            return 0
    
    async def get_tasks_by_status(self, status: str) -> List[Dict]:
        """
        根據狀態取得任務列表
        
        Args:
            status: 任務狀態 ('processing', 'completed', 'failed')
            
        Returns:
            List[Dict]: 指定狀態的任務列表
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute(
                    "SELECT * FROM conversion_tasks WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                )
                rows = await cursor.fetchall()
                
                tasks = []
                for row in rows:
                    task = dict(row)
                    task['files'] = await self._get_task_files(db, task['id'])
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            logger.error(f"根據狀態取得任務失敗: {e}")
            return []

    async def cleanup_old_tasks(self, days_old: int = 30) -> int:
        """
        清理指定天數之前的舊任務記錄
        
        Args:
            days_old: 保留天數，超過此天數的任務將被刪除
            
        Returns:
            int: 被刪除的任務數量
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM conversion_tasks WHERE created_at < ?",
                    (cutoff_date.isoformat(),)
                )
                await db.commit()
                
                deleted_count = cursor.rowcount
                logger.info(f"清理了 {deleted_count} 個超過 {days_old} 天的舊任務")
                return deleted_count
                
        except Exception as e:
            logger.error(f"清理舊任務失敗: {e}")
            return 0

    async def update_task_metadata(self, task_id: str, metadata: dict) -> bool:
        """
        更新任務的 YouTube 元資料
        
        Args:
            task_id: 任務 ID
            metadata: 元資料字典，包含 YouTube 影片資訊和任務名稱
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 建立動態更新語句
            update_fields = []
            values = []
            
            # 處理任務名稱欄位
            if 'name' in metadata and metadata['name'] is not None:
                update_fields.append("name = ?")
                values.append(metadata['name'])
            
            # 處理 YouTube 元資料欄位
            metadata_fields = {
                'video_title': metadata.get('video_title') or metadata.get('title'),
                'video_description': metadata.get('video_description') or metadata.get('description'),
                'video_uploader': metadata.get('video_uploader') or metadata.get('uploader'),
                'video_upload_date': metadata.get('video_upload_date') or metadata.get('upload_date'),
                'video_duration': metadata.get('video_duration') or metadata.get('duration'),
                'video_thumbnail_url': metadata.get('video_thumbnail_url') or metadata.get('thumbnail_url'),
                'video_view_count': metadata.get('video_view_count') or metadata.get('view_count')
            }
            
            for field, value in metadata_fields.items():
                if value is not None:
                    update_fields.append(f"{field} = ?")
                    values.append(value)
            
            if not update_fields:
                logger.warning(f"沒有有效的元資料可更新，任務 ID: {task_id}")
                return False
            
            values.append(task_id)  # WHERE 條件的參數
            
            async with aiosqlite.connect(self.db_path) as db:
                query = f"UPDATE conversion_tasks SET {', '.join(update_fields)} WHERE id = ?"
                cursor = await db.execute(query, values)
                await db.commit()
                
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"更新任務 {task_id} 的元資料，更新了 {len(update_fields)} 個欄位")
                else:
                    logger.warning(f"任務 {task_id} 不存在，無法更新元資料")
                    
                return success
                
        except Exception as e:
            logger.error(f"更新任務元資料失敗: {e}")
            return False

    async def get_tasks_with_metadata(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        獲取包含完整元資料的任務列表
        
        Args:
            limit: 限制回傳筆數
            offset: 偏移量（用於分頁）
            
        Returns:
            List[Dict]: 包含完整元資料的任務列表
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute("""
                    SELECT 
                        id, name, source_type, source_info, model_used, language, status,
                        created_at, completed_at, task_folder, file_size, duration,
                        has_diarization, error_message, tags,
                        video_title, video_description, video_uploader, video_upload_date,
                        video_duration, video_thumbnail_url, video_view_count
                    FROM conversion_tasks 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                
                rows = await cursor.fetchall()
                
                # 轉換為字典列表
                tasks = []
                for row in rows:
                    task = dict(row)
                    # 取得該任務的檔案列表
                    task['files'] = await self._get_task_files(db, task['id'])
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            logger.error(f"取得包含元資料的歷史紀錄失敗: {e}")
            return []

    async def search_tasks_by_title(self, query: str) -> List[Dict]:
        """
        按影片標題搜尋任務
        
        Args:
            query: 搜尋關鍵字
            
        Returns:
            List[Dict]: 符合條件的任務列表
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute("""
                    SELECT 
                        id, name, source_type, source_info, model_used, language, status,
                        created_at, completed_at, task_folder, file_size, duration,
                        has_diarization, error_message, tags,
                        video_title, video_description, video_uploader, video_upload_date,
                        video_duration, video_thumbnail_url, video_view_count
                    FROM conversion_tasks 
                    WHERE video_title LIKE ? OR video_uploader LIKE ? OR name LIKE ?
                    ORDER BY created_at DESC
                """, (f"%{query}%", f"%{query}%", f"%{query}%"))
                
                rows = await cursor.fetchall()
                
                # 轉換為字典列表並加入檔案資訊
                tasks = []
                for row in rows:
                    task = dict(row)
                    task['files'] = await self._get_task_files(db, task['id'])
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            logger.error(f"按標題搜尋任務失敗: {e}")
            return []

    async def get_youtube_tasks(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        獲取 YouTube 來源的任務列表
        
        Args:
            limit: 限制回傳筆數
            offset: 偏移量（用於分頁）
            
        Returns:
            List[Dict]: YouTube 任務列表
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute("""
                    SELECT 
                        id, name, source_type, source_info, model_used, language, status,
                        created_at, completed_at, task_folder, file_size, duration,
                        has_diarization, error_message, tags,
                        video_title, video_description, video_uploader, video_upload_date,
                        video_duration, video_thumbnail_url, video_view_count
                    FROM conversion_tasks 
                    WHERE source_type = 'youtube' AND video_title IS NOT NULL
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                
                rows = await cursor.fetchall()
                
                # 轉換為字典列表
                tasks = []
                for row in rows:
                    task = dict(row)
                    # 取得該任務的檔案列表
                    task['files'] = await self._get_task_files(db, task['id'])
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            logger.error(f"取得 YouTube 任務失敗: {e}")
            return []


# 全域資料庫實例
_db_instance: Optional[ConversionHistoryDB] = None

async def get_db() -> ConversionHistoryDB:
    """
    取得資料庫實例（單例模式）
    
    Returns:
        ConversionHistoryDB: 資料庫管理器實例
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = ConversionHistoryDB()
        await _db_instance.initialize_database()
    return _db_instance


if __name__ == "__main__":
    # 測試資料庫功能
    async def test_database():
        """測試資料庫基本功能"""
        print("開始測試資料庫功能...")
        
        db = await get_db()
        
        # 測試建立任務
        task_data = {
            'name': '測試任務',
            'source_type': 'file',
            'source_info': 'test.mp3',
            'model_used': 'whisper-1',
            'task_folder': 'history/tasks/test_folder',
            'file_size': 1024000,
            'has_diarization': False
        }
        
        task_id = await db.create_task(task_data)
        print(f"✓ 建立任務: {task_id}")
        
        # 測試新增檔案
        file_info = {
            'file_type': 'audio',
            'file_name': 'original.mp3',
            'file_path': 'history/tasks/test_folder/original.mp3',
            'file_size': 1024000
        }
        
        success = await db.add_task_file(task_id, file_info)
        print(f"✓ 新增檔案記錄: {success}")
        
        # 測試更新狀態
        success = await db.update_task_status(task_id, 'completed', duration=120.5)
        print(f"✓ 更新任務狀態: {success}")
        
        # 測試查詢
        tasks = await db.get_task_history(limit=10)
        print(f"✓ 查詢到 {len(tasks)} 個任務")
        
        # 測試根據 ID 查詢
        task = await db.get_task_by_id(task_id)
        print(f"✓ 根據 ID 查詢任務: {task['name'] if task else 'None'}")
        
        # 測試搜尋
        search_results = await db.search_tasks("測試")
        print(f"✓ 搜尋結果: {len(search_results)} 個任務")
        
        # 測試任務數量
        count = await db.get_task_count()
        print(f"✓ 總任務數量: {count}")
        
        # 測試根據狀態查詢
        completed_tasks = await db.get_tasks_by_status('completed')
        print(f"✓ 已完成任務: {len(completed_tasks)} 個")
        
        print("✓ 資料庫測試完成")
    
    # 執行測試
    asyncio.run(test_database())