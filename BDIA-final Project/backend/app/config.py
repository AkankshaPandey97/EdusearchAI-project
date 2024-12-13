from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Temporarily remove BigQuery variables from the environment
#bq_vars = {key: os.environ.pop(key, None) for key in ['BQ_CREDENTIALS', 'BQ_PROJECT_ID', 'BQ_DATASET', 'BQ_TABLE']}

class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "EduSearch AI"
    
    # API Keys
    OPENAI_API_KEY: str
    PINECONE_INDEX_NAME: str
    PINECONE_ENVIRONMENT: str
    PINECONE_API_KEY: str
    API_KEY: str
    
    BIGQUERY_PROJECT_ID: Optional[str] = None
    BIGQUERY_DATASET: Optional[str] = None
    BIGQUERY_TABLE: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # Model settings
    DEFAULT_MODEL: str = "gpt-4-turbo-preview"
    temperature: float = 0.7
    
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
    
    ENV: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = True
        protected_namespaces = ('settings_',)  # Resolve namespace conflict

@lru_cache()
def get_settings() -> Settings:
    return Settings()

# Restore BigQuery variables to environment
#for key, value in bq_vars.items():
#    if value is not None:
#        os.environ[key] = value