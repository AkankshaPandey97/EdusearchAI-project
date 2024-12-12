from typing import Dict, Any, TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager
from backend.rag.context_manager import ContextWindowManager, ContextConfig

class WorkflowState(TypedDict):
    context: Dict[str, Any]
    query: str
    results: List[Any]
    errors: List[WorkflowError]
    context_metrics: Dict[str, Any]

class BaseWorkflow:
    def __init__(self):
        self.graph = StateGraph(WorkflowState)
        self.recovery_handlers = {}
        self.state_manager = StateManager()
        self.context_manager = ContextWindowManager()
        
        # Register common error handlers
        self.state_manager.error_handler.register_callback(
            ErrorCategory.VALIDATION, self._handle_validation_error
        )
        self.state_manager.error_handler.register_callback(
            ErrorCategory.SYSTEM, self._handle_system_error
        )
    
    async def _handle_validation_error(self, error: WorkflowError) -> bool:
        """Handle validation errors"""
        if error.severity != ErrorSeverity.CRITICAL:
            await self.state_manager.update_state("validation_state", {})
            return True
        return False

    async def _handle_system_error(self, error: WorkflowError) -> bool:
        """Handle system-level errors"""
        if error.severity != ErrorSeverity.CRITICAL:
            await self.state_manager.update_state("workflow_state", {})
            return True
        return False

    def create_workflow(self) -> StateGraph:
        """Create and return the workflow graph"""
        raise NotImplementedError
    
    def _create_error_response(self) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            "success": False,
            "errors": [error.dict() for error in self.state_manager.errors],
            "context": self.state_manager.current_state,
            "context_metrics": self.state_manager.get_context_metrics()
        }
    
    async def execute(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            workflow = self.create_workflow()
            result = await workflow.arun(initial_state)
            
            if self.state_manager.errors:  # Check for any errors
                return self._create_error_response()
                
            return {
                "success": True,
                "results": result,
                "context_metrics": self.state_manager.get_context_metrics()
            }
            
        except Exception as e:
            error = WorkflowError(
                code="WORKFLOW_EXECUTION_ERROR",
                message=str(e),
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.SYSTEM,
                context={"initial_state": initial_state}
            )
            await self.state_manager.handle_error(error)
            return self._create_error_response()
    
    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> WorkflowState:
        """Convert and handle general exceptions"""
        workflow_error = WorkflowError(
            code=error.__class__.__name__,
            message=str(error),
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.PROCESSING,
            context=context
        )
        await self.state_manager.handle_error(workflow_error)
        return {
            "errors": [workflow_error],  # Changed from dict() to direct WorkflowError
            **self.state_manager.get_current_state()
        }
    
    async def _process_with_context(
        self,
        state: WorkflowState,
        context_config: Optional[ContextConfig] = None
    ) -> WorkflowState:
        try:
            if "documents" in state:
                optimized_docs = await self.context_manager.optimize_context(
                    docs=state["documents"],
                    query=state["query"],
                    config=context_config
                )
                state["documents"] = optimized_docs
                
                # Update context metrics
                self.state_manager.update_context_metrics(
                    total_tokens=len(optimized_docs),
                    used_tokens=sum(len(doc.page_content) for doc in optimized_docs)
                )
                
                state["context_metrics"] = self.state_manager.get_context_metrics()
                
            return state
            
        except Exception as e:
            error = WorkflowError(
                code="CONTEXT_PROCESSING_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.PROCESSING,
                context={"state": state}
            )
            await self.state_manager.handle_error(error)
            return {
                **state,
                "errors": [error]  # Changed from dict() to direct WorkflowError
            }