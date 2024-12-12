from typing import Optional, Callable
import asyncio
from datetime import datetime

class RetryStrategy:
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        
    async def execute(
        self, 
        operation: Callable,
        *args,
        **kwargs
    ):
        attempts = 0
        last_error = None
        
        while attempts < self.max_attempts:
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                attempts += 1
                last_error = e
                if attempts == self.max_attempts:
                    raise last_error
                await asyncio.sleep(self.base_delay * attempts) 