from typing import Dict, Any
from backend.workflows.base_workflow import BaseWorkflow, WorkflowState
from backend.agents.topic_segmentation import TopicSegmentationAgent
from backend.agents.summarization import SummarizationAgent
from backend.agents.research_notes import ResearchNotesAgent
from backend.utils.logging import workflow_logger
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory
from langgraph.graph import StateGraph, END

__all__ = ['process_query', 'ContentEnrichmentWorkflow']

async def process_query(content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Process a content query through the enrichment workflow"""
    workflow = ContentEnrichmentWorkflow()
    state = WorkflowState(
        context={"content": content},
        metadata=metadata or {},
        results=[],
        errors=[]
    )
    
    try:
        result = await workflow.execute(state)
        return {
            "success": len(result["errors"]) == 0,
            "results": result["results"],
            "errors": [error.dict() for error in result["errors"]]
        }
    except Exception as e:
        error = WorkflowError(
            code="WORKFLOW_EXECUTION_ERROR",
            message=str(e),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PROCESSING,
            context={"content_length": len(content)}
        )
        return {
            "success": False,
            "results": [],
            "errors": [error.dict()]
        }

class ContentEnrichmentWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__()
        self.segmentation_agent = TopicSegmentationAgent()
        self.summarization_agent = SummarizationAgent()
        self.research_notes_agent = ResearchNotesAgent()
        
    async def segment_content(self, state: WorkflowState) -> WorkflowState:
        try:
            segmentation_input = {
                "content": state["context"]["content"],
                "max_segments": state["metadata"].get("max_segments", 10)
            }
            
            segmentation_result = await self.segmentation_agent.process(segmentation_input)
            
            if not segmentation_result.success:
                raise WorkflowError(
                    code="SEGMENTATION_FAILED",
                    message=str(segmentation_result.error),
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.PROCESSING,
                    context={"input": segmentation_input}
                )
                
            state["results"].append({"segments": segmentation_result.segments})
            return state
            
        except WorkflowError as we:
            await self.state_manager.handle_error(we)
            state["errors"].append(we)
            return state
        except Exception as e:
            error = WorkflowError(
                code="CONTENT_SEGMENTATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.PROCESSING,
                context={"content": state["context"].get("content")}
            )
            await self.state_manager.handle_error(error)
            state["errors"].append(error)
            return state
    
    async def generate_summaries(self, state: WorkflowState) -> WorkflowState:
        try:
            if not state["results"] or "segments" not in state["results"][-1]:
                raise WorkflowError(
                    code="NO_SEGMENTS_FOUND",
                    message="No segments available for summarization",
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.VALIDATION,
                    context={"state": state}
                )
                
            for segment in state["results"][-1]["segments"]:
                summary_input = {
                    "content": segment.content,
                    "style": state["metadata"].get("summary_style", "academic")
                }
                
                summary_result = await self.summarization_agent.process(summary_input)
                
                if not summary_result.success:
                    raise WorkflowError(
                        code="SUMMARIZATION_FAILED",
                        message=str(summary_result.error),
                        severity=ErrorSeverity.MEDIUM,
                        category=ErrorCategory.PROCESSING,
                        context={"segment": segment.dict()}
                    )
                    
                segment.summary = summary_result.summary
                
            return state
            
        except WorkflowError as we:
            await self.state_manager.handle_error(we)
            state["errors"].append(we)
            return state
        except Exception as e:
            error = WorkflowError(
                code="SUMMARIZATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={"segments": len(state["results"][-1]["segments"])}
            )
            await self.state_manager.handle_error(error)
            state["errors"].append(error)
            return state
    
    def create_workflow(self) -> StateGraph:
        # Add nodes
        self.graph.add_node("segment", self.segment_content)
        self.graph.add_node("summarize", self.generate_summaries)
        
        # Define edges
        self.graph.add_edge("segment", "summarize")
        self.graph.add_edge("summarize", END)
        
        # Set entry point
        self.graph.set_entry_point("segment")
        
        return self.graph.compile()