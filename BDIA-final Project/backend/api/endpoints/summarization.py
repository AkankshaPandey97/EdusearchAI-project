from fastapi import APIRouter, HTTPException
from typing import Dict
from google.cloud import bigquery
import logging
import os
from ...app.bigquery_config import get_bigquery_settings

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/summarize/{course_title}", response_model=Dict[str, str])
async def get_course_summary(course_title: str):
    try:
        logger.debug(f"Starting summary generation for course: {course_title}")
        
        # Get BigQuery settings
        bq_settings = get_bigquery_settings()
        logger.debug(f"Retrieved BigQuery settings: {bq_settings}")
        
        # Validate BigQuery settings
        required_settings = [
            "GOOGLE_APPLICATION_CREDENTIALS",
            "BIGQUERY_PROJECT_ID",
            "BIGQUERY_DATASET",
            "BIGQUERY_TABLE"
        ]
        
        missing_settings = [
            setting for setting in required_settings 
            if not bq_settings.get(setting)
        ]
        
        if missing_settings:
            error_msg = f"Missing required BigQuery settings: {', '.join(missing_settings)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Initialize client
        logger.debug("Initializing BigQuery client")
        client = bigquery.Client()
        
        # Prepare query - using only the fields that exist in your table
        query = f"""
        SELECT title, description
        FROM `{bq_settings["BIGQUERY_PROJECT_ID"]}.{bq_settings["BIGQUERY_DATASET"]}.{bq_settings["BIGQUERY_TABLE"]}`
        WHERE LOWER(title) = LOWER(@course_title)
        OR playlist_id = @course_title
        LIMIT 1
        """
        logger.debug(f"Executing query: {query}")
        
        # Configure parameters
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("course_title", "STRING", course_title)
            ]
        )
        
        # Execute query
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        
        # Process results with only available fields
        course_data = None
        for row in results:
            course_data = {
                "title": row.title,
                "description": row.description
            }
            break
            
        if not course_data:
            return {
                "course_title": course_title,
                "summary": "No course information available."
            }
            
        # Format the response with available information
        response = {
            "course_title": course_data['title'],
            "summary": course_data['description']
        }
        
        return response
        
    except Exception as e:
        error_msg = f"Error in get_course_summary: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching the course summary: {str(e)}"
        ) 