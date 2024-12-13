from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from fastapi.responses import JSONResponse
from backend.workflows.content_enrichment import ContentEnrichmentWorkflow, process_query
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory
from backend.workflows.base_workflow import WorkflowState

router = APIRouter()

@router.get("/{playlist_id}")
async def get_research_notes(playlist_id: str):
    try:
        # Create a query for the playlist
        request = {
            "query": f"Generate research notes for playlist {playlist_id}"
        }
        result = await process_query(request["query"])
        
        if result["errors"]:
            error = result["errors"][0]
            status_code = _map_error_severity_to_status(error.severity)
            raise HTTPException(
                status_code=status_code,
                detail={
                    "code": error.code,
                    "message": error.message,
                    "category": error.category.value,
                    "context": error.context
                }
            )
            
        return JSONResponse(content={
            "research_notes": result["research_notes"],
            "segments": result["segments"],
            "playlist_id": playlist_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        error = WorkflowError(
            code="RESEARCH_NOTES_ERROR",
            message=str(e),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PROCESSING,
            context={"playlist_id": playlist_id}
        )
        raise HTTPException(
            status_code=500,
            detail=error.dict()
        )

@router.post("/research_notes")
async def generate_research_notes(request: Dict[str, str]):
    try:
        result = await process_query(request["query"])
        if result["errors"]:
            error = result["errors"][0]
            status_code = _map_error_severity_to_status(error.severity)
            raise HTTPException(
                status_code=status_code,
                detail={
                    "code": error.code,
                    "message": error.message,
                    "category": error.category.value,
                    "context": error.context
                }
            )
        return {
            "research_notes": result["research_notes"],
            "segments": result["segments"]
        }
    except HTTPException:
        raise
    except Exception as e:
        error = WorkflowError(
            code="RESEARCH_NOTES_ERROR",
            message=str(e),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PROCESSING,
            context={"query": request.get("query")}
        )
        raise HTTPException(
            status_code=500,
            detail=error.dict()
        )

def _map_error_severity_to_status(severity: ErrorSeverity) -> int:
    """Map error severity to HTTP status code"""
    status_map = {
        ErrorSeverity.LOW: 400,
        ErrorSeverity.MEDIUM: 422,
        ErrorSeverity.HIGH: 500,
        ErrorSeverity.CRITICAL: 503
    }
    return status_map.get(severity, 500)

async def process_query(content: str) -> Dict[str, Any]:
    workflow = ContentEnrichmentWorkflow()
    state = WorkflowState(
        context={"content": content},
        results=[],
        errors=[]
    )
    
    result = await workflow.execute(state)
    
    return {
        "research_notes": result["results"][-1].get("summaries", []),
        "segments": result["results"][0].get("segments", []),
        "errors": result["errors"]
    }