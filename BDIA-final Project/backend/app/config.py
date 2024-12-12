from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "EduSearch AI"
    
    # API Keys
    OPENAI_API_KEY: str
    PINECONE_API_KEY: str
    API_KEY: str
    
    # Pinecone settings
    PINECONE_INDEX_NAME: str
    PINECONE_ENVIRONMENT: str
    
    # Model settings
    DEFAULT_MODEL: str = "gpt-4-turbo-preview"
    MODEL_TEMPERATURE: float = 0.7
    
    # Context window settings
    MAX_CONTEXT_TOKENS: int = 4000
    MIN_CHUNK_SIZE: int = 100
    CONTEXT_OVERLAP_RATIO: float = 0.2
    TOKEN_BUFFER: int = 200
    
    # Embedding settings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_CACHE_SIZE: int = 1000
    
    # API settings
    API_V1_PREFIX: str = "/api/v1"
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    BURST_LIMIT: int = 10
    MAX_CONCURRENT: int = 20

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()