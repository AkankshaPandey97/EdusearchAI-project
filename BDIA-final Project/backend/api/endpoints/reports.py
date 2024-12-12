from fastapi import APIRouter, HTTPException
from ..models.base import BaseResponse, Report
from backend.workflows.user_interaction import UserInteractionWorkflow

router = APIRouter()

@router.post("/reports/generate")
async def generate_report(
    course_id: str,
    include_notes: bool = True,
    include_qa: bool = True,
    include_citations: bool = True
):
    try:
        workflow = UserInteractionWorkflow()
        result = await workflow.execute({
            "query": "generate_report",
            "metadata": {
                "course_id": course_id,
                "include_notes": include_notes,
                "include_qa": include_qa,
                "include_citations": include_citations
            }
        })
        
        return BaseResponse(
            success=True,
            data={"report": Report(**result["results"][-1])}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 