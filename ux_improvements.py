#!/usr/bin/env python3
"""
使用者體驗改進模組
提供載入狀態、回饋機制和互動改進功能
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    """通知類型"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    LOADING = "loading"

class LoadingState(Enum):
    """載入狀態"""
    IDLE = "idle"
    LOADING = "loading"
    SUCCESS = "success"
    ERROR = "error"

@dataclass
class Notification:
    """通知訊息"""
    id: str
    type: NotificationType
    title: str
    message: str
    timestamp: datetime
    duration: Optional[int] = None  # 顯示持續時間（秒）
    actions: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'id': self.id,
            'type': self.type.value,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'duration': self.duration,
            'actions': self.actions or []
        }

@dataclass
class LoadingProgress:
    """載入進度"""
    current: int
    total: int
    message: str
    stage: str
    estimated_time_remaining: Optional[int] = None
    
    @property
    def percentage(self) -> float:
        """進度百分比"""
        if self.total == 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'current': self.current,
            'total': self.total,
            'percentage': self.percentage,
            'message': self.message,
            'stage': self.stage,
            'estimated_time_remaining': self.estimated_time_remaining
        }

class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.notifications: Dict[str, Notification] = {}
        self.subscribers: List[Callable] = []
    
    def subscribe(self, callback: Callable):
        """訂閱通知"""
        self.subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable):
        """取消訂閱通知"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    async def _notify_subscribers(self, notification: Notification):
        """通知所有訂閱者"""
        for callback in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(notification)
                else:
                    callback(notification)
            except Exception as e:
                logger.error(f"通知訂閱者時發生錯誤: {e}")
    
    async def add_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        duration: Optional[int] = None,
        actions: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """新增通知"""
        notification_id = f"notif_{int(time.time() * 1000)}"
        
        notification = Notification(
            id=notification_id,
            type=notification_type,
            title=title,
            message=message,
            timestamp=datetime.now(),
            duration=duration,
            actions=actions
        )
        
        self.notifications[notification_id] = notification
        await self._notify_subscribers(notification)
        
        # 如果有持續時間，設定自動移除
        if duration:
            asyncio.create_task(self._auto_remove_notification(notification_id, duration))
        
        return notification_id
    
    async def _auto_remove_notification(self, notification_id: str, delay: int):
        """自動移除通知"""
        await asyncio.sleep(delay)
        self.remove_notification(notification_id)
    
    def remove_notification(self, notification_id: str):
        """移除通知"""
        if notification_id in self.notifications:
            del self.notifications[notification_id]
    
    def get_notifications(self) -> List[Dict[str, Any]]:
        """取得所有通知"""
        return [notif.to_dict() for notif in self.notifications.values()]
    
    def clear_notifications(self):
        """清除所有通知"""
        self.notifications.clear()

class LoadingStateManager:
    """載入狀態管理器"""
    
    def __init__(self):
        self.states: Dict[str, LoadingState] = {}
        self.progress: Dict[str, LoadingProgress] = {}
        self.subscribers: List[Callable] = []
    
    def subscribe(self, callback: Callable):
        """訂閱狀態變更"""
        self.subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable):
        """取消訂閱狀態變更"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    async def _notify_subscribers(self, task_id: str, state: LoadingState, progress: Optional[LoadingProgress] = None):
        """通知所有訂閱者"""
        for callback in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task_id, state, progress)
                else:
                    callback(task_id, state, progress)
            except Exception as e:
                logger.error(f"通知載入狀態訂閱者時發生錯誤: {e}")
    
    async def set_loading(self, task_id: str, message: str = "載入中..."):
        """設定載入狀態"""
        self.states[task_id] = LoadingState.LOADING
        progress = LoadingProgress(
            current=0,
            total=100,
            message=message,
            stage="initializing"
        )
        self.progress[task_id] = progress
        await self._notify_subscribers(task_id, LoadingState.LOADING, progress)
    
    async def update_progress(
        self,
        task_id: str,
        current: int,
        total: int,
        message: str,
        stage: str = "processing",
        estimated_time_remaining: Optional[int] = None
    ):
        """更新進度"""
        if task_id in self.states and self.states[task_id] == LoadingState.LOADING:
            progress = LoadingProgress(
                current=current,
                total=total,
                message=message,
                stage=stage,
                estimated_time_remaining=estimated_time_remaining
            )
            self.progress[task_id] = progress
            await self._notify_subscribers(task_id, LoadingState.LOADING, progress)
    
    async def set_success(self, task_id: str, message: str = "完成"):
        """設定成功狀態"""
        self.states[task_id] = LoadingState.SUCCESS
        if task_id in self.progress:
            self.progress[task_id].message = message
            self.progress[task_id].current = self.progress[task_id].total
        await self._notify_subscribers(task_id, LoadingState.SUCCESS, self.progress.get(task_id))
    
    async def set_error(self, task_id: str, message: str = "發生錯誤"):
        """設定錯誤狀態"""
        self.states[task_id] = LoadingState.ERROR
        if task_id in self.progress:
            self.progress[task_id].message = message
        await self._notify_subscribers(task_id, LoadingState.ERROR, self.progress.get(task_id))
    
    def get_state(self, task_id: str) -> Optional[LoadingState]:
        """取得載入狀態"""
        return self.states.get(task_id)
    
    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """取得進度資訊"""
        progress = self.progress.get(task_id)
        return progress.to_dict() if progress else None
    
    def cleanup_task(self, task_id: str):
        """清理任務狀態"""
        self.states.pop(task_id, None)
        self.progress.pop(task_id, None)

