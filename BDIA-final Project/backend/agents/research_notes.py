from typing import Dict, Any, List
from .base import BaseAgent
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory

class ResearchNote(BaseModel):
    title: str = Field(description="Title of the section or topic")
    summary: str = Field(description="Concise summary of the content")
    key_points: List[str] = Field(description="Key points extracted from the content")
    
class ResearchNotesAgent(BaseAgent):
    def __init__(self, model_name: str = "gpt-3.5-turbo-16k"):
        super().__init__(model_name)
        self.output_parser = PydanticOutputParser(pydantic_object=ResearchNote)
        
    def _create_system_prompt(self) -> str:
        return """You are an expert research assistant specialized in creating concise, 
        informative research notes from educational content. Your task is to:
        1. Analyze the content and identify key concepts
        2. Create clear, structured summaries
        3. Extract important points that capture the essence of the material
        4. Maintain academic tone while ensuring accessibility"""

    async def process(self, content: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process transcript segments and generate research notes"""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", self._create_system_prompt()),
                ("human", """Please analyze the following content and create a research note:
                Content: {content}
                
                Format your response as a research note with:
                - A clear title
                - A concise summary
                - Key points extracted from the content
                
                {format_instructions}""")
            ])
            
            # Get content from state
            content = state.get("segment_content", "")
            
            # Format prompt with content and parser instructions
            formatted_prompt = prompt.format_messages(
                content=content,
                format_instructions=self.output_parser.get_format_instructions()
            )
            
            # Get response from LLM using retry mechanism
            response = await self._execute_with_retry(
                self.llm.agenerate,
                [formatted_prompt]
            )
            
            # Parse the response into ResearchNote format
            research_note = self.output_parser.parse(response.generations[0][0].text)
            
            # Update state with research note
            state["research_notes"] = research_note.dict()
            
        except Exception as e:
            error = WorkflowError(
                code="RESEARCH_NOTES_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={"content_length": len(content)}
            )
            await self.state_manager.handle_error(error)
            state["errors"] = f"Failed to generate research notes: {str(e)}"
            
        return state