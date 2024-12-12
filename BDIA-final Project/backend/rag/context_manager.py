from typing import List, Dict, Optional
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager
import tiktoken
from pydantic import BaseModel
from enum import Enum

class QueryComplexity(Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class ContextConfig(BaseModel):
    max_tokens: int = 4000
    min_chunk_size: int = 100
    overlap_ratio: float = 0.2
    token_buffer: int = 200  # Buffer for system messages and other overhead

class ContextWindowManager:
    def __init__(self, config: Optional[ContextConfig] = None):
        self.config = config or ContextConfig()
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        #self.token_counter = tiktoken.encoding_for_model("gpt-4")
        self.state_manager = StateManager()
    
    def _count_tokens(self, text: str) -> int:
        """Accurately count tokens using the model's tokenizer"""
        return len(self.token_counter.encode(text))
    
    def _get_chunk_params(self, complexity: QueryComplexity) -> Dict[str, int]:
        """Get chunk parameters based on query complexity"""
        if complexity == QueryComplexity.BASIC:
            return {
                "chunk_size": 800,
                "chunk_overlap": 100
            }
        elif complexity == QueryComplexity.INTERMEDIATE:
            return {
                "chunk_size": 1200,
                "chunk_overlap": 200
            }
        else:  # ADVANCED
            return {
                "chunk_size": 1500,
                "chunk_overlap": 300
            }
    
    async def optimize_context(
        self, 
        docs: List[Document], 
        query: str,
        complexity: QueryComplexity = QueryComplexity.INTERMEDIATE
    ) -> List[Document]:
        """Optimize context window based on query relevance and token limits"""
        try:
            # Get chunk parameters based on complexity
            chunk_params = self._get_chunk_params(complexity)
            
            # Initialize text splitter with dynamic parameters
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_params["chunk_size"],
                chunk_overlap=chunk_params["chunk_overlap"],
                length_function=self._count_tokens,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            
            # Sort documents by relevance
            sorted_docs = await self._sort_by_relevance(docs, query)
            
            # Manage context window size
            return await self._fit_to_context_window(sorted_docs)
            
        except Exception as e:
            error = WorkflowError(
                code="CONTEXT_OPTIMIZATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={
                    "num_docs": len(docs),
                    "query": query,
                    "complexity": complexity.value
                }
            )
            await self.state_manager.handle_error(error)
            return docs  # Return original docs if optimization fails
    
    async def _sort_by_relevance(self, docs: List[Document], query: str) -> List[Document]:
        """Sort documents by relevance using semantic similarity"""
        try:
            # Calculate similarity scores
            scores = await self._calculate_similarity_scores(docs, query)
            
            # Sort documents by score
            sorted_docs = sorted(
                zip(docs, scores),
                key=lambda x: x[1],
                reverse=True
            )
            
            return [doc for doc, _ in sorted_docs]
        except Exception as e:
            await self._handle_sorting_error(e, len(docs))
            return docs
    
    async def _fit_to_context_window(self, docs: List[Document]) -> List[Document]:
        """Fit documents into context window while maintaining coherence"""
        total_tokens = 0
        fitted_docs = []
        available_tokens = self.config.max_tokens - self.config.token_buffer
        
        for doc in docs:
            doc_tokens = self._count_tokens(doc.page_content)
            
            if total_tokens + doc_tokens <= available_tokens:
                fitted_docs.append(doc)
                total_tokens += doc_tokens
            else:
                # Try to split document if it's large enough
                if doc_tokens > self.config.min_chunk_size:
                    chunks = self.text_splitter.split_text(doc.page_content)
                    
                    for chunk in chunks:
                        chunk_tokens = self._count_tokens(chunk)
                        if total_tokens + chunk_tokens <= available_tokens:
                            fitted_docs.append(Document(
                                page_content=chunk,
                                metadata={
                                    **doc.metadata,
                                    "is_chunk": True,
                                    "original_doc_id": doc.metadata.get("doc_id")
                                }
                            ))
                            total_tokens += chunk_tokens
                        else:
                            break
                
                if total_tokens >= available_tokens:
                    break
        
        return fitted_docs
    
    async def _calculate_similarity_scores(
        self, 
        docs: List[Document], 
        query: str
    ) -> List[float]:
        """Calculate semantic similarity scores between query and documents"""
        try:
            embeddings = self.get_embeddings()
            query_embedding = await embeddings.embed_query(query)
            
            scores = []
            for doc in docs:
                doc_embedding = await embeddings.embed_documents([doc.page_content])
                score = self._cosine_similarity(query_embedding, doc_embedding[0])
                scores.append(score)
            
            return scores
        except Exception as e:
            await self._handle_embedding_error(e)
            return [1.0] * len(docs)  # Return neutral scores on error
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        return dot_product / (norm1 * norm2) if norm1 * norm2 != 0 else 0