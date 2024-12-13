from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional, List, Dict, Any

# Base Response Model
class BaseResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    timestamp: datetime = datetime.now()
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    severity: Optional[str] = None

# Course Related Models
class CourseMetadata(BaseModel):
    course_id: str
    title: str
    description: str
    instructor: str
    semester: str
    department: str

class VideoMetadata(BaseModel):
    video_id: str
    title: str
    description: str
    duration: int
    youtube_url: HttpUrl
    course_id: str
    transcript: Optional[str]

# Content Models
class TopicSegment(BaseModel):
    topic: str
    keywords: List[str]
    sentiment_score: Optional[float]
    timestamp_start: Optional[int]
    timestamp_end: Optional[int]

class ResearchNote(BaseModel):
    title: str
    content: str
    topics: List[str]
    source_video_id: str
    generated_at: datetime

class QAPair(BaseModel):
    question: str
    answer: str
    confidence_score: float
    source_video_id: str
    timestamp: Optional[int]

# Supplementary Material Models
class Citation(BaseModel):
    title: str
    authors: List[str]
    publication_date: Optional[datetime]
    url: Optional[HttpUrl]
    citation_format: str  # e.g., "APA", "MLA"
    formatted_citation: str

class SupplementaryMaterial(BaseModel):
    title: str
    type: str  # e.g., "article", "presentation", "dataset"
    url: HttpUrl
    description: Optional[str]
    relevance_score: float
    topics: List[str]

# Search Models
class SearchResult(BaseModel):
    content: str
    content_type: str  # e.g., "note", "qa", "transcript"
    source_id: str
    relevance_score: float
    metadata: Dict

class SearchResponse(BaseResponse):
    results: List[SearchResult]
    total_results: int
    page: int
    page_size: int

# Report Models
class Report(BaseModel):
    course_id: str
    video_ids: List[str]
    research_notes: List[ResearchNote]
    qa_pairs: List[QAPair]
    citations: List[Citation]
    supplementary_materials: List[SupplementaryMaterial]
    generated_at: datetime

# Processing Status Models
class ProcessingStatus(BaseModel):
    status: str  # "queued", "processing", "completed", "failed"
    progress: float  # 0 to 1
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]

class PlaylistProcessingRequest(BaseModel):
    course_id: str
    youtube_playlist_url: HttpUrl
    ocw_course_url: Optional[HttpUrl]

class PlaylistProcessingResponse(BaseResponse):
    processing_id: str
    status: ProcessingStatus