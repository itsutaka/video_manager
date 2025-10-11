"""
檔案中繼資料追蹤系統
提供檔案中繼資料的記錄、更新和查詢功能
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import hashlib
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class FileType(Enum):
    """檔案類型枚舉"""
    AUDIO = "audio"
    SRT = "srt"
    TXT = "txt"
    OTHER = "other"

class FileStatus(Enum):
    """檔案狀態枚舉"""
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class FileMetadata:
    """檔案中繼資料結構"""
    file_id: str
    task_id: str
    file_name: str
    file_path: str
    file_type: FileType
    file_size: int
    file_hash: str
    mime_type: Optional[str]
    status: FileStatus
    created_at: str
    updated_at: str
    processing_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """轉換為字典格式"""
        data = asdict(self)
        # 轉換枚舉為字串
        data['file_type'] = self.file_type.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FileMetadata':
        """從字典建立實例"""
        # 轉換字串為枚舉
        data['file_type'] = FileType(data['file_type'])
        data['status'] = FileStatus(data['status'])
        return cls(**data)

class MetadataTracker:
    """檔案中繼資料追蹤器"""
    
    def __init__(self, base_path: str = "history/tasks"):
        """
        初始化中繼資料追蹤器
        
        Args:
            base_path: 任務資料夾的基礎路徑
        """
        self.base_path = Path(base_path)
        self.metadata_cache: Dict[str, FileMetadata] = {}
        logger.info(f"中繼資料追蹤器初始化，基礎路徑: {self.base_path}")
    
    async def track_file(self, task_id: str, file_path: Path, 
                        file_type: FileType, processing_info: Optional[Dict] = None) -> str:
        """
        開始追蹤檔案，建立中繼資料記錄
        
        Args:
            task_id: 任務 ID
            file_path: 檔案路徑
            file_type: 檔案類型
            processing_info: 處理資訊
            
        Returns:
            str: 檔案 ID
        """
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"檔案不存在: {file_path}")
            
            # 生成檔案 ID
            file_id = self._generate_file_id(task_id, file_path.name)
            
            # 計算檔案雜湊值
            file_hash = await self._calculate_file_hash_async(file_path)
            
            # 取得檔案資訊
            stat = file_path.stat()
            
            # 建立中繼資料
            metadata = FileMetadata(
                file_id=file_id,
                task_id=task_id,
                file_name=file_path.name,
                file_path=str(file_path),
                file_type=file_type,
                file_size=stat.st_size,
                file_hash=file_hash,
                mime_type=self._get_mime_type(file_path),
                status=FileStatus.CREATED,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                processing_info=processing_info
            )
            
            # 保存中繼資料
            await self._save_metadata(metadata)
            
            # 加入快取
            self.metadata_cache[file_id] = metadata
            
            logger.info(f"開始追蹤檔案: {file_id} ({file_path.name})")
            return file_id
            
        except Exception as e:
            logger.error(f"追蹤檔案失敗: {e}")
            raise
    
    async def update_file_status(self, file_id: str, status: FileStatus, 
                                error_message: Optional[str] = None,
                                processing_info: Optional[Dict] = None) -> bool:
        """
        更新檔案狀態
        
        Args:
            file_id: 檔案 ID
            status: 新狀態
            error_message: 錯誤訊息（如果有）
            processing_info: 處理資訊更新
            
        Returns:
            bool: 更新是否成功
        """
        try:
            metadata = await self.get_file_metadata(file_id)
            if not metadata:
                logger.warning(f"檔案 {file_id} 的中繼資料不存在")
                return False
            
            # 更新狀態
            metadata.status = status
            metadata.updated_at = datetime.now().isoformat()
            
            if error_message:
                metadata.error_message = error_message
            
            if processing_info:
                if metadata.processing_info:
                    metadata.processing_info.update(processing_info)
                else:
                    metadata.processing_info = processing_info
            
            # 保存更新
            await self._save_metadata(metadata)
            
            # 更新快取
            self.metadata_cache[file_id] = metadata
            
            logger.info(f"更新檔案狀態: {file_id} -> {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"更新檔案狀態失敗: {e}")
            return False
    
    async def get_file_metadata(self, file_id: str) -> Optional[FileMetadata]:
        """
        取得檔案中繼資料
        
        Args:
            file_id: 檔案 ID
            
        Returns:
            Optional[FileMetadata]: 檔案中繼資料，如果不存在則回傳 None
        """
        try:
            # 先檢查快取
            if file_id in self.metadata_cache:
                return self.metadata_cache[file_id]
            
            # 從檔案載入
            metadata = await self._load_metadata(file_id)
            if metadata:
                self.metadata_cache[file_id] = metadata
            
            return metadata
            
        except Exception as e:
            logger.error(f"取得檔案中繼資料失敗: {e}")
            return None
    
    async def get_task_files_metadata(self, task_id: str) -> List[FileMetadata]:
        """
        取得任務的所有檔案中繼資料
        
        Args:
            task_id: 任務 ID
            
        Returns:
            List[FileMetadata]: 檔案中繼資料列表
        """
        try:
            metadata_list = []
            
            # 搜尋任務資料夾
            task_folder = self._find_task_folder(task_id)
            if not task_folder:
                logger.warning(f"找不到任務 {task_id} 的資料夾")
                return []
            
            # 載入所有中繼資料檔案
            metadata_dir = task_folder / ".metadata"
            if metadata_dir.exists():
                for metadata_file in metadata_dir.glob("*.json"):
                    try:
                        metadata = await self._load_metadata_from_file(metadata_file)
                        if metadata and metadata.task_id == task_id:
                            metadata_list.append(metadata)
                    except Exception as e:
                        logger.warning(f"載入中繼資料檔案失敗: {metadata_file}, {e}")
            
            # 按建立時間排序
            metadata_list.sort(key=lambda x: x.created_at)
            return metadata_list
            
        except Exception as e:
            logger.error(f"取得任務檔案中繼資料失敗: {e}")
            return []
    
    async def remove_file_metadata(self, file_id: str) -> bool:
        """
        移除檔案中繼資料
        
        Args:
            file_id: 檔案 ID
            
        Returns:
            bool: 移除是否成功
        """
        try:
            # 從快取移除
            if file_id in self.metadata_cache:
                del self.metadata_cache[file_id]
            
            # 刪除中繼資料檔案
            metadata_file = self._get_metadata_file_path(file_id)
            if metadata_file and metadata_file.exists():
                metadata_file.unlink()
                logger.info(f"移除檔案中繼資料: {file_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"移除檔案中繼資料失敗: {e}")
            return False
    
    async def verify_file_integrity(self, file_id: str) -> Dict[str, Any]:
        """
        驗證檔案完整性
        
        Args:
            file_id: 檔案 ID
            
        Returns:
            Dict[str, Any]: 驗證結果
        """
        try:
            metadata = await self.get_file_metadata(file_id)
            if not metadata:
                return {
                    'is_valid': False,
                    'error': '中繼資料不存在'
                }
            
            file_path = Path(metadata.file_path)
            if not file_path.exists():
                return {
                    'is_valid': False,
                    'error': '檔案不存在'
                }
            
            # 檢查檔案大小
            current_size = file_path.stat().st_size
            if current_size != metadata.file_size:
                return {
                    'is_valid': False,
                    'error': f'檔案大小不符：預期 {metadata.file_size}，實際 {current_size}'
                }
            
            # 檢查檔案雜湊值
            current_hash = await self._calculate_file_hash_async(file_path)
            if current_hash != metadata.file_hash:
                return {
                    'is_valid': False,
                    'error': '檔案雜湊值不符，檔案可能已損壞'
                }
            
            return {
                'is_valid': True,
                'file_size': current_size,
                'file_hash': current_hash,
                'last_verified': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"驗證檔案完整性失敗: {e}")
            return {
                'is_valid': False,
                'error': f'驗證失敗: {str(e)}'
            }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        取得追蹤統計資訊
        
        Returns:
            Dict[str, Any]: 統計資訊
        """
        try:
            stats = {
                'total_files': 0,
                'by_type': {},
                'by_status': {},
                'total_size': 0,
                'cache_size': len(self.metadata_cache)
            }
            
            # 統計所有任務的檔案
            for task_folder in self.base_path.iterdir():
                if task_folder.is_dir():
                    metadata_list = await self._load_all_metadata_in_folder(task_folder)
                    
                    for metadata in metadata_list:
                        stats['total_files'] += 1
                        stats['total_size'] += metadata.file_size
                        
                        # 按類型統計
                        file_type = metadata.file_type.value
                        stats['by_type'][file_type] = stats['by_type'].get(file_type, 0) + 1
                        
                        # 按狀態統計
                        status = metadata.status.value
                        stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
            
            stats['total_size_mb'] = stats['total_size'] / (1024 * 1024)
            return stats
            
        except Exception as e:
            logger.error(f"取得統計資訊失敗: {e}")
            return {}
    
    def _generate_file_id(self, task_id: str, filename: str) -> str:
        """生成檔案 ID"""
        content = f"{task_id}_{filename}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _get_mime_type(self, file_path: Path) -> Optional[str]:
        """取得檔案 MIME 類型"""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type
    
    async def _calculate_file_hash_async(self, file_path: Path) -> str:
        """異步計算檔案雜湊值"""
        def _calculate_hash():
            hash_obj = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _calculate_hash)
    
    def _find_task_folder(self, task_id: str) -> Optional[Path]:
        """尋找任務資料夾"""
        for folder in self.base_path.iterdir():
            if folder.is_dir() and task_id[:8] in folder.name:
                info_file = folder / ".task_info"
                if info_file.exists():
                    try:
                        with open(info_file, 'r', encoding='utf-8') as f:
                            info = json.load(f)
                            if info.get('task_id') == task_id:
                                return folder
                    except Exception:
                        continue
        return None
    
    async def _save_metadata(self, metadata: FileMetadata) -> None:
        """保存中繼資料到檔案"""
        task_folder = self._find_task_folder(metadata.task_id)
        if not task_folder:
            raise ValueError(f"找不到任務 {metadata.task_id} 的資料夾")
        
        # 建立中繼資料目錄
        metadata_dir = task_folder / ".metadata"
        metadata_dir.mkdir(exist_ok=True)
        
        # 保存中繼資料檔案
        metadata_file = metadata_dir / f"{metadata.file_id}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)
    
    async def _load_metadata(self, file_id: str) -> Optional[FileMetadata]:
        """載入中繼資料"""
        metadata_file = self._get_metadata_file_path(file_id)
        if metadata_file and metadata_file.exists():
            return await self._load_metadata_from_file(metadata_file)
        return None
    
    async def _load_metadata_from_file(self, metadata_file: Path) -> Optional[FileMetadata]:
        """從檔案載入中繼資料"""
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return FileMetadata.from_dict(data)
        except Exception as e:
            logger.error(f"載入中繼資料檔案失敗: {metadata_file}, {e}")
            return None
    
    def _get_metadata_file_path(self, file_id: str) -> Optional[Path]:
        """取得中繼資料檔案路徑"""
        # 搜尋所有任務資料夾中的中繼資料檔案
        for task_folder in self.base_path.iterdir():
            if task_folder.is_dir():
                metadata_file = task_folder / ".metadata" / f"{file_id}.json"
                if metadata_file.exists():
                    return metadata_file
        return None
    
    async def _load_all_metadata_in_folder(self, task_folder: Path) -> List[FileMetadata]:
        """載入資料夾中的所有中繼資料"""
        metadata_list = []
        metadata_dir = task_folder / ".metadata"
        
        if metadata_dir.exists():
            for metadata_file in metadata_dir.glob("*.json"):
                metadata = await self._load_metadata_from_file(metadata_file)
                if metadata:
                    metadata_list.append(metadata)
        
        return metadata_list


