from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentInput, AgentOutput
from langchain.schema import Document
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory

class SearchResult(BaseModel):
    content: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SearchInput(AgentInput):
    query: str
    filters: Optional[Dict[str, Any]] = None
    top_k: int = 5
    min_relevance: float = 0.7

class SearchOutput(AgentOutput):
    results: List[SearchResult]
    total_found: int

class SemanticSearchAgent(BaseAgent):
    def _create_system_prompt(self) -> str:
        return """You are a semantic search expert. Analyze queries to:
        1. Understand semantic intent
        2. Identify key concepts
        3. Determine relevant filters
        4. Rank results by relevance"""
    
    async def process(self, input_data: SearchInput) -> SearchOutput:
        try:
            # Analyze query intent
            query_analysis = await self._execute_with_retry(
                self.llm.apredict_messages,
                messages=[
                    ("system", self._create_system_prompt()),
                    ("human", f"""
                    Query: {input_data.query}
                    Filters: {input_data.filters}
                    
                    Analyze this search query and suggest relevant results.
                    """)
                ]
            )
            
            # Process results
            results = [
                SearchResult(
                    content=result.page_content,
                    relevance_score=result.metadata.get("score", 0.0),
                    metadata=result.metadata
                )
                for result in query_analysis.results[:input_data.top_k]
                if result.metadata.get("score", 0.0) >= input_data.min_relevance
            ]
            
            return SearchOutput(
                success=True,
                data={"results": results},
                results=results,
                total_found=len(results)
            )
            
        except Exception as e:
            error = WorkflowError(
                code="SEMANTIC_SEARCH_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.PROCESSING,
                context={
                    "query": input_data.query,
                    "filters": input_data.filters,
                    "top_k": input_data.top_k
                }
            )
            await self.state_manager.add_error(error)
            return SearchOutput(
                success=False,
                data={},
                error=str(e),
                results=[],
                total_found=0
            )
