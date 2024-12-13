from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import time
import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Dict, List
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager

class ResourcePool:
    def __init__(self, max_size: int = 20):
        self._semaphore = asyncio.Semaphore(max_size)
        
    async def acquire(self):
        return await self._semaphore.acquire()
        
    def release(self):
        self._semaphore.release()

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst_limit: int = 10,
        max_concurrent: int = 20
    ):
        super().__init__(app)
        self.state_manager = StateManager()
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.resource_pool = ResourcePool(max_size=max_concurrent)
        self.cleanup_threshold = burst_limit * 10  # More reasonable threshold
        self._semaphore = asyncio.Semaphore(20)        
        self._request_queue = asyncio.Queue()
        self._worker_task = asyncio.create_task(self._process_queue())
        
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        current_time = time.time()
        
        # Periodic cleanup of old entries
        await self._cleanup_old_requests(current_time)
        
        # Clean old requests for this client
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < 60
        ]
        
        # Check burst limit (requests in last 5 seconds)
        recent_requests = len([
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < 5
        ])
        if recent_requests >= self.burst_limit:
            error = WorkflowError(
                code="BURST_LIMIT_EXCEEDED",
                message="Too many requests in short time period",
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.RATE_LIMIT,
                context={"client_ip": client_ip}
            )
            await self.state_manager.add_error(error)
            raise HTTPException(
                status_code=429,
                detail="Burst limit exceeded"
            )
        
        # Check rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            error = WorkflowError(
                code="RATE_LIMIT_EXCEEDED",
                message="Too many requests",
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.RATE_LIMIT,
                context={"client_ip": client_ip}
            )
            await self.state_manager.add_error(error)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded"
            )
        
        try:
            # Acquire resource from pool
            await self.resource_pool.acquire()
            
            # Add current request
            self.requests[client_ip].append(current_time)
            
            # Process request
            response = await call_next(request)
            return response
            
        except Exception as e:
            error = WorkflowError(
                code="REQUEST_PROCESSING_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.SYSTEM,
                context={"client_ip": client_ip}
            )
            await self.state_manager.add_error(error)
            raise
        finally:
            # Release resource back to pool
            self.resource_pool.release()
    
    async def _cleanup_old_requests(self, current_time: float):
        """Cleanup old requests periodically to prevent memory bloat"""
        for ip, requests in list(self.requests.items()):
            if len(requests) > self.cleanup_threshold:
                self.requests[ip] = [
                    req_time for req_time in requests
                    if current_time - req_time < 60
                ]
            if not self.requests[ip]:
                del self.requests[ip]
    
    async def _process_queue(self):
        """Process queued requests"""
        while True:
            try:
                request = await self._request_queue.get()
                current_time = time.time()
                
                # Process cleanup
                await self._cleanup_old_requests(current_time)
                
                self._request_queue.task_done()
            except Exception as e:
                error = WorkflowError(
                    code="QUEUE_PROCESSING_ERROR",
                    message=str(e),
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.SYSTEM,
                    context={}
                )
                await self.state_manager.add_error(error)
                await asyncio.sleep(1)
