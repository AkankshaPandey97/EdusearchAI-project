from typing import List, Dict, Optional, Any
from google.cloud import bigquery
from .base import BaseAgent, AgentInput, AgentOutput
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory

class Summary(BaseModel):
    title: str
    brief: str
    detailed: str
    key_points: List[str]
    word_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SummarizationInput(AgentInput):
    content: str
    style: Optional[str] = "default"

class SummarizationOutput(AgentOutput):
    summary: Summary
    compression_ratio: float
    error: Optional[WorkflowError] = None

class SummarizationAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.client = bigquery.Client()

    async def fetch_course_description(self, course_title: str) -> str:
        query = """
        SELECT description
        FROM `finalproject-442400.coursesdata.Course`
        WHERE title = @course_title
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("course_title", "STRING", course_title)
            ]
        )
        query_job = self.client.query(query, job_config=job_config)
        results = query_job.result()

        for row in results:
            return row.description
        return "No description available for this course."

    async def summarize(self, course_title: str) -> str:
        try:
            description = await self.fetch_course_description(course_title)
            return description
        except Exception as e:
            error = WorkflowError(
                message=f"Failed to fetch course description: {str(e)}",
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.DATA,
                context={"course_title": course_title}
            )
            await self.state_manager.handle_error(error)
            return "An error occurred while fetching the course description."

    def _create_system_prompt(self) -> str:
        return """You are an expert summarization assistant. Your task is to:
        1. Create concise yet comprehensive summaries
        2. Maintain key information and context
        3. Adapt to different summarization styles
        4. Extract essential key points
        5. Ensure accuracy and clarity"""
    
    async def _process_implementation(self, input_data: SummarizationInput) -> SummarizationOutput:
        try:
            # 1. Get LLM response with proper formatting
            response = await self._execute_with_retry(
                self.llm.apredict_messages,
                messages=[
                    ("system", self._create_system_prompt()),
                    ("human", f"""
                    Please provide a summary in the following format:
                    TITLE: [title]
                    BRIEF: [brief summary]
                    DETAILED: [detailed summary]
                    KEY POINTS:
                    - [point 1]
                    - [point 2]
                    ...
                    
                    Content: {input_data.content}
                    """)
                ]
            )
            
            # 2. Parse the LLM response into structured format
            parsed_response = self._parse_llm_response(response)
            
            # 3. Create Summary object
            summary = Summary(
                title=parsed_response["title"],
                brief=parsed_response["brief"],
                detailed=parsed_response["detailed"],
                key_points=parsed_response["key_points"],
                word_count=len(parsed_response["detailed"].split())
            )
            
            # 4. Return properly formatted output
            return SummarizationOutput(
                success=True,
                data={
                    "summary": summary.dict(),
                    "compression_ratio": len(summary.detailed.split()) / len(input_data.content.split())
                },
                summary=summary,
                compression_ratio=len(summary.detailed.split()) / len(input_data.content.split())
            )
            
        except Exception as e:
            raise WorkflowError(
                code="SUMMARIZATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={"content_length": len(input_data.content)}
            )

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM response into structured format"""
        try:
            lines = response.strip().split('\n')
            result = {
                "title": "",
                "brief": "",
                "detailed": "",
                "key_points": []
            }
            
            current_section = None
            for line in lines:
                if line.startswith("TITLE:"):
                    current_section = "title"
                    result["title"] = line.replace("TITLE:", "").strip()
                elif line.startswith("BRIEF:"):
                    current_section = "brief"
                    result["brief"] = line.replace("BRIEF:", "").strip()
                elif line.startswith("DETAILED:"):
                    current_section = "detailed"
                    result["detailed"] = line.replace("DETAILED:", "").strip()
                elif line.startswith("KEY POINTS:"):
                    current_section = "key_points"
                elif line.strip().startswith("-") and current_section == "key_points":
                    result["key_points"].append(line.strip()[1:].strip())
                    
            return result
        except Exception as e:
            raise ValueError(f"Failed to parse LLM response: {str(e)}")
    
    async def _validate_summary(self, summary: str, original: str) -> bool:
        """Validate summary for factual consistency"""
        try:
            validation = await self.llm.apredict_messages([
                ("system", "You are a fact-checking assistant. Verify if the summary maintains factual accuracy with the original text."),
                ("human", f"Original: {original}\nSummary: {summary}\nIs the summary factually accurate?")
            ])
            return "yes" in validation.lower()
        except Exception as e:
            error = WorkflowError(
                code="SUMMARY_VALIDATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.VALIDATION,
                context={"summary_length": len(summary)}
            )
            await self.state_manager.handle_error(error)
            return True  # Default to true if validation fails
