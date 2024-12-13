from typing import Dict, List, Any, Optional, AsyncGenerator
import openai
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel
from app.config import get_settings
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory

settings = get_settings()

class OpenAIConfig(BaseModel):
    """Configuration for OpenAI API calls"""
    model: str = "gpt-4-turbo-preview"
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 30

class OpenAIManager:
    """Manager class for OpenAI API operations"""
    
    def __init__(self, config: Optional[OpenAIConfig] = None):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.config = config or OpenAIConfig()
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate completion with retry logic"""
        try:
            response = await self.client.chat.completions.create(
                model=kwargs.get("model", self.config.model),
                messages=messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                top_p=kwargs.get("top_p", self.config.top_p),
                frequency_penalty=kwargs.get("frequency_penalty", self.config.frequency_penalty),
                presence_penalty=kwargs.get("presence_penalty", self.config.presence_penalty),
                timeout=kwargs.get("timeout", self.config.timeout)
            )
            return response
        except openai.RateLimitError as e:
            error = WorkflowError(
                code="OPENAI_RATE_LIMIT",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.RATE_LIMIT,
                context={"model": self.config.model},
                recoverable=True
            )
            await self.state_manager.add_error(error)
            raise
        except openai.APIError as e:
            error = WorkflowError(
                code="OPENAI_API_ERROR",
                message=str(e),
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.API,
                context={"model": self.config.model}
            )
            await self.state_manager.add_error(error)
            raise
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small"
    ) -> List[List[float]]:
        """Generate embeddings for given texts"""
        try:
            response = await self.client.embeddings.create(
                model=model,
                input=texts
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            raise Exception(f"Embedding generation failed: {str(e)}")
    
    async def count_tokens(self, text: str) -> int:
        """Estimate token count for a given text"""
        try:
            # Using tiktoken for accurate token counting
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.config.model)
            return len(encoding.encode(text))
        except ImportError:
            # Fallback to approximate counting if tiktoken is not available
            return len(text.split()) * 1.3
    
    async def check_content_safety(
        self,
        text: str
    ) -> Dict[str, float]:
        """Check content safety using OpenAI's moderation endpoint"""
        try:
            response = await self.client.moderations.create(input=text)
            return response.results[0]
        except Exception as e:
            raise Exception(f"Content moderation failed: {str(e)}")

class OpenAIStreamManager(OpenAIManager):
    """Manager class for handling streaming responses"""
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion responses"""
        try:
            stream = await self.client.chat.completions.create(
                model=kwargs.get("model", self.config.model),
                messages=messages,
                stream=True,
                **{k: v for k, v in kwargs.items() if k != "model"}
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise Exception(f"Streaming completion failed: {str(e)}")

# Utility functions
async def validate_api_key() -> bool:
    """Validate OpenAI API key"""
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        await client.models.list()
        return True
    except Exception:
        return False

async def get_available_models() -> List[str]:
    """Get list of available OpenAI models"""
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        models = await client.models.list()
        return [model.id for model in models.data]
    except Exception as e:
        raise Exception(f"Failed to fetch models: {str(e)}")

# Create default instances
openai_manager = OpenAIManager()
stream_manager = OpenAIStreamManager()
