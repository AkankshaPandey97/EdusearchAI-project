from typing import Dict, Any, List, Optional, Literal
from langgraph.graph import StateGraph
from .base_workflow import BaseWorkflow, WorkflowState
from backend.agents.qa import QAAgent
from backend.agents.research_notes import ResearchNotesAgent
from backend.utils.logging import workflow_logger
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, RetryStrategy
from pydantic import BaseModel

class UserPreferences(BaseModel):
    difficulty_level: str = "intermediate"
    learning_style: str = "visual"
    topics_of_interest: List[str] = []
    preferred_content_type: str = "article"

class UserSession(BaseModel):
    session_id: str
    preferences: UserPreferences
    interaction_history: List[Dict[str, Any]] = []
    current_context: Optional[Dict[str, Any]] = None

class UserInteractionWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__()
        self.qa_agent = QAAgent()
        self.research_agent = ResearchNotesAgent()
        self.logger = workflow_logger
        
    async def initialize_session(self, state: WorkflowState) -> WorkflowState:
        """Initialize or restore user session"""
        try:
            session_data = state["metadata"].get("session_data", {})
            state["context"]["user_session"] = UserSession(
                session_id=session_data.get("session_id", ""),
                preferences=UserPreferences(**session_data.get("preferences", {}))
            )
            self.logger.log_state_transition("init", "session_created", state)
            return state
        except Exception as e:
            error_msg = f"Session initialization failed: {str(e)}"
            self.logger.log_error(error_msg, state)
            state["errors"].append(error_msg)
            return state

    async def process_user_input(self, state: WorkflowState) -> str:
        """Process and route user input"""
        try:
            input_type = state["metadata"].get("input_type", "query")
            session = state["context"]["user_session"]
            
            # Update interaction history
            session.interaction_history.append({
                "type": input_type,
                "query": state["query"],
                "timestamp": state["metadata"].get("timestamp")
            })
            
            if input_type == "preference_update":
                return "update_preferences"
            elif input_type == "query":
                return "process_query"
            return "end_session"
        except Exception as e:
            state["errors"].append(f"Input processing failed: {str(e)}")
            return "end_session"

    async def update_preferences(self, state: WorkflowState) -> WorkflowState:
        """Update user preferences"""
        try:
            session = state["context"]["user_session"]
            new_preferences = state["metadata"].get("new_preferences", {})
            session.preferences = UserPreferences(**new_preferences)
            state["results"].append({"preferences_updated": True})
            self.logger.log_state_transition("preferences", "updated", state)
            return state
        except Exception as e:
            error_msg = f"Preference update failed: {str(e)}"
            self.logger.log_error(error_msg, state)
            state["errors"].append(error_msg)
            return state

    async def process_query(self, state: WorkflowState) -> WorkflowState:
        """Process user query based on preferences"""
        try:
            session = state["context"]["user_session"]
            
            # Adapt query processing based on user preferences
            response = await self.qa_agent.process({
                "query": state["query"],
                "context": {
                    "preferences": session.preferences.dict(),
                    "history": session.interaction_history[-5:]  # Last 5 interactions
                }
            })
            
            state["results"].append({
                "answer": response.answer,
                "adapted_to_preferences": True
            })
            
            self.logger.log_state_transition("query", "processed", state)
            return state
        except Exception as e:
            error_msg = f"Query processing failed: {str(e)}"
            self.logger.log_error(error_msg, state)
            state["errors"].append(error_msg)
            return state

    async def end_session(self, state: WorkflowState) -> WorkflowState:
        """Clean up and save session data"""
        try:
            session = state["context"]["user_session"]
            state["results"].append({
                "session_summary": {
                    "interactions": len(session.interaction_history),
                    "last_interaction": session.interaction_history[-1] if session.interaction_history else None
                }
            })
            self.logger.log_state_transition("session", "ended", state)
            return state
        except Exception as e:
            error_msg = f"Session end failed: {str(e)}"
            self.logger.log_error(error_msg, state)
            state["errors"].append(error_msg)
            return state

    def create_workflow(self) -> StateGraph:
        # Add nodes
        self.graph.add_node("initialize", self.initialize_session)
        self.graph.add_node("route", self.process_user_input)
        self.graph.add_node("update_preferences", self.update_preferences)
        self.graph.add_node("process_query", self.process_query)
        self.graph.add_node("end", self.end_session)
        
        # Define workflow edges
        self.graph.add_edge("initialize", "route")
        
        # Add conditional edges from router
        self.graph.add_conditional_edges(
            "route",
            self.process_user_input,
            {
                "update_preferences": "update_preferences",
                "process_query": "process_query",
                "end_session": "end"
            }
        )
        
        # Add completion edges
        self.graph.add_edge("update_preferences", "end")
        self.graph.add_edge("process_query", "end")
        
        # Set entry point
        self.graph.set_entry_point("initialize")
        
        return self.graph.compile()