# 全域中繼資料追蹤器實例
_metadata_tracker_instance: Optional[MetadataTracker] = None

def get_metadata_tracker() -> MetadataTracker:
    """
    取得中繼資料追蹤器實例（單例模式）
    
    Returns:
        MetadataTracker: 中繼資料追蹤器實例
    """
    global _metadata_tracker_instance
    if _metadata_tracker_instance is None:
        _metadata_tracker_instance = MetadataTracker()
    return _metadata_tracker_instance


if __name__ == "__main__":
    # 測試中繼資料追蹤功能
    import tempfile
    import uuid
    
    async def test_metadata_tracker():
        """測試中繼資料追蹤器功能"""
        print("開始測試中繼資料追蹤器功能...")
        
        # 使用臨時目錄進行測試
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = MetadataTracker(base_path=temp_dir)
            
            # 建立測試任務資料夾
            task_id = str(uuid.uuid4())
            task_folder = Path(temp_dir) / f"20250929_test_{task_id[:8]}"
            task_folder.mkdir()
            
            # 建立任務資訊檔案
            task_info = {"task_id": task_id, "task_name": "測試任務"}
            with open(task_folder / ".task_info", 'w', encoding='utf-8') as f:
                json.dump(task_info, f)
            
            # 建立測試檔案
            test_file = task_folder / "test.mp3"
            test_file.write_text("fake audio content")
            
            # 測試追蹤檔案
            file_id = await tracker.track_file(
                task_id, test_file, FileType.AUDIO, 
                {"duration": 120.5, "bitrate": 192}
            )
            print(f"✓ 開始追蹤檔案: {file_id}")
            
            # 測試更新狀態
            success = await tracker.update_file_status(
                file_id, FileStatus.PROCESSING, 
                processing_info={"progress": 50}
            )
            print(f"✓ 更新檔案狀態: {success}")
            
            # 測試取得中繼資料
            metadata = await tracker.get_file_metadata(file_id)
            print(f"✓ 取得中繼資料: {metadata.file_name if metadata else 'None'}")
            
            # 測試取得任務檔案
            task_files = await tracker.get_task_files_metadata(task_id)
            print(f"✓ 取得任務檔案: {len(task_files)} 個檔案")
            
            # 測試驗證檔案完整性
            integrity = await tracker.verify_file_integrity(file_id)
            print(f"✓ 驗證檔案完整性: {integrity['is_valid']}")
            
            # 測試統計資訊
            stats = await tracker.get_statistics()
            print(f"✓ 統計資訊: {stats['total_files']} 個檔案，{stats['total_size_mb']:.3f} MB")
            
            # 測試移除中繼資料
            success = await tracker.remove_file_metadata(file_id)
            print(f"✓ 移除中繼資料: {success}")
            
        print("✓ 中繼資料追蹤器測試完成")
    
    # 執行測試
    asyncio.run(test_metadata_tracker())