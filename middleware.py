"""
API 錯誤處理中介軟體
提供統一的錯誤處理、日誌記錄和回應格式化功能
"""

import time
import logging
import traceback
from typing import Callable, Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from error_handling import HistoryAPIException, ErrorCodes

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """API 錯誤處理中介軟體"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.error_messages = {
            # 中文錯誤訊息對照表
            ErrorCodes.INVALID_INPUT: "輸入資料無效",
            ErrorCodes.VALIDATION_ERROR: "資料驗證失敗",
            ErrorCodes.INTERNAL_ERROR: "系統內部錯誤",
            ErrorCodes.TASK_NOT_FOUND: "任務不存在",
            ErrorCodes.TASK_CREATION_FAILED: "任務建立失敗",
            ErrorCodes.TASK_UPDATE_FAILED: "任務更新失敗",
            ErrorCodes.TASK_DELETE_FAILED: "任務刪除失敗",
            ErrorCodes.FILE_NOT_FOUND: "檔案不存在",
            ErrorCodes.FILE_ACCESS_DENIED: "檔案存取被拒絕",
            ErrorCodes.FILE_TOO_LARGE: "檔案過大",
            ErrorCodes.INVALID_FILE_TYPE: "檔案類型無效",
            ErrorCodes.FILE_CORRUPTED: "檔案已損壞",
            ErrorCodes.DATABASE_ERROR: "資料庫錯誤",
            ErrorCodes.DATABASE_CONNECTION_FAILED: "資料庫連線失敗",
            ErrorCodes.PERMISSION_DENIED: "權限不足",
            ErrorCodes.UNAUTHORIZED_ACCESS: "未授權存取",
            ErrorCodes.DISK_FULL: "磁碟空間不足",
            ErrorCodes.MEMORY_INSUFFICIENT: "記憶體不足",
            ErrorCodes.NETWORK_ERROR: "網路錯誤",
            ErrorCodes.TIMEOUT_ERROR: "請求逾時"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        處理請求並捕獲例外
        
        Args:
            request: HTTP 請求
            call_next: 下一個中介軟體或路由處理器
            
        Returns:
            Response: HTTP 回應
        """
        start_time = time.time()
        request_id = self._generate_request_id()
        
        # 記錄請求開始
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - 開始處理請求",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": self._get_client_ip(request)
            }
        )
        
        try:
            # 執行請求處理
            response = await call_next(request)
            
            # 計算處理時間
            process_time = time.time() - start_time
            
            # 記錄成功回應
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"處理完成 {response.status_code} ({process_time:.3f}s)",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "process_time": process_time
                }
            )
            
            # 添加回應標頭
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except HistoryAPIException as e:
            # 處理自訂 API 例外
            return await self._handle_api_exception(request, e, request_id, start_time)
            
        except HTTPException as e:
            # 處理 FastAPI HTTP 例外
            return await self._handle_http_exception(request, e, request_id, start_time)
            
        except Exception as e:
            # 處理未預期的例外
            return await self._handle_unexpected_exception(request, e, request_id, start_time)
    
    async def _handle_api_exception(
        self, 
        request: Request, 
        exc: HistoryAPIException, 
        request_id: str, 
        start_time: float
    ) -> JSONResponse:
        """
        處理自訂 API 例外
        
        Args:
            request: HTTP 請求
            exc: 自訂 API 例外
            request_id: 請求 ID
            start_time: 請求開始時間
            
        Returns:
            JSONResponse: 錯誤回應
        """
        process_time = time.time() - start_time
        
        # 記錄錯誤
        logger.warning(
            f"[{request_id}] API 例外: {exc.error_code} - {exc.detail}",
            extra={
                "request_id": request_id,
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "context": exc.context,
                "process_time": process_time
            }
        )
        
        # 建立錯誤回應
        error_response = {
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.detail,
                "user_message": self.error_messages.get(exc.error_code, exc.detail),
                "timestamp": exc.timestamp,
                "request_id": request_id
            }
        }
        
        # 在開發模式下添加額外的除錯資訊
        if logger.level <= logging.DEBUG and exc.context:
            error_response["error"]["context"] = exc.context
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response,
            headers={
                "X-Request-ID": request_id,
                "X-Process-Time": f"{process_time:.3f}"
            }
        )
    
    async def _handle_http_exception(
        self, 
        request: Request, 
        exc: HTTPException, 
        request_id: str, 
        start_time: float
    ) -> JSONResponse:
        """
        處理 FastAPI HTTP 例外
        
        Args:
            request: HTTP 請求
            exc: HTTP 例外
            request_id: 請求 ID
            start_time: 請求開始時間
            
        Returns:
            JSONResponse: 錯誤回應
        """
        process_time = time.time() - start_time
        
        # 記錄錯誤
        logger.warning(
            f"[{request_id}] HTTP 例外: {exc.status_code} - {exc.detail}",
            extra={
                "request_id": request_id,
                "status_code": exc.status_code,
                "process_time": process_time
            }
        )
        
        # 建立錯誤回應
        error_response = {
            "success": False,
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "user_message": self._get_user_friendly_message(exc.status_code),
                "timestamp": time.time(),
                "request_id": request_id
            }
        }
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response,
            headers={
                "X-Request-ID": request_id,
                "X-Process-Time": f"{process_time:.3f}"
            }
        )
    
    async def _handle_unexpected_exception(
        self, 
        request: Request, 
        exc: Exception, 
        request_id: str, 
        start_time: float
    ) -> JSONResponse:
        """
        處理未預期的例外
        
        Args:
            request: HTTP 請求
            exc: 例外物件
            request_id: 請求 ID
            start_time: 請求開始時間
            
        Returns:
            JSONResponse: 錯誤回應
        """
        process_time = time.time() - start_time
        
        # 記錄嚴重錯誤
        logger.error(
            f"[{request_id}] 未預期的例外: {type(exc).__name__} - {str(exc)}",
            extra={
                "request_id": request_id,
                "exception_type": type(exc).__name__,
                "process_time": process_time,
                "traceback": traceback.format_exc()
            }
        )
        
        # 建立錯誤回應（不洩露內部錯誤詳情）
        error_response = {
            "success": False,
            "error": {
                "code": ErrorCodes.INTERNAL_ERROR,
                "message": "系統發生內部錯誤，請稍後再試",
                "user_message": "系統暫時無法處理您的請求，請稍後再試",
                "timestamp": time.time(),
                "request_id": request_id
            }
        }
        
        # 在開發模式下添加詳細錯誤資訊
        if logger.level <= logging.DEBUG:
            error_response["error"]["debug_info"] = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)
            }
        
        return JSONResponse(
            status_code=500,
            content=error_response,
            headers={
                "X-Request-ID": request_id,
                "X-Process-Time": f"{process_time:.3f}"
            }
        )
    
    def _generate_request_id(self) -> str:
        """
        生成請求 ID
        
        Returns:
            str: 唯一的請求 ID
        """
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _get_client_ip(self, request: Request) -> str:
        """
        取得客戶端 IP 位址
        
        Args:
            request: HTTP 請求
            
        Returns:
            str: 客戶端 IP 位址
        """
        # 檢查代理伺服器標頭
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 回退到直接連線 IP
        return request.client.host if request.client else "unknown"
    
    def _get_user_friendly_message(self, status_code: int) -> str:
        """
        根據 HTTP 狀態碼取得使用者友善的錯誤訊息
        
        Args:
            status_code: HTTP 狀態碼
            
        Returns:
            str: 使用者友善的錯誤訊息
        """
        messages = {
            400: "請求格式錯誤，請檢查輸入資料",
            401: "需要身份驗證",
            403: "沒有權限執行此操作",
            404: "請求的資源不存在",
            405: "不支援的請求方法",
            409: "資源衝突",
            413: "請求內容過大",
            422: "請求資料格式錯誤",
            429: "請求過於頻繁，請稍後再試",
            500: "伺服器內部錯誤",
            502: "服務暫時無法使用",
            503: "服務暫時無法使用",
            504: "請求逾時"
        }
        
        return messages.get(status_code, "發生未知錯誤")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """請求日誌記錄中介軟體"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        記錄請求和回應資訊
        
        Args:
            request: HTTP 請求
            call_next: 下一個中介軟體或路由處理器
            
        Returns:
            Response: HTTP 回應
        """
        start_time = time.time()
        
        # 記錄請求詳情
        request_info = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "client_ip": request.client.host if request.client else "unknown"
        }
        
        # 過濾敏感標頭
        sensitive_headers = ["authorization", "cookie", "x-api-key"]
        for header in sensitive_headers:
            if header in request_info["headers"]:
                request_info["headers"][header] = "[REDACTED]"
        
        logger.debug(f"請求詳情: {request_info}")
        
        # 執行請求
        response = await call_next(request)
        
        # 計算處理時間
        process_time = time.time() - start_time
        
        # 記錄回應資訊
        response_info = {
            "status_code": response.status_code,
            "process_time": f"{process_time:.3f}s"
        }
        
        logger.debug(f"回應詳情: {response_info}")
        
        return response

