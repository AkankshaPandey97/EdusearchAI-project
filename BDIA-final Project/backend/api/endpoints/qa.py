from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ..models.base import BaseResponse
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory
from backend.utils.logging_config import logger
from typing import Dict, Any
from openai import OpenAI

router = APIRouter()
client = OpenAI()  # Initialize the OpenAI client

@router.post("/api/v1/qa", response_model=BaseResponse)
async def question_answering(request: Dict[str, Any]):
    try:
        query = request.get("question", "")
        logger.info(f"Processing question: {query[:100]}...")
        
        # New OpenAI API call format
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a helpful educational assistant."},
                {"role": "user", "content": query}
            ],
            max_tokens=150
        )
        
        answer = response.choices[0].message.content
        logger.info("Answer generated successfully")
        
        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "answer": answer,
                    "confidence": 0.9,
                    "citations": []
                }
            },
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Error processing question: {str(e)}")
        error = WorkflowError(
            code="QA_ENDPOINT_ERROR",
            message=str(e),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.API,
            context={"query": query}
        )
        
        return JSONResponse(
            content={
                "success": False,
                "message": str(e),
                "error_code": "QA_ENDPOINT_ERROR",
                "error_details": {"query": query}
            },
            status_code=500
        )