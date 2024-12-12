from typing import Dict, Any, Literal
from .base_workflow import BaseWorkflow, WorkflowState
from backend.agents.qa import QAAgent
from backend.agents.semantic_search import SemanticSearchAgent
from backend.utils.logging import workflow_logger
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory

# Correct way to define Literal type
InteractionType = Literal["question", "search", "explore"]

class InteractiveFeaturesWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__()
        self.qa_agent = QAAgent()
        self.search_agent = SemanticSearchAgent()
        self.logger = workflow_logger
        
    async def route_interaction(self, state: WorkflowState) -> str:
        """Determine next step based on interaction type"""
        try:
            interaction_type: InteractionType = state["metadata"].get("interaction_type", "question")
            self.logger.log_state_transition("start", interaction_type, state)
            
            if interaction_type == "question":
                return "answer_question"
            elif interaction_type == "search":
                return "semantic_search"
            elif interaction_type == "explore":
                return "semantic_search"  # Default to search for explore
            return END
        except Exception as e:
            error = WorkflowError(
                code="INTERACTION_ROUTING_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.SYSTEM,
                context={"interaction_type": state["metadata"].get("interaction_type")}
            )
            await self.state_manager.add_error(error)
            return END
    
    async def answer_question(self, state: WorkflowState) -> WorkflowState:
        try:
            answer = await self.qa_agent.process({
                "query": state["query"],
                "documents": state["context"].get("documents", [])
            })
            state["results"].append({"answer": answer.answer})
            self.logger.log_state_transition("answer_question", "complete", state)
            return state
        except Exception as e:
            error_msg = f"QA failed: {str(e)}"
            self.logger.log_error(error_msg, state)
            state["errors"].append(error_msg)
            return state
    
    async def semantic_search(self, state: WorkflowState) -> WorkflowState:
        try:
            search_results = await self.search_agent.process({
                "query": state["query"],
                "filters": state["metadata"].get("filters", {})
            })
            state["results"].append({"search_results": search_results.results})
            self.logger.log_state_transition("semantic_search", "complete", state)
            return state
        except Exception as e:
            error_msg = f"Search failed: {str(e)}"
            self.logger.log_error(error_msg, state)
            state["errors"].append(error_msg)
            return state
    
    def create_workflow(self) -> StateGraph:
        # Add nodes
        self.graph.add_node("route", self.route_interaction)
        self.graph.add_node("answer_question", self.answer_question)
        self.graph.add_node("semantic_search", self.semantic_search)
        
        # Define conditional edges
        self.graph.add_conditional_edges(
            "route",
            self.route_interaction,
            {
                "answer_question": "answer_question",
                "semantic_search": "semantic_search",
                END: END
            }
        )
        
        # Add completion edges
        self.graph.add_edge("answer_question", END)
        self.graph.add_edge("semantic_search", END)
        
        # Set entry point
        self.graph.set_entry_point("route")
        
        return self.graph.compile()
