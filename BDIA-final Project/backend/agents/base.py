from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
#from langchain_community.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from backend.utils.llm.base import llm_manager
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager, RetryStrategy
import asyncio

class AgentInput(BaseModel):
    """Base input schema for agents"""
    query: str
    context: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentOutput(BaseModel):
    """Base output schema for agents"""
    success: bool
    data: Dict[str, Any]
    error: Optional[WorkflowError] = None

class BaseAgent(ABC):
    def __init__(self, model_name: str = "gpt-4-turbo-preview"):
        self.llm = llm_manager.get_llm()
        self.state_manager = StateManager()
        self.retry_strategy = RetryStrategy()
        
        # Register common error handlers
        self.state_manager.error_handler.register_callback(
            ErrorCategory.API,
            self._handle_api_error
        )
        self.state_manager.error_handler.register_callback(
            ErrorCategory.PROCESSING,
            self._handle_processing_error
        )
    
    async def _handle_api_error(self, error: WorkflowError) -> bool:
        """Handle API-related errors"""
        if error.should_retry(self.retry_strategy.max_attempts):
            await asyncio.sleep(
                self.retry_strategy.base_delay * 
                (self.retry_strategy.exponential_base ** error.retry_count)
            )
            return True
        return False
    
    async def _handle_processing_error(self, error: WorkflowError) -> bool:
        """Handle processing errors"""
        if error.recoverable:
            await self.state_manager.update_state("processing_state", {})
            return True
        return False

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize the error based on its type"""
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorCategory.API
        elif isinstance(error, ValueError):
            return ErrorCategory.VALIDATION
        return ErrorCategory.PROCESSING
    
    @abstractmethod
    def _create_system_prompt(self) -> str:
        """Create system prompt for the agent"""
        pass
    
    async def _execute_with_retry(self, func, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        error = None
        for attempt in range(self.retry_strategy.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error = WorkflowError(
                    code=e.__class__.__name__,
                    message=str(e),
                    severity=ErrorSeverity.MEDIUM,
                    category=self._categorize_error(e),
                    retry_count=attempt,
                    context={"agent": self.__class__.__name__}
                )
                if not await self.state_manager.handle_error(error):
                    break
                # If error was handled successfully, continue with next attempt
                continue
        # If we get here, all retries failed
        return AgentOutput(
            success=False,
            data={},
            error=error
        )

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """Process the input and return output"""
        try:
            # Update state with input
            await self.state_manager.update_state("input", input_data.dict())
            
            # Execute with retry logic
            result = await self._execute_with_retry(
                self._process_implementation,
                input_data
            )
            
            # Update state with result if successful
            if result.success:
                await self.state_manager.update_state("output", result.dict())
            
            return result
            
        except Exception as e:
            error = WorkflowError(
                code=e.__class__.__name__,
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=self._categorize_error(e),
                context={"agent": self.__class__.__name__, "input": input_data.dict()}
            )
            await self.state_manager.handle_error(error)
            return AgentOutput(
                success=False,
                data={},
                error=error
            )
    
    @abstractmethod
    async def _process_implementation(self, input_data: AgentInput) -> AgentOutput:
        """Implementation of processing logic"""
        pass