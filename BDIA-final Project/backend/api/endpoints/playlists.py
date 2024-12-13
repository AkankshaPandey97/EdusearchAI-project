from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from ..models.base import BaseResponse, PlaylistProcessingRequest, ProcessingStatus
from ...workflows.content_enrichment import ContentEnrichmentWorkflow

router = APIRouter()

@router.post("/process")
#@router.post("/playlists/process")
async def process_playlist(
    request: PlaylistProcessingRequest,
    background_tasks: BackgroundTasks
):
    try:
        workflow = ContentEnrichmentWorkflow()
        
        # Start processing in background
        background_tasks.add_task(
            workflow.execute,
            {
                "course_id": request.course_id,
                "playlist_url": request.youtube_playlist_url,
                "ocw_url": request.ocw_course_url
            }
        )
        
        return BaseResponse(
            success=True,
            data={
                "processing_id": request.course_id,
                "status": ProcessingStatus(
                    status="queued",
                    progress=0.0,
                    started_at=datetime.now()
                )
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/playlists/{processing_id}/status")
async def get_processing_status(processing_id: str):
    # Implement status checking logic
    pass 

@router.get("/metadata")
async def get_playlists_metadata():
    try:
        # Return basic metadata for all playlists
        return JSONResponse(
            content={
                "status": "success",
                "data": {}  # Add your playlist metadata here
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{playlist_id}/status")
async def get_playlist_status(playlist_id: str):
    try:
        return JSONResponse(
            content={
                "status": "not_processed",
                "playlist_id": playlist_id
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{playlist_id}/segments")
async def get_playlist_segments(playlist_id: str):
    try:
        return JSONResponse(
            content={
                "segments": [],  # Add your segments data here
                "playlist_id": playlist_id
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))