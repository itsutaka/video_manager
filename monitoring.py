"""
監控系統模組
提供 YouTube 處理和系統效能的即時監控
"""

import asyncio
import time
import psutil
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict, deque

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from config import get_config
from logging_config import get_performance_logger, get_error_tracker


@dataclass
class SystemMetrics:
    """系統指標"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    gpu_memory_percent: Optional[float] = None
    gpu_memory_used_gb: Optional[float] = None
    gpu_memory_total_gb: Optional[float] = None
    gpu_utilization: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class YouTubeProcessingMetrics:
    """YouTube 處理指標"""
    timestamp: datetime
    task_id: str
    youtube_url: str
    stage: str  # metadata_extraction, audio_download, video_download, transcription
    duration: float
    success: bool
    error_message: Optional[str] = None
    file_size: Optional[int] = None
    video_duration: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class APIMetrics:
    """API 指標"""
    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    duration: float
    task_id: Optional[str] = None
    user_agent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class MetricsCollector:
    """指標收集器"""
    
    def __init__(self):
        self.config = get_config()
        self.performance_logger = get_performance_logger()
        self.error_tracker = get_error_tracker()
        
        # 指標儲存 (記憶體中的環形緩衝區)
        self.system_metrics: deque = deque(maxlen=1440)  # 24小時的分鐘級資料
        self.youtube_metrics: deque = deque(maxlen=10000)  # 最近10000次處理
        self.api_metrics: deque = deque(maxlen=10000)  # 最近10000次API請求
        
        # 統計資料
        self.stats = {
            'youtube_processing': defaultdict(int),
            'api_requests': defaultdict(int),
            'errors': defaultdict(int),
            'warnings': defaultdict(int)
        }
        
        # 監控任務
        self._monitoring_task = None
        self._is_monitoring = False
    
    async def start_monitoring(self):
        """開始監控"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.performance_logger.logger.info("監控系統已啟動")
    
    async def stop_monitoring(self):
        """停止監控"""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        self.performance_logger.logger.info("監控系統已停止")
    
    async def _monitoring_loop(self):
        """監控循環"""
        while self._is_monitoring:
            try:
                # 收集系統指標
                await self._collect_system_metrics()
                
                # 檢查警告閾值
                await self._check_thresholds()
                
                # 等待下一次收集
                await asyncio.sleep(self.config.performance.performance_monitor_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error_tracker.track_error(e, {'context': 'monitoring_loop'})
                await asyncio.sleep(60)  # 錯誤時等待1分鐘
    
    async def _collect_system_metrics(self):
        """收集系統指標"""
        try:
            # CPU 和記憶體
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # GPU 指標 (如果可用)
            gpu_memory_percent = None
            gpu_memory_used_gb = None
            gpu_memory_total_gb = None
            gpu_utilization = None
            
            if TORCH_AVAILABLE and torch.cuda.is_available():
                try:
                    gpu_memory_used = torch.cuda.memory_allocated() / 1024**3
                    gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    gpu_memory_percent = (gpu_memory_used / gpu_memory_total) * 100
                    gpu_memory_used_gb = gpu_memory_used
                    gpu_memory_total_gb = gpu_memory_total
                    gpu_utilization = torch.cuda.utilization() if hasattr(torch.cuda, 'utilization') else None
                except Exception:
                    pass
            
            # 建立指標物件
            metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_gb=memory.used / 1024**3,
                memory_total_gb=memory.total / 1024**3,
                disk_percent=disk.percent,
                disk_used_gb=disk.used / 1024**3,
                disk_total_gb=disk.total / 1024**3,
                gpu_memory_percent=gpu_memory_percent,
                gpu_memory_used_gb=gpu_memory_used_gb,
                gpu_memory_total_gb=gpu_memory_total_gb,
                gpu_utilization=gpu_utilization
            )
            
            # 儲存指標
            self.system_metrics.append(metrics)
            
            # 記錄到日誌
            self.performance_logger.log_system_metrics(
                cpu_percent, memory.percent, disk.percent, gpu_memory_percent
            )
            
        except Exception as e:
            self.error_tracker.track_error(e, {'context': 'collect_system_metrics'})
    
    async def _check_thresholds(self):
        """檢查警告閾值"""
        if not self.system_metrics:
            return
        
        latest_metrics = self.system_metrics[-1]
        
        # CPU 警告
        if latest_metrics.cpu_percent > self.config.performance.cpu_warning_threshold:
            self.error_tracker.track_warning(
                f"CPU 使用率過高: {latest_metrics.cpu_percent:.1f}%",
                {'threshold': self.config.performance.cpu_warning_threshold},
                warning_code='HIGH_CPU_USAGE'
            )
        
        # 記憶體警告
        if latest_metrics.memory_percent > self.config.performance.memory_warning_threshold:
            self.error_tracker.track_warning(
                f"記憶體使用率過高: {latest_metrics.memory_percent:.1f}%",
                {'threshold': self.config.performance.memory_warning_threshold},
                warning_code='HIGH_MEMORY_USAGE'
            )
        
        # GPU 記憶體警告
        if (latest_metrics.gpu_memory_percent and 
            latest_metrics.gpu_memory_percent > self.config.performance.gpu_memory_warning_threshold):
            self.error_tracker.track_warning(
                f"GPU 記憶體使用率過高: {latest_metrics.gpu_memory_percent:.1f}%",
                {'threshold': self.config.performance.gpu_memory_warning_threshold},
                warning_code='HIGH_GPU_MEMORY_USAGE'
            )
        
        # 磁碟空間警告
        if latest_metrics.disk_percent > self.config.disk_space.disk_warning_threshold:
            self.error_tracker.track_warning(
                f"磁碟使用率過高: {latest_metrics.disk_percent:.1f}%",
                {'threshold': self.config.disk_space.disk_warning_threshold},
                warning_code='HIGH_DISK_USAGE'
            )
    
    def record_youtube_processing(self, task_id: str, youtube_url: str, stage: str, 
                                 duration: float, success: bool, error_message: str = None,
                                 file_size: int = None, video_duration: float = None):
        """記錄 YouTube 處理指標"""
        metrics = YouTubeProcessingMetrics(
            timestamp=datetime.now(),
            task_id=task_id,
            youtube_url=youtube_url,
            stage=stage,
            duration=duration,
            success=success,
            error_message=error_message,
            file_size=file_size,
            video_duration=video_duration
        )
        
        self.youtube_metrics.append(metrics)
        
        # 更新統計
        self.stats['youtube_processing'][f'{stage}_total'] += 1
        if success:
            self.stats['youtube_processing'][f'{stage}_success'] += 1
        else:
            self.stats['youtube_processing'][f'{stage}_error'] += 1
    
    def record_api_request(self, endpoint: str, method: str, status_code: int, 
                          duration: float, task_id: str = None, user_agent: str = None):
        """記錄 API 請求指標"""
        metrics = APIMetrics(
            timestamp=datetime.now(),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration=duration,
            task_id=task_id,
            user_agent=user_agent
        )
        
        self.api_metrics.append(metrics)
        
        # 更新統計
        self.stats['api_requests']['total'] += 1
        self.stats['api_requests'][f'status_{status_code}'] += 1
        
        # 記錄到效能日誌
        self.performance_logger.log_api_performance(
            endpoint, method, duration, status_code, task_id
        )
    
    def get_system_metrics(self, hours: int = 1) -> List[Dict[str, Any]]:
        """獲取系統指標"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            metrics.to_dict() 
            for metrics in self.system_metrics 
            if metrics.timestamp >= cutoff_time
        ]
    
    def get_youtube_metrics(self, hours: int = 24) -> List[Dict[str, Any]]:
        """獲取 YouTube 處理指標"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            metrics.to_dict() 
            for metrics in self.youtube_metrics 
            if metrics.timestamp >= cutoff_time
        ]
    
    def get_api_metrics(self, hours: int = 24) -> List[Dict[str, Any]]:
        """獲取 API 指標"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            metrics.to_dict() 
            for metrics in self.api_metrics 
            if metrics.timestamp >= cutoff_time
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取統計資料"""
        # 計算成功率
        youtube_stats = dict(self.stats['youtube_processing'])
        for stage in ['metadata_extraction', 'audio_download', 'video_download', 'transcription']:
            total = youtube_stats.get(f'{stage}_total', 0)
            success = youtube_stats.get(f'{stage}_success', 0)
            if total > 0:
                youtube_stats[f'{stage}_success_rate'] = (success / total) * 100
        
        # API 統計
        api_stats = dict(self.stats['api_requests'])
        total_requests = api_stats.get('total', 0)
        if total_requests > 0:
            success_requests = sum(
                count for key, count in api_stats.items() 
                if key.startswith('status_2')  # 2xx 狀態碼
            )
            api_stats['success_rate'] = (success_requests / total_requests) * 100
        
        return {
            'youtube_processing': youtube_stats,
            'api_requests': api_stats,
            'errors': dict(self.stats['errors']),
            'warnings': dict(self.stats['warnings']),
            'system': {
                'monitoring_active': self._is_monitoring,
                'metrics_count': {
                    'system': len(self.system_metrics),
                    'youtube': len(self.youtube_metrics),
                    'api': len(self.api_metrics)
                }
            }
        }
    
    async def export_metrics(self, file_path: str, hours: int = 24):
        """匯出指標到檔案"""
        try:
            data = {
                'export_time': datetime.now().isoformat(),
                'hours': hours,
                'system_metrics': self.get_system_metrics(hours),
                'youtube_metrics': self.get_youtube_metrics(hours),
                'api_metrics': self.get_api_metrics(hours),
                'statistics': self.get_statistics()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.performance_logger.logger.info(f"指標已匯出到: {file_path}")
            
        except Exception as e:
            self.error_tracker.track_error(e, {'context': 'export_metrics', 'file_path': file_path})


class AlertManager:
    """告警管理器"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.config = get_config()
        self.error_tracker = get_error_tracker()
        
        # 告警狀態追蹤
        self.alert_states = {}
        self.alert_cooldowns = {}
    
    async def check_alerts(self):
        """檢查告警條件"""
        current_time = datetime.now()
        
        # 檢查系統資源告警
        await self._check_system_alerts(current_time)
        
        # 檢查 YouTube 處理告警
        await self._check_youtube_alerts(current_time)
        
        # 檢查 API 告警
        await self._check_api_alerts(current_time)
    
    async def _check_system_alerts(self, current_time: datetime):
        """檢查系統告警"""
        if not self.metrics_collector.system_metrics:
            return
        
        latest_metrics = self.metrics_collector.system_metrics[-1]
        
        # 高 CPU 使用率告警
        if latest_metrics.cpu_percent > 90:
            await self._trigger_alert(
                'high_cpu', 
                f'CPU 使用率極高: {latest_metrics.cpu_percent:.1f}%',
                current_time
            )
        
        # 高記憶體使用率告警
        if latest_metrics.memory_percent > 95:
            await self._trigger_alert(
                'high_memory',
                f'記憶體使用率極高: {latest_metrics.memory_percent:.1f}%',
                current_time
            )
        
        # 磁碟空間不足告警
        if latest_metrics.disk_percent > 95:
            await self._trigger_alert(
                'disk_full',
                f'磁碟空間不足: {latest_metrics.disk_percent:.1f}%',
                current_time
            )
    
    async def _check_youtube_alerts(self, current_time: datetime):
        """檢查 YouTube 處理告警"""
        # 檢查最近1小時的失敗率
        recent_metrics = [
            m for m in self.metrics_collector.youtube_metrics
            if m.timestamp >= current_time - timedelta(hours=1)
        ]
        
        if len(recent_metrics) >= 10:  # 至少有10次處理
            failed_count = sum(1 for m in recent_metrics if not m.success)
            failure_rate = (failed_count / len(recent_metrics)) * 100
            
            if failure_rate > 50:  # 失敗率超過50%
                await self._trigger_alert(
                    'youtube_high_failure_rate',
                    f'YouTube 處理失敗率過高: {failure_rate:.1f}%',
                    current_time
                )
    
    async def _check_api_alerts(self, current_time: datetime):
        """檢查 API 告警"""
        # 檢查最近1小時的錯誤率
        recent_metrics = [
            m for m in self.metrics_collector.api_metrics
            if m.timestamp >= current_time - timedelta(hours=1)
        ]
        
        if len(recent_metrics) >= 50:  # 至少有50次請求
            error_count = sum(1 for m in recent_metrics if m.status_code >= 500)
            error_rate = (error_count / len(recent_metrics)) * 100
            
            if error_rate > 10:  # 錯誤率超過10%
                await self._trigger_alert(
                    'api_high_error_rate',
                    f'API 錯誤率過高: {error_rate:.1f}%',
                    current_time
                )
    
    async def _trigger_alert(self, alert_type: str, message: str, current_time: datetime):
        """觸發告警"""
        # 檢查冷卻時間
        if alert_type in self.alert_cooldowns:
            if current_time < self.alert_cooldowns[alert_type]:
                return
        
        # 記錄告警
        self.error_tracker.track_warning(
            f"告警觸發: {message}",
            {'alert_type': alert_type},
            warning_code=f'ALERT_{alert_type.upper()}'
        )
        
        # 設定冷卻時間 (30分鐘)
        self.alert_cooldowns[alert_type] = current_time + timedelta(minutes=30)
        
        # 更新告警狀態
        self.alert_states[alert_type] = {
            'active': True,
            'message': message,
            'triggered_at': current_time.isoformat()
        }


# 全域監控實例
metrics_collector = MetricsCollector()
alert_manager = AlertManager(metrics_collector)


def get_metrics_collector() -> MetricsCollector:
    """獲取指標收集器"""
    return metrics_collector


def get_alert_manager() -> AlertManager:
    """獲取告警管理器"""
    return alert_manager


async def start_monitoring():
    """啟動監控系統"""
    await metrics_collector.start_monitoring()


async def stop_monitoring():
    """停止監控系統"""
    await metrics_collector.stop_monitoring()