class FeedbackCollector:
    """回饋收集器"""
    
    def __init__(self):
        self.feedback_data: List[Dict[str, Any]] = []
    
    async def collect_user_feedback(
        self,
        task_id: str,
        rating: int,
        comment: str = "",
        category: str = "general",
        user_agent: str = "",
        additional_data: Dict[str, Any] = None
    ):
        """收集使用者回饋"""
        feedback = {
            'id': f"feedback_{int(time.time() * 1000)}",
            'task_id': task_id,
            'rating': rating,
            'comment': comment,
            'category': category,
            'user_agent': user_agent,
            'timestamp': datetime.now().isoformat(),
            'additional_data': additional_data or {}
        }
        
        self.feedback_data.append(feedback)
        
        # 記錄到日誌
        logger.info(f"收到使用者回饋: 任務 {task_id}, 評分 {rating}/5")
        
        return feedback['id']
    
    def get_feedback_summary(self) -> Dict[str, Any]:
        """取得回饋摘要"""
        if not self.feedback_data:
            return {
                'total_feedback': 0,
                'average_rating': 0.0,
                'rating_distribution': {},
                'recent_feedback': []
            }
        
        ratings = [fb['rating'] for fb in self.feedback_data]
        rating_distribution = {}
        for rating in range(1, 6):
            rating_distribution[str(rating)] = ratings.count(rating)
        
        return {
            'total_feedback': len(self.feedback_data),
            'average_rating': sum(ratings) / len(ratings),
            'rating_distribution': rating_distribution,
            'recent_feedback': self.feedback_data[-10:]  # 最近 10 個回饋
        }

