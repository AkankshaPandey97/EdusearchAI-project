from typing import List
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentInput, AgentOutput
from langchain.schema import Document
from backend.utils.llm.prompt_templates import QA_PROMPT
from backend.rag.context_manager import QueryComplexity, ContextWindowManager
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager
import openai

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

    async def _process_implementation(self, input_data: AgentInput) -> AgentOutput:
        # Cast input to correct type
        qa_input = input_data if isinstance(input_data, QAInput) else QAInput(**input_data.dict())
        
        try:
            # Determine complexity
            complexity = await self._analyze_question_complexity(qa_input.query)

            # Optimize context
            optimized_docs = await self.context_manager.optimize_context(
                docs=qa_input.documents,
                query=qa_input.query,
                complexity=complexity
            )

            # Generate answer
            response = await self._generate_answer(
                query=qa_input.query,
                documents=optimized_docs
            )

            return QAOutput(
                success=True,
                data={"answer": response},
                answer=response,
                confidence=0.9,
                citations=[]
            )

        except Exception as e:
            error = WorkflowError(
                code="QA_PROCESSING_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.PROCESSING,
                context={
                    "query": qa_input.query,
                    "num_docs": len(qa_input.documents)
                }
            )
            await self.state_manager.add_error(error)
            return QAOutput(
                success=False,
                data={},
                error=str(e),
                answer="",
                confidence=0.0,
                citations=[]
            )

    async def _analyze_question_complexity(self, query: str) -> QueryComplexity:
        try:
            complex_indicators = [
                "compare", "analyze", "explain", "how", "why", "what are the implications",
                "evaluate", "discuss", "describe the relationship", "what is the difference"
            ]
            
            indicator_count = sum(1 for indicator in complex_indicators if indicator in query.lower())
            
            if indicator_count >= 2 or len(query.split()) > 15:
                return QueryComplexity.HIGH
            elif indicator_count == 1 or len(query.split()) > 8:
                return QueryComplexity.MEDIUM
            else:
                return QueryComplexity.LOW
                
        except Exception as e:
            await self.state_manager.add_error(WorkflowError(
                code="COMPLEXITY_ANALYSIS_ERROR",
                message=str(e),
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.PROCESSING
            ))
            return QueryComplexity.MEDIUM

    async def _generate_answer(self, query: str, documents: List[Document]) -> str:
        try:
            context = "\n".join([doc.page_content for doc in documents])
            
            # Create the prompt for OpenAI
            prompt = f"""
            You are an educational AI assistant. Provide clear, accurate answers based on the given context.
            Question: {query}
            Context: {context}
            Please provide a clear and concise answer based on the given context. 
            If the context doesn't contain enough information to answer the question fully, 
            acknowledge this in your response.
            """
            
            # Call OpenAI's API
            response = openai.Completion.create(
                engine="gpt-4-turbo-preview",
                prompt=prompt,
                max_tokens=150
            )
            
            answer = response.choices[0].text.strip()
            
            if len(answer) < 10:
                raise ValueError("Generated answer is too short")
                
            return answer
            
        except Exception as e:
            error = WorkflowError(
                code="ANSWER_GENERATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.PROCESSING,
                context={
                    "query": query,
                    "num_documents": len(documents)
                }
            )
            await self.state_manager.add_error(error)
            raise error
