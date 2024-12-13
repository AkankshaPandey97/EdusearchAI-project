from typing import List, Dict
from langchain.vectorstores import Pinecone
from langchain.schema import Document
from utils.vector_db.pinecone_client import PineconeManager

class VectorStoreManager:
    def __init__(self):
        self.pinecone_manager = PineconeManager()
        self.vectorstore = self.pinecone_manager.get_vectorstore()
    
    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict] = None
    ) -> List[Document]:
        return await self.vectorstore.asimilarity_search(
            query,
            k=k,
            filter=filter
        )