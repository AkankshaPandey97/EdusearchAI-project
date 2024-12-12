from fastapi import APIRouter, Depends, HTTPException
from ..models.base import BaseResponse
from backend.agents.qa import QAAgent
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory
from backend.utils.logging_config import logger
from backend.utils.model_loader import get_model_loader
from typing import Dict, Any

router = APIRouter()

@router.post("/qa", response_model=BaseResponse)
async def question_answering(
    query: str,
    qa_agent: QAAgent = Depends(lambda: QAAgent())
):
    logger.info(f"Processing question: {query[:100]}...")
    try:
        logger.debug("Generating answer using model...")
        model_loader = get_model_loader()
        model = await model_loader.get_model("gpt-4-turbo-preview")
        result = await qa_agent.process_question(query)
        logger.info("Answer generated successfully")
        return BaseResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error processing question: {str(e)}", exc_info=True)
        error = WorkflowError(
            code="QA_ENDPOINT_ERROR",
            message=str(e),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.API,
            context={"query": query}
        )
        await qa_agent.state_manager.add_error(error)
        return BaseResponse(
            success=False,
            message=str(e),
            error_code=error.code,
            error_details=error.context
        )