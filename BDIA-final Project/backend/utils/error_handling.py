from enum import Enum
from typing import Optional, Dict, Any, List, Type, Callable, Awaitable
from pydantic import BaseModel, Field
import asyncio
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ErrorSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(str, Enum):
    API = "api"
    PROCESSING = "processing"
    RATE_LIMIT = "rate_limit"
    SYSTEM = "system"

class RetryStrategy(BaseModel):
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    exponential_base: float = 2.0

class WorkflowError(BaseModel):
    code: str
    message: str
    severity: ErrorSeverity
    category: ErrorCategory
    timestamp: datetime = Field(default_factory=datetime.now)
    context: Dict[str, Any] = {}
    retry_count: int = 0
    recoverable: bool = True
    
    def should_retry(self, max_retries: int) -> bool:
        return self.recoverable and self.retry_count < max_retries
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ErrorHandler:
    def __init__(self, retry_strategy: RetryStrategy = RetryStrategy()):
        self.retry_strategy = retry_strategy
        self._error_callbacks: Dict[ErrorCategory, List[Callable]] = {
            category: [] for category in ErrorCategory
        }
        
    async def handle_error(self, error: WorkflowError, state_manager: 'StateManager') -> bool:
        """Handle error and return whether it was recovered"""
        logger.error(f"Error occurred: {error.code} - {error.message}", 
                    extra={"error_context": error.context})
        
        # Try registered handlers first
        handlers = self._error_callbacks.get(error.category, [])
        for handler in handlers:
            try:
                if await handler(error):
                    return True
            except Exception as e:
                logger.error(f"Error handler failed: {str(e)}")
        
        # If no handler succeeded, try retry mechanism
        if error.should_retry(self.retry_strategy.max_attempts):
            return await self._retry_operation(error, state_manager)
        
        # Add error to state manager if not resolved
        state_manager.add_error(error)
        return False
    
    async def _retry_operation(self, error: WorkflowError, state_manager: 'StateManager') -> bool:
        delay = self._calculate_delay(error.retry_count)
        error.retry_count += 1
        
        logger.info(f"Retrying operation. Attempt {error.retry_count} after {delay}s delay")
        await asyncio.sleep(delay)
        
        try:
            # Attempt recovery action if defined
            if recovery_action := self._get_recovery_action(error.category):
                await recovery_action(error, state_manager)
                return True
        except Exception as e:
            logger.error(f"Recovery action failed: {str(e)}")
        
        return False
    
    def _calculate_delay(self, retry_count: int) -> float:
        """Calculate exponential backoff delay"""
        delay = self.retry_strategy.base_delay * (
            self.retry_strategy.exponential_base ** retry_count
        )
        return min(delay, self.retry_strategy.max_delay)
    
    def register_callback(self, category: ErrorCategory, callback: callable):
        self._error_callbacks[category].append(callback)
    
    async def _execute_callbacks(self, error: WorkflowError):
        for callback in self._error_callbacks.get(error.category, []):
            await callback(error)
    
    def _get_recovery_action(self, category: ErrorCategory) -> callable:
        return self._error_callbacks.get(category, [])[0]
    
class StateManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.current_state: Dict[str, Any] = {}
        self.errors: List[WorkflowError] = []
        self.context_metrics: Dict[str, Any] = {}
        self._error_handlers: List[Callable] = []
        self.error_handler = ErrorHandler()
    
    async def update_state(self, key: str, value: Any) -> bool:
        try:
            self._validate_state_update(key, value)
            self.current_state[key] = value
            return True
        except Exception as e:
            error = WorkflowError(
                code="STATE_UPDATE_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.SYSTEM,
                context={"key": key}
            )
            return await self.handle_error(error)
    
    def _validate_state_update(self, key: str, value: Any):
        """Validate state updates"""
        if key in self.current_state:
            if not isinstance(value, type(self.current_state[key])):
                raise ValueError(f"Type mismatch for key {key}")
    
    async def handle_error(self, error: WorkflowError) -> bool:
        """Handle error and track it"""
        self.errors.append(error)
        return await self.error_handler.handle_error(error, self)
    
    def update_context_metrics(self, total_tokens: int, used_tokens: int):
        """Update context metrics"""
        self.context_metrics.update({
            "total_tokens": total_tokens,
            "used_tokens": used_tokens,
            "remaining_tokens": total_tokens - used_tokens
        })
    
    def get_context_metrics(self) -> Dict[str, Any]:
        """Get current context metrics"""
        return self.context_metrics.copy()
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get complete current state"""
        return {
            "state": self.current_state,
            "errors": [error.dict() for error in self.errors],
            "context_metrics": self.context_metrics
        } 
    
    async def add_error(self, error: WorkflowError):
        async with self._lock:
            self.errors.append(error)
            await self._notify_error_handlers(error)
    
    async def _notify_error_handlers(self, error: WorkflowError):
        """Notify all registered error handlers of a new error"""
        for handler in self._error_handlers:
            try:
                await handler(error)
            except Exception as e:
                print(f"Error in error handler: {str(e)}")
    
    def register_error_handler(self, handler: Callable):
        """Register a new error handler"""
        self._error_handlers.append(handler)
    
    def get_errors(self) -> List[WorkflowError]:
        """Get all recorded errors"""
        return self._errors.copy()
    
    async def clear_errors(self):
        """Clear all recorded errors"""
        async with self._lock:
            self._errors.clear()