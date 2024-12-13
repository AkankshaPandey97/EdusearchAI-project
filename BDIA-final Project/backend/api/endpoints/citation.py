from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from backend.api.models.base import BaseResponse
from backend.agents.citation import CitationAgent, CitationInput, Citation
from backend.utils.logging_config import logger

router = APIRouter()

class CitationRequest(BaseModel):
    content: str
    style: str = "APA"

class CitationResponse(BaseResponse):
    citations: List[Citation]
    generated_at: datetime = datetime.now()

@router.post("/generate", response_model=CitationResponse)
async def generate_citation(request: CitationRequest):
    try:
        logger.info("Generating citation for content: " + str(request.content))
        
        # Initialize citation agent
        agent = CitationAgent()
        
        # Create input data with all required fields including query
        input_data = CitationInput(
            content=request.content,
            course_title=request.content,  # Using content as course title
            style=request.style,
            query=request.content  # Add this line to include the query field
        )
        
        logger.debug("Processing citation request...")
        result = await agent.process(input_data)
        
        if not result.citations:
            logger.info("No citations found")
            return CitationResponse(
                success=True,
                message="No citations found",
                citations=[],
                data={"message": "No citations found"}
            )
        
        logger.info(f"Generated {len(result.citations)} citations successfully")
        return CitationResponse(
            success=True,
            message="Citations generated successfully",
            citations=result.citations,
            data={"citations": [citation.dict() for citation in result.citations]}
        )
        
    except Exception as e:
        logger.error("Failed to generate citation: " + str(e))
        return CitationResponse(
            success=False,
            message=str(e),
            citations=[],
            data={"error": str(e)}
        )

@router.get("/styles")
async def get_citation_styles():
    """Get available citation styles"""
    styles = ["APA", "MLA", "Chicago", "Harvard"]
    return {
        "success": True,
        "styles": styles
    }
