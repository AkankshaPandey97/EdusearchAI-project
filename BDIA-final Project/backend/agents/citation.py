from typing import List, Optional
from pydantic import BaseModel
from .base import BaseAgent, AgentInput, AgentOutput
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory

class Citation(BaseModel):
    text: str
    source: str
    page: Optional[int]
    confidence: float

class CitationInput(AgentInput):
    content: str
    style: str = "APA"

class CitationOutput(AgentOutput):
    citations: List[Citation]
    error: Optional[WorkflowError] = None

class CitationAgent(BaseAgent):
    def _create_system_prompt(self) -> str:
        return """You are a citation expert. Generate accurate citations 
        following the specified style guide."""
    
    async def _process_implementation(self, input_data: CitationInput) -> CitationOutput:
        """Implementation of citation processing"""
        try:
            response = await self.llm.apredict_messages([
                ("system", self._create_system_prompt()),
                ("human", f"""
                Content: {input_data.content}
                Style: {input_data.style}
                
                Generate appropriate citations.
                """)
            ])
            
            # Parse citations from response
            citation = Citation(
                text=response,
                source=input_data.metadata.get("source", "Unknown"),
                page=input_data.metadata.get("page"),
                confidence=0.9
            )
            
            return CitationOutput(
                success=True,
                data={"citations": [citation]},
                citations=[citation]
            )
            
        except Exception as e:
            error = WorkflowError(
                code="CITATION_PROCESSING_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={
                    "content": input_data.content,
                    "style": input_data.style
                }
            )
            # Let BaseAgent handle the error through state_manager
            raise error
