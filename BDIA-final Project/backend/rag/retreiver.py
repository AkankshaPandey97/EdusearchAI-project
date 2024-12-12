from typing import List, Dict, Optional
from langchain.schema import Document
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from utils.llm.base import get_llm
from utils.vector_db.pinecone_client import PineconeClient
from langchain.embeddings import OpenAIEmbeddings
from functools import lru_cache

class AdaptiveRetriever:
    def __init__(self):
        self.client = PineconeClient()
        self.llm = get_llm()
        # Ensure embeddings match Pinecone index dimensions
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",  # This model uses 384 dimensions
            dimensions=384  # Explicitly set dimensions
        )
        self.base_compressor = LLMChainExtractor.from_llm(self.llm)
        # Use the langchain retriever from our PineconeClient
        self.compression_retriever = ContextualCompressionRetriever(
            base_compressor=self.base_compressor,
            base_retriever=self.client.get_langchain_retriever(
                embedding=self.embeddings
            )
        )
        self.cache = {}
    
    @lru_cache(maxsize=1000)
    async def _cached_retrieval(self, query: str, cache_key: Optional[str] = None):
        if cache_key and cache_key in self.cache:
            return self.cache[cache_key]
            
        # Your existing retrieval logic
        result = await self.compression_retriever.aget_relevant_documents(query)
        
        if cache_key:
            self.cache[cache_key] = result
            
        return result

    async def retrieve(
        self,
        query: str,
        analysis: Dict
    ) -> List[Document]:
        async with self.client.get_connection() as pinecone:
            try:
                # Adjust retrieval based on query analysis
                k = 6 if analysis.get('depth') == 'advanced' else 4
                
                # Initial retrieval using compression retriever
                docs = await self._cached_retrieval(query)
                
                # Check if we need more context
                if len(docs) < 2 or self._needs_expansion(docs, analysis):
                    expanded_docs = await self._expand_retrieval(pinecone, query, docs, analysis)
                    docs.extend(expanded_docs)
                
                return docs
            except Exception as e:
                raise Exception(f"Retrieval failed: {str(e)}")

    def _needs_expansion(self, docs: List[Document], analysis: Dict) -> bool:
        total_content = sum(len(doc.page_content) for doc in docs)
        return (total_content < 1000 and 
                analysis.get('depth') in ['intermediate', 'advanced'])

    async def _expand_retrieval(
        self,
        pinecone_client,
        query: str,
        initial_docs: List[Document],
        analysis: Dict
    ) -> List[Document]:
        topics = analysis.get('topics', [])
        if not topics:
            return []
            
        # Batch search for all topics at once
        try:
            filter_conditions = {
                "topics": {"$in": topics}
            }
            
            results = await pinecone_client.similarity_search(
                query=query,
                k=4,  # Adjust based on needs
                filter=filter_conditions,
                namespace="edu-content"  # Add your namespace if using one
            )
            
            return [
                Document(
                    page_content=result.metadata.get('text', ''),
                    metadata={
                        **result.metadata,
                        'score': result.score,  # Include relevance score
                        'retrieval_type': 'expansion'
                    }
                ) for result in results
            ]
        except Exception as e:
            raise Exception(f"Expansion retrieval failed: {str(e)}")

    async def _hybrid_search(
        self,
        query: str,
        analysis: Dict,
        k: int = 4
    ) -> List[Document]:
        """Implement hybrid search combining semantic and keyword search"""
        semantic_results = await self._cached_retrieval(query)
        
        # Get keyword results if needed
        if analysis.get('requires_factual', False):
            keyword_results = await self._keyword_search(query, k=k)
            return self._merge_results(semantic_results, keyword_results)
            
        return semantic_results
    
    async def _keyword_search(self, query: str, k: int = 4) -> List[Document]:
        """Implement keyword-based search for factual queries"""
        try:
            # Use Pinecone's keyword matching capabilities
            filter_conditions = {
                "$or": [
                    {"text": {"$contains": keyword}} 
                    for keyword in query.lower().split()
                ]
            }
            
            results = await self.client.similarity_search(
                query=query,
                k=k,
                filter=filter_conditions,
                namespace="edu-content"
            )
            
            return [
                Document(
                    page_content=result.metadata.get('text', ''),
                    metadata={
                        **result.metadata,
                        'retrieval_type': 'keyword'
                    }
                ) for result in results
            ]
        except Exception as e:
            raise Exception(f"Keyword search failed: {str(e)}")
    
    def _merge_results(
        self,
        semantic_docs: List[Document],
        keyword_docs: List[Document]
    ) -> List[Document]:
        """Merge and deduplicate results with score-based ranking"""
        doc_map = {}
        
        for doc in semantic_docs + keyword_docs:
            doc_id = doc.metadata.get('id')
            score = doc.metadata.get('score', 0.0)
            
            if doc_id not in doc_map or score > doc_map[doc_id].metadata.get('score', 0.0):
                doc_map[doc_id] = doc
                
        # Sort by score and return top results
        sorted_docs = sorted(
            doc_map.values(),
            key=lambda x: x.metadata.get('score', 0.0),
            reverse=True
        )
        
        return sorted_docs[:max(len(semantic_docs), len(keyword_docs))]