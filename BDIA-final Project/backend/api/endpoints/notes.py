from fastapi import APIRouter, HTTPException
from typing import Dict
from backend.workflows.content_enrichment import process_query
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory

router = APIRouter()

@router.post("/research_notes")
async def generate_research_notes(request: Dict[str, str]):
    try:
        result = await process_query(request["query"])
        if result["errors"]:
            # Convert WorkflowError to appropriate HTTP response
            error = result["errors"][0]  # Get the first error
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