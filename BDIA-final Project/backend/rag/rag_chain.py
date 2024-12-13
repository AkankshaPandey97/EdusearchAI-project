from typing import Dict, List, Optional
from langchain.chains import LLMChain
from langchain.schema import Document
from utils.llm.base import get_llm
from utils.llm.prompt_templates import QUERY_ANALYSIS_PROMPT, QA_PROMPT
from .retriever import AdaptiveRetriever
from .context_manager import ContextWindowManager, QueryComplexity, ContextConfig
from .feedback import RAGFeedback
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager

class AdaptiveRAGChain:
    def __init__(self):
        self.context_manager = ContextWindowManager(
            config=ContextConfig(
                max_tokens=4000,
                min_chunk_size=100,
                overlap_ratio=0.2
            )
        )
        self.state_manager = StateManager()
        # Register error callbacks
        self.state_manager.error_handler.register_callback(
            ErrorCategory.API, self._handle_api_error
        )
        self.state_manager.error_handler.register_callback(
            ErrorCategory.PROCESSING, self._handle_processing_error
        )
        self.llm = get_llm()
        self.retriever = AdaptiveRetriever()
        self.query_analyzer = LLMChain(
            llm=self.llm,
            prompt=QUERY_ANALYSIS_PROMPT
        )
        self.qa_chain = LLMChain(
            llm=self.llm,
            prompt=QA_PROMPT
        )
        self.feedback = RAGFeedback()
    
    async def process_query(self, query: str) -> Dict:
        try:
            # Analyze query
            analysis = await self.query_analyzer.arun(query=query)
            
            # Get relevant documents
            docs = await self.retriever.retrieve(query, analysis)
            
            # Optimize context window
            optimized_docs = await self.context_manager.optimize_context(docs, query)
            
            # Generate response
            context = self._format_context(optimized_docs)
            response = await self.qa_chain.arun(
                query=query,
                context=context
            )
            
            # Log interaction
            await self.feedback.log_interaction(
                query=query,
                response=response,
                metadata={"analysis": analysis, "docs_count": len(docs)}
            )
            
            return {
                "query": query,
                "analysis": analysis,
                "response": response,
                "sources": self._get_sources(optimized_docs)
            }
        except Exception as e:
            error = WorkflowError(
                code="RAG_PROCESSING_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.PROCESSING,
                context={"query": query}
            )
            await self.state_manager.add_error(error)
            return self._create_error_response(error)
    
    def _format_context(self, docs: List[Document]) -> str:
        return "\n\n".join(doc.page_content for doc in docs)
    
    def _get_sources(self, docs: List[Document]) -> List[Dict]:
        return [
            {
                "title": doc.metadata.get("title", "Unknown"),
                "source": doc.metadata.get("source", "Unknown")
            }
            for doc in docs
        ]