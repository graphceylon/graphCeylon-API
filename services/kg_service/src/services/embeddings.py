"""Service for generating text embeddings."""

import logging
from typing import List
from sentence_transformers import SentenceTransformer
from core.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Singleton service for generating embeddings."""
    
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model_name}")
            try:
                self._model = SentenceTransformer(settings.embedding_model_name)
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single string."""
        try:
            if not text:
                return []
            embedding = self._model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return []

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of strings."""
        try:
            if not texts:
                return []
            embeddings = self._model.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return []

# Global instance
embedding_service = EmbeddingService()
