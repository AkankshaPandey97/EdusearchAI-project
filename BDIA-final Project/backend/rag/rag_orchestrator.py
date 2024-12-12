from typing import Dict, Any
from .retriever import AdaptiveRetriever
from .embeddings import EduSearchEmbeddings
from utils.llm.base import get_llm
from agents.qa_agent import QAAgent
from .query_router import QueryRouter

class RAGOrchestrator:
    def __init__(self):
        self.embeddings = EduSearchEmbeddings()
        self.retriever = AdaptiveRetriever()
        self.qa_agent = QAAgent()
        self.llm = get_llm()
        self.query_router = QueryRouter()
    
    async def process_query(self, query: str) -> Dict[str, Any]:
        # Analyze query
        analysis = await self.query_router.analyze_query(query)
        
        # Determine retrieval strategy
        strategy = self.query_router.determine_retrieval_strategy(analysis)
        
        # Get embeddings and retrieve documents
        embeddings = await self.embeddings.get_query_embedding(query)
        documents = await self.retriever.retrieve(
            query=query, 
            embeddings=embeddings,
            **strategy
        )
        
        # Generate response
        response = await self.qa_agent.generate_response(
            query=query, 
            documents=documents,
            analysis=analysis
        )
        
        return {
            "query": query,
            "analysis": analysis.dict(),
            "response": response,
            "strategy_used": strategy
        } 