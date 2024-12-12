from langchain.prompts import ChatPromptTemplate

QUERY_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Analyze the educational query to determine:
    1. Query type (factual/conceptual/procedural/analytical)
    2. Complexity level (basic/intermediate/advanced)
    3. Main topics and concepts
    4. Whether it requires additional context
    5. Whether it requires citations
    6. Estimated response length (short/medium/long)
    
    Respond in JSON format:
    {
        "query_type": string,
        "complexity": string,
        "topics": string[],
        "requires_context": boolean,
        "requires_citations": boolean,
        "estimated_length": string
    }"""),
    ("human", "{query}")
])

CONTEXT_OPTIMIZATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Analyze the relevance of each context chunk to the query.
    Consider:
    1. Direct relevance to the query
    2. Supporting information value
    3. Prerequisites or background information
    
    Rate each chunk's relevance from 0-1."""),
    ("human", "Query: {query}\n\nContext chunks: {chunks}")
])

QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an educational assistant helping students understand course content.
    Use the following context to answer the question. Be comprehensive but concise.
    
    Context: {context}
    
    If the context doesn't contain enough information, say so and suggest what additional information might help."""),
    ("human", "{query}")
])