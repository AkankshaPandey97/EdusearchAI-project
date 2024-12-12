import logging
from typing import Dict, Any

class WorkflowLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
    def log_state_transition(self, from_state: str, to_state: str, data: Dict[str, Any]):
        self.logger.info(
            f"Workflow transition: {from_state} -> {to_state}",
            extra={"state_data": data}
        )
    
    def log_error(self, error: str, context: Dict[str, Any]):
        self.logger.error(
            f"Workflow error: {error}",
            extra={"error_context": context}
        )

workflow_logger = WorkflowLogger("workflow") 