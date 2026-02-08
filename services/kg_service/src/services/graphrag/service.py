"""Main GraphRAG service orchestrating all components."""

import logging
from typing import Dict, Any
from neo4j import Driver

from .vector_indexer import VectorIndexer
from .entity_extractor import EntityExtractor
from .chunk_processor import ChunkProcessor
from .data_ingestion import DataIngestionService
from .rag_query_engine import RAGQueryEngine
from .config import graphrag_config

logger = logging.getLogger(__name__)


class GraphRAGService:
    """Main service coordinating GraphRAG operations."""
    
    def __init__(self, driver: Driver):
        """Initialize GraphRAG service with all components.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
        
        # Initialize components (they now get their LLM config from settings)
        self.vector_indexer = VectorIndexer(driver)
        self.entity_extractor = EntityExtractor()
        self.chunk_processor = ChunkProcessor()
        self.rag_query_engine = RAGQueryEngine(driver)
        self.data_ingestion = DataIngestionService(
            driver,
            self.entity_extractor,
            self.chunk_processor
        )
        
        logger.info("GraphRAG service initialized")
    
    def ensure_vector_index(self) -> Dict[str, Any]:
        """Ensure vector index exists for similarity search.
        
        Returns:
            Dictionary with success status and message
        """
        return self.vector_indexer.ensure_index_exists()
    
    def ingest_immigration_data(
        self,
        data_dir: str = "data/immigration",
        domain_name: str = "Economic & Policy"
    ) -> Dict[str, Any]:
        """Ingest immigration data into knowledge graph.
        
        Args:
            data_dir: Directory containing immigration JSON files
            domain_name: Domain to link data to
            
        Returns:
            Processing statistics
        """
        return self.data_ingestion.process_immigration_data(data_dir, domain_name)
    
    def query(
        self,
        question: str,
        domain_name: str = "Economic & Policy",
        top_k: int = 5
    ) -> Dict[str, Any]:
        """Execute a RAG query.
        
        Args:
            question: Question to answer
            domain_name: Domain to search within
            top_k: Number of similar chunks to retrieve
            
        Returns:
            Dictionary with answer, context, and metadata
        """
        return self.rag_query_engine.query(question, domain_name, top_k)
    
    def get_statistics(self, domain_name: str = "Economic & Policy") -> Dict[str, Any]:
        """Get statistics about ingested data.
        
        Args:
            domain_name: Domain to get statistics for
            
        Returns:
            Statistics dictionary
        """
        try:
            with self.driver.session() as session:
                # Count chunks
                chunk_result = session.run("""
                    MATCH (c:Chunk)-[:BELONGS_TO]->(d:Domain {name: $domain_name})
                    RETURN count(c) AS chunk_count
                """, {"domain_name": domain_name})
                chunk_count = chunk_result.single()["chunk_count"]
                
                # Count entity types
                entity_result = session.run("""
                    MATCH (n)-[:BELONGS_TO]->(d:Domain {name: $domain_name})
                    WHERE NOT n:Chunk AND NOT n:Domain
                    RETURN labels(n)[0] AS entity_type, count(n) AS count
                    ORDER BY count DESC
                """, {"domain_name": domain_name})
                entity_types = [
                    {"type": record["entity_type"], "count": record["count"]}
                    for record in entity_result
                ]
                
                # Count relationship types
                rel_result = session.run("""
                    MATCH (n)-[r]->(m)
                    WHERE (n)-[:BELONGS_TO]->(:Domain {name: $domain_name})
                      AND type(r) <> 'BELONGS_TO'
                      AND type(r) <> 'MENTIONS'
                    RETURN type(r) AS rel_type, count(r) AS count
                    ORDER BY count DESC
                """, {"domain_name": domain_name})
                relationship_types = [
                    {"type": record["rel_type"], "count": record["count"]}
                    for record in rel_result
                ]
                
                # Get sample chunks
                sample_result = session.run("""
                    MATCH (c:Chunk)-[:BELONGS_TO]->(d:Domain {name: $domain_name})
                    RETURN c.text AS text, c.source AS source, c.chunk_id AS chunk_id
                    LIMIT 3
                """, {"domain_name": domain_name})
                sample_chunks = [
                    {
                        "text": record["text"][:200] + "..." if len(record["text"]) > 200 else record["text"],
                        "source": record["source"],
                        "chunk_id": record["chunk_id"]
                    }
                    for record in sample_result
                ]
                
                return {
                    "domain": domain_name,
                    "chunk_count": chunk_count,
                    "entity_types": entity_types,
                    "relationship_types": relationship_types,
                    "sample_chunks": sample_chunks
                }
                
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            raise
    
    def is_available(self) -> Dict[str, bool]:
        """Check which features are available.
        
        Returns:
            Dictionary indicating feature availability
        """
        return {
            "entity_extraction": self.entity_extractor.is_available(),
            "rag_queries": self.rag_query_engine.is_available(),
            "vector_indexing": True,
            "data_ingestion": True
        }
    
    def retrieve_relevant_chunks(
        self,
        query_text: str,
        domain_name: str = "Economic & Policy",
        top_k: int = 10,
        min_score: float = 0.5
    ) -> Dict[str, Any]:
        """Retrieve relevant chunks without LLM generation.
        
        Args:
            query_text: Text to search for
            domain_name: Domain to search within
            top_k: Number of similar chunks to retrieve
            min_score: Minimum similarity score threshold
            
        Returns:
            Dictionary with chunks and metadata
        """
        return self.rag_query_engine.retrieve_relevant_chunks(
            query_text,
            domain_name,
            top_k,
            min_score
        )
