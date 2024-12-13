from typing import Dict, Any, Literal, List, Optional
from pydantic import BaseModel
from utils.llm.base import get_llm
from utils.llm.prompt_templates import QUERY_ANALYSIS_PROMPT
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager
from .context_manager import QueryComplexity, ContextConfig

import tiktoken

QueryType = Literal["factual", "conceptual", "procedural", "analytical"]
Complexity = Literal["basic", "intermediate", "advanced"]

class QueryAnalysis(BaseModel):
    query_type: QueryType
    complexity: Complexity
    topics: List[str]
    requires_context: bool
    requires_citations: bool
    token_estimate: int = 0
    context_config: Optional[ContextConfig] = None

class QueryRouter:
    def __init__(self):
        self.llm = get_llm()
        self.state_manager = StateManager()
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
    
    async def analyze_query(self, query: str) -> QueryAnalysis:
        """Analyze query to determine type, complexity, and requirements"""
        try:
            # Get LLM analysis
            analysis_response = await self.llm.apredict_messages([
                ("system", QUERY_ANALYSIS_PROMPT),
                ("human", query)
            ])
            
            # Parse LLM response
            parsed_analysis = self._parse_llm_response(analysis_response)
            
            # Determine complexity
            complexity = await self._determine_complexity(query)
            
            # Estimate token requirements
            token_estimate = self._estimate_token_requirements(
                query, 
                complexity,
                parsed_analysis["query_type"]
            )
            
            # Generate context configuration
            context_config = self._generate_context_config(
                complexity,
                token_estimate,
                parsed_analysis["requires_context"]
            )
            
            return QueryAnalysis(
                query_type=parsed_analysis["query_type"],
                complexity=complexity,
                topics=parsed_analysis["topics"],
                requires_context=parsed_analysis["requires_context"],
                requires_citations=parsed_analysis["requires_citations"],
                token_estimate=token_estimate,
                context_config=context_config
            )
            
        except Exception as e:
            error = WorkflowError(
                code="QUERY_ANALYSIS_ERROR",
                message=str(e),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                context={"query": query}
            )
            await self.state_manager.add_error(error)
            return self._get_default_analysis()
    
    def _estimate_token_requirements(
        self, 
        query: str, 
        complexity: Complexity,
        query_type: QueryType
    ) -> int:
        """Estimate token requirements based on query characteristics"""
        base_tokens = len(self.tokenizer.encode(query))
        
        # Complexity multipliers
        complexity_multipliers = {
            "basic": 1.5,
            "intermediate": 2.0,
            "advanced": 3.0
        }
        
        # Query type multipliers
        type_multipliers = {
            "factual": 1.0,
            "conceptual": 1.5,
            "procedural": 2.0,
            "analytical": 2.5
        }
        
        estimated_tokens = base_tokens * complexity_multipliers[complexity] * type_multipliers[query_type]
        return int(estimated_tokens)
    
    def _generate_context_config(
        self, 
        complexity: Complexity,
        token_estimate: int,
        requires_context: bool
    ) -> ContextConfig:
        """Generate context configuration based on analysis"""
        if not requires_context:
            return ContextConfig(max_tokens=1000)  # Minimal context
            
        # Base configuration by complexity
        configs = {
            "basic": ContextConfig(
                max_tokens=2000,
                min_chunk_size=100,
                overlap_ratio=0.1
            ),
            "intermediate": ContextConfig(
                max_tokens=3000,
                min_chunk_size=150,
                overlap_ratio=0.15
            ),
            "advanced": ContextConfig(
                max_tokens=4000,
                min_chunk_size=200,
                overlap_ratio=0.2
            )
        }
        
        config = configs[complexity]
        
        # Adjust based on token estimate
        if token_estimate > config.max_tokens * 0.7:
            config.max_tokens = min(6000, int(token_estimate * 1.5))
            
        return config
    
    async def _determine_complexity(self, query: str) -> QueryComplexity:
        """Determine query complexity using heuristics and LLM"""
        try:
            # Basic heuristics
            word_count = len(query.split())
            has_complex_keywords = any(word in query.lower() for word in [
                "explain", "compare", "analyze", "evaluate", "synthesize"
            ])
            
            # LLM-based complexity assessment
            complexity_response = await self.llm.apredict_messages([
                ("system", "Analyze the complexity of this query and respond with BASIC, INTERMEDIATE, or ADVANCED."),
                ("human", query)
            ])
            
            # Combine heuristics and LLM assessment
            if "ADVANCED" in complexity_response or (
                word_count > 30 and has_complex_keywords
            ):
                return QueryComplexity.ADVANCED
            elif "INTERMEDIATE" in complexity_response or (
                word_count > 15 or has_complex_keywords
            ):
                return QueryComplexity.INTERMEDIATE
            else:
                return QueryComplexity.BASIC
                
        except Exception as e:
            await self.state_manager.add_error(WorkflowError(
                code="COMPLEXITY_DETERMINATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.PROCESSING,
                context={"query": query}
            ))
            return QueryComplexity.INTERMEDIATE  # Default to intermediate
    
    def _get_default_analysis(self) -> QueryAnalysis:
        """Return default analysis for error cases"""
        return QueryAnalysis(
            query_type="factual",
            complexity="intermediate",
            topics=[],
            requires_context=True,
            requires_citations=False,
            token_estimate=2000,
            context_config=ContextConfig(
                max_tokens=3000,
                min_chunk_size=150,
                overlap_ratio=0.15
            )
        )