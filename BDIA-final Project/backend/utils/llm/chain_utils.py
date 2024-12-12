from typing import List, Dict, Any, Optional
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.callbacks import AsyncCallbackManager
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from .base import get_llm
from .prompt_templates import QA_PROMPT

class ChainManager:
    """Utility class to manage LangChain chains and their configurations"""
    
    def __init__(self, memory_key: str = "chat_history"):
        self.llm = get_llm()
        self.memory = ConversationBufferMemory(
            memory_key=memory_key,
            return_messages=True
        )
        self.callback_manager = AsyncCallbackManager([])
    
    async def create_chain(
        self,
        prompt: ChatPromptTemplate,
        memory: Optional[bool] = False,
        callbacks: Optional[List[Any]] = None
    ) -> LLMChain:
        """Create a LangChain chain with optional memory and callbacks"""
        chain_kwargs = {
            "llm": self.llm,
            "prompt": prompt,
            "verbose": True
        }
        
        if memory:
            chain_kwargs["memory"] = self.memory
            
        if callbacks:
            self.callback_manager.handlers.extend(callbacks)
            chain_kwargs["callback_manager"] = self.callback_manager
            
        return LLMChain(**chain_kwargs)
    
    def format_chat_history(self, messages: List[BaseMessage]) -> str:
        """Format chat history for prompt context"""
        formatted_messages = []
        for message in messages:
            if isinstance(message, HumanMessage):
                formatted_messages.append(f"Human: {message.content}")
            elif isinstance(message, AIMessage):
                formatted_messages.append(f"Assistant: {message.content}")
        return "\n".join(formatted_messages)
    
    async def get_conversation_chain(
        self,
        system_prompt: str,
        callbacks: Optional[List[Any]] = None
    ) -> LLMChain:
        """Create a conversation chain with memory"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            ("ai", "{output}")
        ])
        
        return await self.create_chain(
            prompt=prompt,
            memory=True,
            callbacks=callbacks
        )
    
    async def get_qa_chain(
        self,
        callbacks: Optional[List[Any]] = None
    ) -> LLMChain:
        """Create a Q&A chain with context"""
        return await self.create_chain(
            prompt=QA_PROMPT,
            callbacks=callbacks
        )
    
    def clear_memory(self):
        """Clear conversation memory"""
        self.memory.clear()

class ChainUtilities:
    """Utility functions for chain operations"""
    
    @staticmethod
    async def batch_process(
        chain: LLMChain,
        inputs: List[Dict[str, Any]],
        batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        """Process multiple inputs through a chain in batches"""
        results = []
        for i in range(0, len(inputs), batch_size):
            batch = inputs[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[chain.apredict(**input_data) for input_data in batch]
            )
            results.extend(batch_results)
        return results
    
    @staticmethod
    def create_retry_decorator(
        max_retries: int = 3,
        base_delay: float = 1.0
    ):
        """Create a retry decorator for chain execution"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)  # Exponential backoff
                            await asyncio.sleep(delay)
                raise last_exception
            return wrapper
        return decorator

class PromptManager:
    """Utility class to manage prompt templates and their variations"""
    
    @staticmethod
    def create_few_shot_prompt(
        examples: List[Dict[str, str]],
        prefix: str,
        suffix: str,
        input_variables: List[str]
    ) -> ChatPromptTemplate:
        """Create a few-shot prompt template"""
        example_prompt = ChatPromptTemplate.from_messages([
            ("human", "{input}"),
            ("ai", "{output}")
        ])
        
        few_shot_prompt = ChatPromptTemplate.from_messages([
            ("system", prefix),
            *[
                message for example in examples
                for message in [
                    ("human", example["input"]),
                    ("ai", example["output"])
                ]
            ],
            ("system", suffix),
            ("human", "{input}")
        ])
        
        return few_shot_prompt
    
    @staticmethod
    def add_context_to_prompt(
        prompt: ChatPromptTemplate,
        context: str
    ) -> ChatPromptTemplate:
        """Add context to an existing prompt template"""
        messages = prompt.messages.copy()
        context_message = ("system", f"Context:\n{context}")
        messages.insert(1, context_message)  # Insert after system message
        return ChatPromptTemplate.from_messages(messages)

# Export utility instances
chain_manager = ChainManager()
chain_utils = ChainUtilities()
prompt_manager = PromptManager()
