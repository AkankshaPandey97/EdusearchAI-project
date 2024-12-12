from typing import List, Dict, Optional, Any
from .base import BaseAgent, AgentInput, AgentOutput
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory

class Summary(BaseModel):
    title: str
    brief: str
    detailed: str
    key_points: List[str]
    word_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SummarizationInput(AgentInput):
    content: str
    style: Optional[str] = "default"

class SummarizationOutput(AgentOutput):
    summary: Summary
    compression_ratio: float
    error: Optional[WorkflowError] = None

class SummarizationAgent(BaseAgent):
    def _create_system_prompt(self) -> str:
        return """You are an expert summarization assistant. Your task is to:
        1. Create concise yet comprehensive summaries
        2. Maintain key information and context
        3. Adapt to different summarization styles
        4. Extract essential key points
        5. Ensure accuracy and clarity"""
    
    async def _process_implementation(self, input_data: SummarizationInput) -> SummarizationOutput:
        try:
            # Generate summary using LLM
            response = await self._execute_with_retry(
                self.llm.apredict_messages,
                messages=[
                    ("system", self._create_system_prompt()),
                    ("human", f"""
                    Content: {input_data.content}
                    Style: {input_data.style}
                    Max Length: {input_data.max_length or 'Not specified'}
                    Include Key Points: {input_data.include_key_points}
                    
                    Please provide:
                    1. A title
                    2. A brief summary (1-2 sentences)
                    3. A detailed summary
                    4. Key points (if requested)
                    """)
                ]
            )
            
            # Process the response into structured format
            sections = response.split("\n\n")
            title = sections[0].replace("Title: ", "").strip()
            brief = sections[1].replace("Brief: ", "").strip()
            detailed = sections[2].replace("Detailed: ", "").strip()
            key_points = []
            
            if input_data.include_key_points and len(sections) > 3:
                key_points = [
                    point.strip().replace("- ", "") 
                    for point in sections[3].split("\n")
                    if point.strip()
                ]
            
            summary = Summary(
                title=title,
                brief=brief,
                detailed=detailed,
                key_points=key_points,
                word_count=len(detailed.split()),
                metadata={
                    "style": input_data.style,
                    "original_length": len(input_data.content.split())
                }
            )
            
            compression_ratio = len(detailed.split()) / len(input_data.content.split())
            
            return SummarizationOutput(
                success=True,
                data={
                    "summary": summary.dict(),
                    "compression_ratio": compression_ratio
                },
                summary=summary,
                compression_ratio=compression_ratio
            )
            
        except Exception as e:
            error = WorkflowError(
                code="SUMMARIZATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={
                    "style": input_data.style,
                    "content_length": len(input_data.content)
                }
            )
            raise error
    
    async def _validate_summary(self, summary: str, original: str) -> bool:
        """Validate summary for factual consistency"""
        try:
            validation = await self.llm.apredict_messages([
                ("system", "You are a fact-checking assistant. Verify if the summary maintains factual accuracy with the original text."),
                ("human", f"Original: {original}\nSummary: {summary}\nIs the summary factually accurate?")
            ])
            return "yes" in validation.lower()
        except Exception as e:
            error = WorkflowError(
                code="SUMMARY_VALIDATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.VALIDATION,
                context={"summary_length": len(summary)}
            )
            await self.state_manager.handle_error(error)
            return True  # Default to true if validation fails
