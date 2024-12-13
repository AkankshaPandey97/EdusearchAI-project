from fastapi import APIRouter, Depends, HTTPException
from backend.app.dependencies import get_pinecone_index
from backend.utils.vectorDb.pinecone_client import PineconeClient
from typing import List, Optional, Dict
from ..models.base import BaseResponse

router = APIRouter()

@router.get("/search", response_model=BaseResponse)
async def semantic_search(
    query: str,
    k: int = 4,
    filter: Optional[Dict] = None,
    pinecone: PineconeClient = Depends(get_pinecone_index)
):
    """Semantic search using vector similarity"""
    try:
        results = await pinecone.similarity_search(
            query=query,
            k=k,
            filter=filter
        )
        
        return BaseResponse(
            success=True,
            message="Search completed successfully",
            data={
                "results": results,
                "count": len(results)
            }
        )
    except Exception as e:
        return BaseResponse(
            success=False,
            message=f"Search operation failed: {str(e)}"
        )