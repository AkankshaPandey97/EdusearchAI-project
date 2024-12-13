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
        self.summarization_agent = SummarizationAgent()
        self.topic_segmentation_agent = TopicSegmentationAgent()
        self.research_notes_agent = ResearchNotesAgent()
        
    async def segment_content(self, state: WorkflowState) -> WorkflowState:
        """Segment content into topics"""
        try:
            segments = await self.topic_segmentation_agent.process({
                "content": state["context"].get("content", ""),
                "min_segment_length": 100,
                "max_segments": 10
            })
            
            if segments.success:
                state["results"].append({"segments": segments.data})
                return state
            else:
                raise WorkflowError(
                    code="SEGMENTATION_FAILED",
                    message=str(segments.error),
                    severity=ErrorSeverity.MEDIUM,
                    category=ErrorCategory.PROCESSING
                )
                
        except Exception as e:
            error = WorkflowError(
                code="SEGMENTATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={"content_length": len(state["context"].get("content", ""))}
            )
            state["errors"].append(error)
            return state

    async def generate_summaries(self, state: WorkflowState) -> WorkflowState:
        """Generate summaries for each segment"""
        try:
            segments = state["results"][-1].get("segments", [])
            summaries = []
            
            for segment in segments:
                summary = await self.summarization_agent.process({
                    "content": segment["content"],
                    "style": "default"
                })
                
                if summary.success:
                    summaries.append(summary.data)
                else:
                    raise WorkflowError(
                        code="SUMMARY_GENERATION_FAILED",
                        message=str(summary.error),
                        severity=ErrorSeverity.MEDIUM,
                        category=ErrorCategory.PROCESSING
                    )
            
            state["results"].append({"summaries": summaries})
            return state
            
        except Exception as e:
            error = WorkflowError(
                code="SUMMARY_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={"segments_count": len(segments)}
            )
            state["errors"].append(error)
            return state

    def create_workflow(self) -> StateGraph:
        """Create the workflow graph"""
        # Add nodes
        self.graph.add_node("segment", self.segment_content)
        self.graph.add_node("summarize", self.generate_summaries)
        
        # Define edges with conditions
        self.graph.add_conditional_edges(
            "segment",
            lambda x: "summarize" if not x.get("errors") else END
        )
        self.graph.add_edge("summarize", END)
        
        # Set entry point
        self.graph.set_entry_point("segment")
        
        return self.graph.compile()