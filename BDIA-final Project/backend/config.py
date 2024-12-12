from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "EduSearch AI"
    
    # API Keys - match the exact case of env variables
    openai_api_key: str  # Changed from OPENAI_API_KEY
    pinecone_api_key: str  # Changed from PINECONE_API_KEY
    api_key: str  # Changed from API_KEY
    
    # Pinecone settings
    pinecone_index_name: str  # Changed from PINECONE_INDEX_NAME
    pinecone_environment: str  # Changed from PINECONE_ENVIRONMENT
    
    # Model settings
    default_model: str = "gpt-4-turbo-preview"
    model_temperature: float = 0.7
    
    # Context window settings
    max_context_tokens: int = 4000
    min_chunk_size: int = 100
    context_overlap_ratio: float = 0.2
    token_buffer: int = 200
    
    # Embedding settings
    embedding_model: str = "text-embedding-3-small"
    embedding_cache_size: int = 1000
    
    # API settings
    api_v1_prefix: str = "/api/v1"
    
    # Rate limiting
    rate_limit_per_minute: int = 60
    burst_limit: int = 10
    max_concurrent: int = 20

    class Config:
        env_file = ".env"
        case_sensitive = False  # Allow case-insensitive matching

@lru_cache()
def get_settings() -> Settings:
    return Settings()