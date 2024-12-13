from typing import List, Optional, Dict
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.config import get_settings
import numpy as np
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager

settings = get_settings()

class EduSearchEmbeddings:
    def __init__(self):
        self.model = "text-embedding-3-small"
        self.cache = {}
        self.state_manager = StateManager()

    async def embed_query(self, query: str) -> List[float]:
        try:
            if query in self.cache:
                return self.cache[query]

            embedding = await self._get_embedding(query)
            self.cache[query] = embedding
            return embedding

        except Exception as e:
            error = WorkflowError(
                code="EMBEDDING_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.API,
                context={"query": query}
            )
            await self.state_manager.add_error(error)
            raise

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            embeddings = []
            for text in texts:
                if text in self.cache:
                    embeddings.append(self.cache[text])
                else:
                    embedding = await self._get_embedding(text)
                    self.cache[text] = embedding
                    embeddings.append(embedding)
            return embeddings
        except Exception as e:
            error = WorkflowError(
                code="BATCH_EMBEDDING_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.API,
                context={"num_texts": len(texts)}
            )
            await self.state_manager.add_error(error)
            raise

    async def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single query text"""
        try:
            return await self.embeddings.aembed_query(text)
        except Exception as e:
            raise Exception(f"Error generating query embedding: {str(e)}")

    async def get_text_embeddings(
        self,
        texts: List[str],
        metadata: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        Generate embeddings for a list of texts with optional metadata
        Returns: List of dicts containing embeddings and metadata
        """
        try:
            # Split texts if they're too long
            all_chunks = []
            all_metadata = []
            
            for i, text in enumerate(texts):
                chunks = self.text_splitter.split_text(text)
                all_chunks.extend(chunks)
                
                # Duplicate metadata for each chunk if provided
                if metadata and len(metadata) > i:
                    chunk_metadata = metadata[i].copy()
                    chunk_metadata['chunk_index'] = range(len(chunks))
                    all_metadata.extend([chunk_metadata] * len(chunks))

            # Generate embeddings for all chunks
            embeddings = await self.embeddings.aembed_documents(all_chunks)

            # Combine embeddings with their metadata
            result = []
            for i, embedding in enumerate(embeddings):
                entry = {
                    'text': all_chunks[i],
                    'embedding': embedding,
                }
                if all_metadata:
                    entry['metadata'] = all_metadata[i]
                result.append(entry)

            return result

        except Exception as e:
            error = WorkflowError(
                code="EMBEDDING_GENERATION_ERROR",
                message=str(e),
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.API,
                context={"num_texts": len(texts)}
            )
            await self.state_manager.add_error(error)
            raise

    async def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between two embeddings"""
        try:
            # Convert to numpy arrays for efficient computation
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Compute cosine similarity
            similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            return float(similarity)
        except Exception as e:
            raise Exception(f"Error computing similarity: {str(e)}")

    async def batch_process_texts(
        self,
        texts: List[str],
        batch_size: int = 5,
        metadata: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """Process large numbers of texts in batches"""
        try:
            results = []
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_metadata = metadata[i:i + batch_size] if metadata else None
                
                batch_results = await self.get_text_embeddings(
                    texts=batch_texts,
                    metadata=batch_metadata
                )
                results.extend(batch_results)
                
            return results
        except Exception as e:
            raise Exception(f"Error in batch processing: {str(e)}")

    def get_embedding_dimension(self) -> int:
        """Return the dimension of the embeddings"""
        return 384  # Your Pinecone index dimension