class SecurityMiddleware(BaseHTTPMiddleware):
    """安全性中介軟體"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.max_request_size = 100 * 1024 * 1024  # 100MB
        self.rate_limit_requests = 100  # 每分鐘最大請求數
        self.rate_limit_window = 60  # 時間窗口（秒）
        self.client_requests: Dict[str, list] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        執行安全性檢查
        
        Args:
            request: HTTP 請求
            call_next: 下一個中介軟體或路由處理器
            
        Returns:
            Response: HTTP 回應
        """
        client_ip = self._get_client_ip(request)
        
        # 檢查請求大小
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            return JSONResponse(
                status_code=413,
                content={
                    "success": False,
                    "error": {
                        "code": "REQUEST_TOO_LARGE",
                        "message": f"請求內容過大，最大允許 {self.max_request_size / 1024 / 1024}MB"
                    }
                }
            )
        
        # 簡單的速率限制
        if self._is_rate_limited(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "請求過於頻繁，請稍後再試"
                    }
                }
            )
        
        # 執行請求
        response = await call_next(request)
        
        # 添加安全性標頭
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """取得客戶端 IP 位址"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _is_rate_limited(self, client_ip: str) -> bool:
        """
        檢查是否超過速率限制
        
        Args:
            client_ip: 客戶端 IP
            
        Returns:
            bool: 是否超過限制
        """
        current_time = time.time()
        
        # 初始化客戶端請求記錄
        if client_ip not in self.client_requests:
            self.client_requests[client_ip] = []
        
        # 清理過期的請求記錄
        self.client_requests[client_ip] = [
            req_time for req_time in self.client_requests[client_ip]
            if current_time - req_time < self.rate_limit_window
        ]
        
        # 檢查是否超過限制
        if len(self.client_requests[client_ip]) >= self.rate_limit_requests:
            return True
        
        # 記錄當前請求
        self.client_requests[client_ip].append(current_time)
        return False