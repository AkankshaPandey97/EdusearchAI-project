from typing import Dict, List, Optional
from pydantic import BaseModel
from .base import BaseAgent, AgentInput, AgentOutput
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory
from google.cloud import bigquery
from backend.utils.logging_config import logger

class TopicSegmentInput(AgentInput):
    course_title: str
    query: Optional[str] = None

class TopicSegment(BaseModel):
    title: str
    formatted_title: str
    segment_number: int

class TopicSegmentOutput(AgentOutput):
    segments: List[TopicSegment]
    error: Optional[WorkflowError] = None

class TopicSegmentationAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.client = bigquery.Client()

    def _create_system_prompt(self) -> str:
        return "Topic segmentation assistant for course materials"

    def _format_title(self, title: str) -> str:
        """Format the title to extract the relevant part after the colon"""
        try:
            # Handle different title formats
            if ": :" in title:  # Format: "Lecture 6: : Independent Chip Model - How to..."
                main_title = title.split(": :")[-1].strip()
                if "-" in main_title:
                    main_title = main_title.split("-")[0].strip()
                return main_title
            elif ":" in title:  # Format: "pdf4 MBMathematics...: Artificial Intelligence..."
                return title.split(":")[-1].strip()
            else:
                return title.strip()
        except Exception as e:
            logger.error(f"Error formatting title: {str(e)}")
            return title

    async def _fetch_topics_from_bigquery(self, course_title: str) -> List[Dict]:
        """Fetch titles from BigQuery for the given course"""
        try:
            query = """
            SELECT course_id, title
            FROM `finalproject-442400.coursesdata.LectureNotes`
            WHERE LOWER(course_id) LIKE LOWER(@course_title)
            ORDER BY lecture_id
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(
                        "course_title", 
                        "STRING", 
                        f"%{course_title.replace(' ', '_')}%"
                    )
                ]
            )
            
            logger.info(f"Executing query for course: {course_title}")
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            topics = []
            for i, row in enumerate(results, 1):
                if row.title:
                    formatted_title = self._format_title(row.title)
                    topics.append({
                        'original_title': row.title,
                        'formatted_title': formatted_title,
                        'segment_number': i
                    })
            
            logger.info(f"Found {len(topics)} topics")
            return topics
            
        except Exception as e:
            logger.error(f"BigQuery error: {str(e)}")
            raise WorkflowError(
                code="BIGQUERY_FETCH_ERROR",
                message=f"Failed to fetch topics: {str(e)}",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.DATABASE
            )

    async def _process_implementation(self, input_data: TopicSegmentInput) -> TopicSegmentOutput:
        """Implementation of topic segmentation processing"""
        try:
            # Format course title to match database format
            course_title = input_data.course_title.replace(" ", "_")
            
            # Fetch topics from BigQuery
            topic_data = await self._fetch_topics_from_bigquery(course_title)
            
            if not topic_data:
                logger.warning(f"No topics found for: {course_title}")
                return TopicSegmentOutput(
                    success=True,
                    data={"message": "No topics found"},
                    segments=[]
                )
            
            # Create TopicSegment objects
            segments = []
            for data in topic_data:
                segment = TopicSegment(
                    title=data['original_title'],
                    formatted_title=data['formatted_title'],
                    segment_number=data['segment_number']
                )
                segments.append(segment)
            
            logger.info(f"Generated {len(segments)} segments successfully")
            return TopicSegmentOutput(
                success=True,
                data={"segments": [s.dict() for s in segments]},
                segments=segments
            )
            
        except Exception as e:
            logger.error(f"Topic segmentation error: {str(e)}")
            raise WorkflowError(
                code="TOPIC_SEGMENTATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={"course_title": course_title}
            )