class InteractionTracker:
    """互動追蹤器"""
    
    def __init__(self):
        self.interactions: List[Dict[str, Any]] = []
        self.session_data: Dict[str, Any] = {}
    
    async def track_interaction(
        self,
        action: str,
        element: str,
        session_id: str,
        additional_data: Dict[str, Any] = None
    ):
        """追蹤使用者互動"""
        interaction = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'element': element,
            'session_id': session_id,
            'additional_data': additional_data or {}
        }
        
        self.interactions.append(interaction)
        
        # 更新會話資料
        if session_id not in self.session_data:
            self.session_data[session_id] = {
                'start_time': datetime.now().isoformat(),
                'interaction_count': 0,
                'last_activity': datetime.now().isoformat()
            }
        
        self.session_data[session_id]['interaction_count'] += 1
        self.session_data[session_id]['last_activity'] = datetime.now().isoformat()
    
    def get_interaction_analytics(self) -> Dict[str, Any]:
        """取得互動分析"""
        if not self.interactions:
            return {
                'total_interactions': 0,
                'unique_sessions': 0,
                'popular_actions': {},
                'popular_elements': {}
            }
        
        actions = [interaction['action'] for interaction in self.interactions]
        elements = [interaction['element'] for interaction in self.interactions]
        
        action_counts = {}
        for action in actions:
            action_counts[action] = action_counts.get(action, 0) + 1
        
        element_counts = {}
        for element in elements:
            element_counts[element] = element_counts.get(element, 0) + 1
        
        return {
            'total_interactions': len(self.interactions),
            'unique_sessions': len(self.session_data),
            'popular_actions': dict(sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            'popular_elements': dict(sorted(element_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        }

class UXManager:
    """使用者體驗管理器"""
    
    def __init__(self):
        self.notification_manager = NotificationManager()
        self.loading_manager = LoadingStateManager()
        self.feedback_collector = FeedbackCollector()
        self.interaction_tracker = InteractionTracker()
    
    # 通知相關方法
    async def show_success(self, title: str, message: str, duration: int = 5):
        """顯示成功通知"""
        return await self.notification_manager.add_notification(
            NotificationType.SUCCESS, title, message, duration
        )
    
    async def show_error(self, title: str, message: str, duration: int = 10):
        """顯示錯誤通知"""
        return await self.notification_manager.add_notification(
            NotificationType.ERROR, title, message, duration
        )
    
    async def show_warning(self, title: str, message: str, duration: int = 8):
        """顯示警告通知"""
        return await self.notification_manager.add_notification(
            NotificationType.WARNING, title, message, duration
        )
    
    async def show_info(self, title: str, message: str, duration: int = 5):
        """顯示資訊通知"""
        return await self.notification_manager.add_notification(
            NotificationType.INFO, title, message, duration
        )
    
    # 載入狀態相關方法
    async def start_loading(self, task_id: str, message: str = "處理中..."):
        """開始載入"""
        await self.loading_manager.set_loading(task_id, message)
    
    async def update_loading_progress(
        self,
        task_id: str,
        current: int,
        total: int,
        message: str,
        stage: str = "processing"
    ):
        """更新載入進度"""
        await self.loading_manager.update_progress(task_id, current, total, message, stage)
    
    async def finish_loading_success(self, task_id: str, message: str = "完成"):
        """完成載入（成功）"""
        await self.loading_manager.set_success(task_id, message)
    
    async def finish_loading_error(self, task_id: str, message: str = "發生錯誤"):
        """完成載入（錯誤）"""
        await self.loading_manager.set_error(task_id, message)
    
    # 回饋相關方法
    async def collect_feedback(
        self,
        task_id: str,
        rating: int,
        comment: str = "",
        category: str = "general"
    ):
        """收集回饋"""
        return await self.feedback_collector.collect_user_feedback(
            task_id, rating, comment, category
        )
    
    # 互動追蹤相關方法
    async def track_user_interaction(
        self,
        action: str,
        element: str,
        session_id: str,
        data: Dict[str, Any] = None
    ):
        """追蹤使用者互動"""
        await self.interaction_tracker.track_interaction(action, element, session_id, data)
    
    # 綜合報告
    def get_ux_analytics(self) -> Dict[str, Any]:
        """取得 UX 分析報告"""
        return {
            'notifications': self.notification_manager.get_notifications(),
            'feedback_summary': self.feedback_collector.get_feedback_summary(),
            'interaction_analytics': self.interaction_tracker.get_interaction_analytics(),
            'timestamp': datetime.now().isoformat()
        }

# 全域 UX 管理器實例
ux_manager = UXManager()

def get_ux_manager() -> UXManager:
    """取得 UX 管理器實例"""
    return ux_manager

# WebSocket 訊息輔助函數
async def send_websocket_notification(
    websocket_manager,
    client_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: Dict[str, Any] = None
):
    """發送 WebSocket 通知"""
    message_data = {
        'type': 'notification',
        'notification_type': notification_type,
        'title': title,
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'data': data or {}
    }
    
    try:
        await websocket_manager.send_json(client_id, message_data)
    except Exception as e:
        logger.error(f"發送 WebSocket 通知失敗: {e}")

async def send_websocket_progress(
    websocket_manager,
    client_id: str,
    task_id: str,
    progress: LoadingProgress
):
    """發送 WebSocket 進度更新"""
    message_data = {
        'type': 'progress_update',
        'task_id': task_id,
        **progress.to_dict()
    }
    
    try:
        await websocket_manager.send_json(client_id, message_data)
    except Exception as e:
        logger.error(f"發送 WebSocket 進度更新失敗: {e}")

# UX 改進裝飾器
def track_user_action(action: str, element: str):
    """追蹤使用者動作裝飾器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 嘗試從請求中取得 session_id
            session_id = kwargs.get('session_id', 'unknown')
            
            # 追蹤互動
            await ux_manager.track_user_interaction(action, element, session_id)
            
            # 執行原函數
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def with_loading_state(task_id_key: str = 'task_id'):
    """載入狀態裝飾器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            task_id = kwargs.get(task_id_key, f"task_{int(time.time())}")
            
            try:
                # 開始載入
                await ux_manager.start_loading(task_id, "處理中...")
                
                # 執行函數
                result = await func(*args, **kwargs)
                
                # 完成載入
                await ux_manager.finish_loading_success(task_id, "完成")
                
                return result
            except Exception as e:
                # 錯誤載入
                await ux_manager.finish_loading_error(task_id, f"錯誤: {str(e)}")
                raise
        return wrapper
    return decorator