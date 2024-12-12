from typing import Dict, Any, Optional
from backend.utils.logging_config import logger
from langchain_openai import ChatOpenAI
from backend.config import get_settings
import asyncio
from functools import lru_cache

class ModelLoader:
    _instance = None
    _models: Dict[str, Any] = {}
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelLoader, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    async def load_model(cls, model_name: str, **kwargs) -> Any:
        """Load and cache an ML model"""
        async with cls._lock:
            if model_name in cls._models:
                logger.info(f"Using cached model: {model_name}")
                return cls._models[model_name]
            
            logger.info(f"Loading model: {model_name}")
            try:
                settings = get_settings()
                
                if model_name.startswith("gpt"):
                    model = ChatOpenAI(
                        model_name=model_name,
                        temperature=kwargs.get("temperature", settings.model_temperature),
                        api_key=settings.openai_api_key
                    )
                else:
                    raise ValueError(f"Unsupported model: {model_name}")
                
                cls._models[model_name] = model
                logger.info(f"Model {model_name} loaded successfully")
                return model
                
            except Exception as e:
                logger.error(f"Error loading model {model_name}: {str(e)}", exc_info=True)
                raise
    
    @classmethod
    async def get_model(cls, model_name: str, **kwargs) -> Any:
        """Get a model, loading it if necessary"""
        return await cls.load_model(model_name, **kwargs)
    
    @classmethod
    async def unload_model(cls, model_name: str):
        """Unload a model from memory"""
        async with cls._lock:
            if model_name in cls._models:
                logger.info(f"Unloading model: {model_name}")
                del cls._models[model_name]
    
    @classmethod
    async def unload_all(cls):
        """Unload all models from memory"""
        async with cls._lock:
            logger.info("Unloading all models")
            cls._models.clear()

# Create a singleton instance
model_loader = ModelLoader()

# Helper function to get models with caching
@lru_cache(maxsize=None)
def get_model_loader() -> ModelLoader:
    return model_loader 