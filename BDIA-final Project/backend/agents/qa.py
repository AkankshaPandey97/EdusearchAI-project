from typing import List
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentInput, AgentOutput
from langchain.schema import Document
from backend.utils.llm.prompt_templates import QA_PROMPT
from backend.rag.context_manager import QueryComplexity, ContextWindowManager
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager

class QAInput(AgentInput):
    documents: List[Document]
    require_citations: bool = False
    query: str

class QAOutput(AgentOutput):
    answer: str
    confidence: float
    citations: List[str] = Field(default_factory=list)

class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.context_manager = ContextWindowManager()
        self.state_manager = StateManager()

    def _create_system_prompt(self) -> str:
        return """You are an educational AI assistant. Provide clear, accurate answers 
        based on the given context. If citations are requested, include relevant sources."""
    
    async def process(self, input_data: QAInput) -> QAOutput:
        try:
            # Determine complexity
            complexity = await self._analyze_question_complexity(input_data.query)

            # Optimize context
            optimized_docs = await self.context_manager.optimize_context(
                docs=input_data.documents,
                query=input_data.query,
                complexity=complexity
            )

            # Generate answer
            response = await self._generate_answer(
                query=input_data.query,
                documents=optimized_docs
            )

            return QAOutput(
                success=True,
                data={"answer": response},
                answer=response,
                confidence=0.9
            )

        except Exception as e:
            error = WorkflowError(
                code="QA_PROCESSING_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.PROCESSING,
                context={
                    "query": input_data.query,
                    "num_docs": len(input_data.documents)
                }
            )
            await self.state_manager.add_error(error)
            return QAOutput(
                success=False,
                data={},
                error=str(e),
                answer="",
                confidence=0.0
            )
