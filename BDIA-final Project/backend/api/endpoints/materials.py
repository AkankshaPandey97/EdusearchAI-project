from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from backend.api.models.base import BaseResponse
from backend.agents.material_retrieval import MaterialRetrievalAgent, RetrievalInput
from backend.app.dependencies import get_pinecone_index
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory

router = APIRouter()

@router.get("/materials/{course_id}")
async def get_course_materials(
    course_id: str,
    topic: Optional[str] = None,
    material_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 10,
    index = Depends(get_pinecone_index)
):
    try:
        agent = MaterialRetrievalAgent()
        input_data = RetrievalInput(
            topic=topic or "",
            material_type=material_type,
            difficulty_level=difficulty,
            max_results=limit
        )
        result = await agent.process(input_data)
        
        return BaseResponse(
            success=True,
            data={"materials": result.materials}
        )
    except Exception as e:
        error = WorkflowError(
            code="MATERIAL_RETRIEVAL_ENDPOINT_ERROR",
            message=str(e),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.API,
            context={
                "course_id": course_id,
                "topic": topic,
                "material_type": material_type
            }
        )
        await state_manager.add_error(error)
        raise HTTPException(status_code=500, detail=str(e))
