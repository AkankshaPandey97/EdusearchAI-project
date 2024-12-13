from typing import Any, Dict, Optional
from pydantic import BaseModel, validator, Field
import re

class SafeString(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
        
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError('string required')
        # Remove potentially dangerous characters
        return cls(re.sub(r'[^\w\s-]', '', v))

class ValidatedInput(BaseModel):
    query: SafeString
    max_length: Optional[int] = Field(None, ge=1, le=10000)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('metadata')
    def validate_metadata(cls, v):
        # Validate metadata structure
        allowed_keys = {'source', 'timestamp', 'user_id'}
        if not all(key in allowed_keys for key in v.keys()):
            raise ValueError('Invalid metadata keys')
        return v 