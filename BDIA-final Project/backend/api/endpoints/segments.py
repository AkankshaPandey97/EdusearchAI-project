from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from backend.api.models.base import BaseResponse
from backend.agents.topic_segmentation import TopicSegmentationAgent, TopicSegmentInput
from backend.utils.logging_config import logger

router = APIRouter()

class SegmentRequest(BaseModel):
    course_title: str

class SegmentResponse(BaseResponse):
    segments: List[dict]

@router.post("/api/v1/segments")
async def get_segments(request: SegmentRequest):
    try:
        logger.info(f"Fetching segments for course: {request.course_title}")
        
        # Initialize agent
        agent = TopicSegmentationAgent()
        
        # Process request
        input_data = TopicSegmentInput(
            course_title=request.course_title,
            query=request.course_title
        )
        
        result = await agent.process(input_data)
        
        if not result.segments:
            return SegmentResponse(
                success=True,
                message="No segments found",
                segments=[],
                data={"message": "No segments found"}
            )
        
        return SegmentResponse(
            success=True,
            message="Segments retrieved successfully",
            segments=[{
                "title": segment.title,
                "formatted_title": segment.formatted_title,
                "segment_number": segment.segment_number
            } for segment in result.segments],
            data={"segments": result.segments}
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch segments: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch segments: {str(e)}"
        ) 