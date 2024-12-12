from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from backend.api.models.base import BaseResponse, Citation
from backend.agents.citation import CitationAgent, CitationInput
from backend.app.dependencies import get_pinecone_index
from backend.utils.logging import workflow_logger

router = APIRouter()

class CitationRequest(BaseModel):
    content: str
    style: str = "APA"  # Default to APA style
    source_url: Optional[str] = None
    source_type: Optional[str] = None  # e.g., "video", "article", "lecture"
    timestamp: Optional[int] = None  # For video sources
    page: Optional[int] = None  # For text sources

class CitationResponse(BaseResponse):
    citations: List[Citation]
    generated_at: datetime = datetime.now()

@router.post("/generate", response_model=CitationResponse)
async def generate_citation(
    request: CitationRequest,
    index = Depends(get_pinecone_index)
):
    """
    Generate citations for educational content in the specified style.
    Supports multiple citation styles (APA, MLA, Chicago, etc.).
    """
    try:
        # Initialize citation agent
        agent = CitationAgent()
        
        # Prepare input for citation agent
        input_data = CitationInput(
            content=request.content,
            style=request.style,
            query="",  # Required by base AgentInput
            metadata={
                "source_url": request.source_url,
                "source_type": request.source_type,
                "timestamp": request.timestamp,
                "page": request.page
            }
        )
        
        # Process citation request
        result = await agent.process(input_data)
        
        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Citation generation failed"
            )
        
        # Log successful citation generation
        workflow_logger.logger.info(
            "Citation generated",
            extra={
                "style": request.style,
                "source_type": request.source_type
            }
        )
        
        return CitationResponse(
            success=True,
            message="Citations generated successfully",
            citations=result.citations,
            data={"citations": [citation.dict() for citation in result.citations]}
        )
        
    except Exception as e:
        workflow_logger.logger.error(
            f"Citation generation failed: {str(e)}",
            extra={"request": request.dict()}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate citation: {str(e)}"
        )

@router.post("/batch", response_model=CitationResponse)
async def batch_generate_citations(
    requests: List[CitationRequest],
    index = Depends(get_pinecone_index)
):
    """
    Generate citations for multiple content pieces in batch.
    """
    try:
        agent = CitationAgent()
        all_citations = []
        
        for req in requests:
            input_data = CitationInput(
                content=req.content,
                style=req.style,
                query="",
                metadata={
                    "source_url": req.source_url,
                    "source_type": req.source_type,
                    "timestamp": req.timestamp,
                    "page": req.page
                }
            )
            
            result = await agent.process(input_data)
            if result.success:
                all_citations.extend(result.citations)
        
        return CitationResponse(
            success=True,
            message=f"Generated {len(all_citations)} citations",
            citations=all_citations,
            data={"citations": [citation.dict() for citation in all_citations]}
        )
        
    except Exception as e:
        workflow_logger.logger.error(
            f"Batch citation generation failed: {str(e)}",
            extra={"request_count": len(requests)}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate batch citations: {str(e)}"
        )

@router.get("/styles", response_model=BaseResponse)
async def list_citation_styles():
    """
    List all supported citation styles.
    """
    styles = {
        "APA": "American Psychological Association",
        "MLA": "Modern Language Association",
        "Chicago": "Chicago Manual of Style",
        "Harvard": "Harvard Referencing",
        "IEEE": "Institute of Electrical and Electronics Engineers"
    }
    
    return BaseResponse(
        success=True,
        message="Available citation styles",
        data={"styles": styles}
    )

@router.get("/validate/{style}", response_model=BaseResponse)
async def validate_citation(
    style: str,
    citation_text: str
):
    """
    Validate if a citation follows the specified style guide correctly.
    """
    try:
        agent = CitationAgent()
        input_data = CitationInput(
            content=citation_text,
            style=style,
            query="validate_citation",
            metadata={"validation_mode": True}
        )
        
        result = await agent.process(input_data)
        
        return BaseResponse(
            success=True,
            message="Citation validation complete",
            data={
                "is_valid": result.success,
                "confidence": result.citations[0].confidence if result.citations else 0,
                "suggestions": result.data.get("suggestions", [])
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Citation validation failed: {str(e)}"
        )
