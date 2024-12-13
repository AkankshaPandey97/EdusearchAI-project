from typing import Dict, List, Any, Optional, Tuple
import pinecone
import asyncio
from langchain_community.vectorstores import Pinecone
from langchain_community.embeddings import OpenAIEmbeddings
from backend.app.config import get_settings
from contextlib import asynccontextmanager
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager
from backend.utils.retry_strategy import RetryStrategy

settings = get_settings()

class PineconeClient:
    _instance = None
    
    def __new__(cls):
        # Singleton pattern to avoid multiple initializations
        if cls._instance is None:
            cls._instance = super(PineconeClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Initialize only once
        if not hasattr(self, 'index'):
            self.api_key = settings.PINECONE_API_KEY
            self.index_name = settings.PINECONE_INDEX_NAME
            self.environment = settings.PINECONE_ENVIRONMENT
            self.state_manager = StateManager()  # Add StateManager initialization
            
            # Initialize embeddings
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                dimensions=384
            )
            
            # Initialize Pinecone
            pinecone.init(
                api_key=self.api_key,
                environment=self.environment
            )
            self.index = pinecone.Index(self.index_name)
            
            # Initialize LangChain vectorstore
            self.vectorstore = Pinecone(
                self.index,
                self.embeddings,
                "text"
            )
            self._connection_pool = []
            self._retry_strategy = RetryStrategy(max_attempts=3)

    @asynccontextmanager
    async def get_connection(self):
        """Async context manager for Pinecone operations"""
        try:
            yield self
        except Exception as e:
            raise Exception(f"Pinecone operation failed: {str(e)}")
        
    async def fetch_segments(
        self, 
        query_vector: List[float], 
        top_k: int = 5,
        filter: Optional[Dict] = None,
        namespace: str = ""
    ) -> List[Dict]:
        """Fetch relevant segments from Pinecone with retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                results = self.index.query(
                    vector=query_vector,
                    top_k=top_k,
                    include_metadata=True,
                    filter=filter,
                    namespace=namespace
                )
                return results.matches
            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"Error fetching from Pinecone after {max_retries} attempts: {str(e)}")
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff

    async def update_segment(
        self, 
        id: str, 
        metadata: Dict[str, Any],
        namespace: str = ""
    ):
        """Update segment with enriched metadata"""
        try:
            # Get existing vector
            vector_data = self.index.fetch([id])
            if not vector_data.vectors:
                raise Exception(f"Vector {id} not found")
                
            # Update with new metadata while keeping existing vector
            self.index.upsert([
                (id, vector_data.vectors[id].values, {
                    **vector_data.vectors[id].metadata,
                    **metadata
                })
            ], namespace=namespace)
        except Exception as e:
            raise Exception(f"Error updating Pinecone: {str(e)}")

    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict] = None,
        namespace: str = ""
    ) -> List[Dict]:
        """Perform similarity search using LangChain integration"""
        retries = 3
        while retries > 0:
            try:
                return await self._do_search(query, k=k, filter=filter)
            except Exception as e:
                retries -= 1
                if retries == 0:
                    raise
                await asyncio.sleep(1)

    async def _do_search(self, query: str, k: int, filter: Optional[Dict] = None):
        try:
            return await self.vectorstore.asimilarity_search(query, k=k, filter=filter)
        except Exception as e:
            error = WorkflowError(
                code="VECTOR_SEARCH_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.DATABASE,
                context={"query": query, "k": k}
            )
            await self.state_manager.add_error(error)
            raise

    async def batch_upsert(
        self,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]],
        batch_size: int = 100,
        namespace: str = ""
    ):
        """Batch upsert vectors with automatic batching"""
        try:
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                self.index.upsert(vectors=batch, namespace=namespace)
                await asyncio.sleep(0.5)  # Rate limiting
        except Exception as e:
            raise Exception(f"Batch upsert failed: {str(e)}")

    def get_langchain_retriever(self, search_kwargs: Optional[Dict] = None):
        """Get LangChain retriever for RAG operations"""
        return self.vectorstore.as_retriever(
            search_kwargs=search_kwargs or {"k": 4}
        )
