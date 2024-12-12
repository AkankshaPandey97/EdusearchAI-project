from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentInput, AgentOutput
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager

class Material(BaseModel):
    title: str
    content: str
    type: str  # e.g., "article", "video", "exercise"
    difficulty: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RetrievalInput(AgentInput):
    topic: str
    material_type: Optional[str] = None
    difficulty_level: Optional[str] = None
    max_results: int = 5

class RetrievalOutput(AgentOutput):
    materials: List[Material]

class MaterialRetrievalAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.state_manager = StateManager()

    def _create_system_prompt(self) -> str:
        return """You are an educational material curator. For given topics:
        1. Identify relevant learning materials
        2. Match difficulty levels appropriately
        3. Ensure material diversity
        4. Consider learner context"""
    
    async def process(self, input_data: RetrievalInput) -> RetrievalOutput:
        try:
            # Get relevant materials
            response = await self._execute_with_retry(
                self.llm.apredict_messages,
                messages=[
                    ("system", self._create_system_prompt()),
                    ("human", f"""
                    Topic: {input_data.topic}
                    Type: {input_data.material_type or 'any'}
                    Difficulty: {input_data.difficulty_level or 'any'}
                    Max Results: {input_data.max_results}
                    
                    Suggest appropriate learning materials.
                    """)
                ]
            )
            
            # Process and format materials
            materials = []
            # Add material processing logic here
            
            return RetrievalOutput(
                success=True,
                data={"materials": materials},
                materials=materials
            )
            
        except Exception as e:
            error = WorkflowError(
                code="MATERIAL_RETRIEVAL_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.DATABASE,
                context={"topic": input_data.topic}
            )
            await self.state_manager.add_error(error)
            return RetrievalOutput(
                success=False,
                data={},
                error=str(e),
                materials=[]
            )
