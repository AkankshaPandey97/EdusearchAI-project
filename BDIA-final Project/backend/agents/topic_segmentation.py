from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentInput, AgentOutput
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory

class TopicSegment(BaseModel):
    topic: str
    content: str
    keywords: List[str]
    start_index: int
    end_index: int
    confidence: float = Field(ge=0.0, le=1.0)

class SegmentationInput(AgentInput):
    content: str
    min_segment_length: int = 100
    max_segments: int = 10

class SegmentationOutput(AgentOutput):
    segments: List[TopicSegment]
    error: Optional[WorkflowError] = None

class TopicSegmentationAgent(BaseAgent):
    def _create_system_prompt(self) -> str:
        return """You are a content segmentation expert. Analyze the content and:
        1. Identify distinct topics and themes
        2. Create logical segments with clear boundaries
        3. Extract relevant keywords for each segment
        4. Maintain content coherence within segments"""
    
    async def _process_implementation(self, input_data: SegmentationInput) -> SegmentationOutput:
        try:
            # Get topic segments from LLM
            response = await self._execute_with_retry(
                self.llm.apredict_messages,
                messages=[
                    ("system", self._create_system_prompt()),
                    ("human", f"""
                    Content: {input_data.content}
                    Min Segment Length: {input_data.min_segment_length}
                    Max Segments: {input_data.max_segments}
                    
                    Segment this content into topics. For each segment, provide:
                    - Topic title
                    - Content
                    - Keywords
                    - Start and end positions
                    """)
                ]
            )
            
            # Parse segments from response
            segments = []
            # Add parsing logic here based on LLM response format
            
            return SegmentationOutput(
                success=True,
                data={"segments": segments},
                segments=segments
            )
            
        except Exception as e:
            error = WorkflowError(
                code="TOPIC_SEGMENTATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={
                    "content_length": len(input_data.content),
                    "max_segments": input_data.max_segments
                }
            )
            # Let BaseAgent handle the error through state_manager
            raise error
