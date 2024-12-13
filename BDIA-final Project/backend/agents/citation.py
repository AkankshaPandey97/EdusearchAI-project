from typing import List, Optional
from pydantic import BaseModel
from .base import BaseAgent, AgentInput, AgentOutput
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory
from google.cloud import bigquery
from backend.utils.logging_config import logger

class Citation(BaseModel):
    text: str
    source: str
    url: str
    confidence: float = 0.9

class CitationInput(AgentInput):
    content: str
    course_title: str
    style: str = "APA"
    query: Optional[str] = None

class CitationOutput(AgentOutput):
    citations: List[Citation]
    error: Optional[WorkflowError] = None

class CitationAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.client = bigquery.Client()

    def _create_system_prompt(self) -> str:
        return "Citation assistant for course materials"

    async def _process_implementation(self, input_data: CitationInput) -> CitationOutput:
        """Required implementation of the abstract method"""
        try:
            # Format course title to match database format
            course_title = input_data.content.replace(" ", "_")
            
            # Fetch citations from BigQuery
            citation_data = await self._fetch_urls_from_bigquery(course_title)
            
            if not citation_data:
                logger.warning(f"No citations found for: {course_title}")
                return CitationOutput(
                    success=True,
                    data={"message": "No citations found"},
                    citations=[]
                )
            
            # Create Citation objects
            citations = []
            for data in citation_data:
                citation = Citation(
                    text=f"Lecture: {data['title']}",
                    source=data['lecture_id'],
                    url=data['url'],
                    confidence=0.9
                )
                citations.append(citation)
            
            logger.info(f"Generated {len(citations)} citations successfully")
            return CitationOutput(
                success=True,
                data={"citations": [c.dict() for c in citations]},
                citations=citations
            )
            
        except Exception as e:
            logger.error(f"Citation processing error: {str(e)}")
            raise WorkflowError(
                code="CITATION_PROCESSING_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={"course_title": course_title}
            )

    async def _fetch_urls_from_bigquery(self, course_title: str) -> List[dict]:
        """Fetch URLs and titles from BigQuery for the given course"""
        try:
            query = """
            SELECT course_id, lecture_id, title, url
            FROM `finalproject-442400.coursesdata.LectureNotes`
            WHERE LOWER(course_id) LIKE LOWER(@course_title)
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(
                        "course_title", 
                        "STRING", 
                        f"%{course_title}%"
                    )
                ]
            )
            
            logger.info(f"Executing query for course: {course_title}")
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            citations = []
            for row in results:
                if row.url:
                    citations.append({
                        'title': row.title,
                        'url': row.url,
                        'lecture_id': row.lecture_id
                    })
            
            logger.info(f"Found {len(citations)} citations")
            return citations
            
        except Exception as e:
            logger.error(f"BigQuery error: {str(e)}")
            raise WorkflowError(
                code="BIGQUERY_FETCH_ERROR",
                message=f"Failed to fetch citations: {str(e)}",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.DATABASE
            )

    async def process(self, input_data: CitationInput) -> CitationOutput:
        """Main process method that calls _process_implementation"""
        try:
            return await self._process_implementation(input_data)
        except Exception as e:
            logger.error(f"Process error: {str(e)}")
            raise e
