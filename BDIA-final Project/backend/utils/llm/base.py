from langchain_community.chat_models import ChatOpenAI
from backend.app.config import get_settings
import tiktoken
from typing import Optional
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import asyncio

class LLMManager:
    def __init__(self, model_name: str = "gpt-4-turbo-preview"):
        self.settings = get_settings()
        self.model_name = model_name
        self.tokenizer = tiktoken.encoding_for_model(model_name)
        self.llm = None
        self._cleanup_task = None
        self._is_initialized = False
        
    async def initialize(self):
        self.llm = ChatOpenAI()
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        
    async def cleanup(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
    def get_llm(
        self, 
        temperature: float = 0, 
        max_tokens: Optional[int] = None,
        streaming: bool = False,
        callbacks: Optional[CallbackManager] = None
    ) -> ChatOpenAI:
        """
        Get a configured LLM instance
        
        Args:
            temperature: The temperature for generation
            max_tokens: Maximum tokens to generate
            streaming: Whether to stream the output
            callbacks: Optional callback manager
        
        Returns:
            ChatOpenAI: Configured LLM instance
        """
        # Set up default callbacks for streaming if needed
        if streaming and not callbacks:
            callbacks = CallbackManager([StreamingStdOutCallbackHandler()])
            
        return ChatOpenAI(
            model_name=self.model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            callback_manager=callbacks,
            api_key=self.settings.OPENAI_API_KEY
        )
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string"""
        return len(self.tokenizer.encode(text))

# Singleton instance
llm_manager = LLMManager()

# For backward compatibility with existing code
def get_llm(**kwargs) -> ChatOpenAI:
    """Helper function to maintain compatibility with existing code"""
    return llm_manager.get_llm(**kwargs)