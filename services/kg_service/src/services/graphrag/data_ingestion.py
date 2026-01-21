"""Data ingestion service for GraphRAG."""

import logging
from typing import Dict, Any
from pathlib import Path
from neo4j import Driver

from services.embeddings import embedding_service
from models.ai.graphrag import GraphExtraction
from services.graphrag.config import graphrag_config
from services.graphrag.entity_extractor import EntityExtractor
from services.graphrag.chunk_processor import ChunkProcessor

logger = logging.getLogger(__name__)


class DataIngestionService:
    """Handles ingestion of data into the knowledge graph."""
    
    def __init__(
        self, 
        driver: Driver,
        entity_extractor: EntityExtractor,
        chunk_processor: ChunkProcessor
    ):
        """Initialize data ingestion service.
        
        Args:
            driver: Neo4j driver instance
            entity_extractor: Entity extraction service
            chunk_processor: Chunk processing service
        """
        self.driver = driver
        self.entity_extractor = entity_extractor
        self.chunk_processor = chunk_processor
    
    def ingest_chunk(
        self,
        text: str,
        source_file: str,
        chunk_id: str,
        extraction: GraphExtraction,
        domain_name: str = "Economic & Policy"
    ) -> None:
        """Ingest a single chunk with extracted entities into the graph.
        
        Args:
            text: Chunk text
            source_file: Source file name
            chunk_id: Unique chunk identifier
            extraction: Extracted entities and relationships
            domain_name: Domain to link chunk to
        """
        try:
            # Generate embedding
            embedding = embedding_service.generate_embedding(text)
            
            with self.driver.session() as session:
                # 1. Create Chunk node with embedding
                session.run("""
                    MERGE (c:Chunk {id: $chunk_id})
                    SET c.text = $text,
                        c.source = $source,
                        c.embedding = $embedding,
                        c.createdAt = datetime()
                    """,
                    {
                        "chunk_id": chunk_id,
                        "text": text,
                        "source": source_file,
                        "embedding": embedding
                    }
                )
                
                # 2. Link chunk to domain
                session.run("""
                    MATCH (c:Chunk {id: $chunk_id})
                    MATCH (d:Domain {name: $domain_name})
                    MERGE (c)-[:BELONGS_TO]->(d)
                    """,
                    {"chunk_id": chunk_id, "domain_name": domain_name}
                )
                
                # 3. Create extracted entity nodes
                for node in extraction.nodes:
                    # Validate node type
                    if node.type not in graphrag_config.ALLOWED_NODES:
                        logger.warning(f"Skipping invalid node type: {node.type}")
                        continue
                    
                    props = {**node.properties, "id": node.id}
                    
                    session.run(f"""
                        MERGE (n:`{node.type}` {{id: $id}})
                        SET n += $props
                        """,
                        {"id": node.id, "props": props}
                    )
                    
                    # Link chunk to entity via MENTIONS
                    session.run(f"""
                        MATCH (c:Chunk {{id: $chunk_id}})
                        MATCH (n:`{node.type}` {{id: $node_id}})
                        MERGE (c)-[:MENTIONS]->(n)
                        """,
                        {"chunk_id": chunk_id, "node_id": node.id}
                    )
                    
                    # Link entity to domain
                    session.run(f"""
                        MATCH (n:`{node.type}` {{id: $node_id}})
                        MATCH (d:Domain {{name: $domain_name}})
                        MERGE (n)-[:BELONGS_TO]->(d)
                        """,
                        {"node_id": node.id, "domain_name": domain_name}
                    )
                
                # 4. Create relationships between entities
                for rel in extraction.relationships:
                    # Validate relationship type
                    if rel.type not in graphrag_config.ALLOWED_RELATIONSHIPS:
                        logger.warning(f"Skipping invalid relationship type: {rel.type}")
                        continue
                    
                    session.run(f"""
                        MATCH (a {{id: $source_id}})
                        MATCH (b {{id: $target_id}})
                        MERGE (a)-[r:`{rel.type}`]->(b)
                        SET r += $props
                        """,
                        {
                            "source_id": rel.source_id,
                            "target_id": rel.target_id,
                            "props": rel.properties
                        }
                    )
            
            logger.info(f"Ingested chunk: {chunk_id}")
            
        except Exception as e:
            logger.error(f"Failed to ingest chunk {chunk_id}: {e}")
            raise
    
    def process_json_file(
        self, 
        file_path: str,
        domain_name: str = "Economic & Policy"
    ) -> Dict[str, Any]:
        """Process and ingest a JSON file.
        
        Args:
            file_path: Path to JSON file
            domain_name: Domain to link data to
            
        Returns:
            Processing statistics
        """
        try:
            logger.info(f"Processing file: {file_path}")
            
            # Process file into chunks
            chunks = self.chunk_processor.process_json_file(file_path)
            
            if not chunks:
                return {
                    "file": file_path,
                    "chunks_processed": 0,
                    "entities_extracted": 0,
                    "relationships_extracted": 0
                }
            
            # Process each chunk
            total_entities = 0
            total_relationships = 0
            
            for chunk in chunks:
                # Extract entities
                if self.entity_extractor.is_available():
                    extraction = self.entity_extractor.extract_entities(chunk["text"])
                    total_entities += len(extraction.nodes)
                    total_relationships += len(extraction.relationships)
                else:
                    # If no extractor, create empty extraction
                    extraction = GraphExtraction(nodes=[], relationships=[])
                
                # Ingest chunk
                self.ingest_chunk(
                    text=chunk["text"],
                    source_file=chunk["source"],
                    chunk_id=chunk["chunk_id"],
                    extraction=extraction,
                    domain_name=domain_name
                )
            
            result = {
                "file": file_path,
                "chunks_processed": len(chunks),
                "entities_extracted": total_entities,
                "relationships_extracted": total_relationships
            }
            
            logger.info(f"Completed processing {file_path}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            raise
    
    def process_immigration_data(
        self, 
        data_dir: str = "data/immigration",
        domain_name: str = "Economic & Policy"
    ) -> Dict[str, Any]:
        """Process all immigration data files.
        
        Args:
            data_dir: Directory containing immigration JSON files
            domain_name: Domain to link data to
            
        Returns:
            Overall processing statistics
        """
        try:
            # Resolve path relative to kg_service directory
            if not Path(data_dir).is_absolute():
                # Try relative to current working directory first
                data_path = Path(data_dir)
                if not data_path.exists():
                    # Try relative to project root (services/kg_service)
                    project_root = Path(__file__).parent.parent.parent.parent
                    data_path = project_root / data_dir
                    logger.info(f"Resolved path: {data_path} (exists: {data_path.exists()})")
                data_dir = str(data_path)
            
            logger.info(f"Processing immigration data from: {data_dir}")
            
            # Get all JSON files
            files = self.chunk_processor.get_files_in_directory(data_dir, "*.json")
            
            if not files:
                logger.warning(f"No JSON files found in {data_dir}")
                return {
                    "files_processed": 0,
                    "total_chunks": 0,
                    "total_entities": 0,
                    "total_relationships": 0
                }
            
            # Process each file
            file_results = []
            for file_path in files:
                result = self.process_json_file(str(file_path), domain_name)
                file_results.append(result)
            
            # Aggregate statistics
            overall_stats = {
                "files_processed": len(file_results),
                "total_chunks": sum(r["chunks_processed"] for r in file_results),
                "total_entities": sum(r["entities_extracted"] for r in file_results),
                "total_relationships": sum(r["relationships_extracted"] for r in file_results),
                "file_details": file_results
            }
            
            logger.info(f"Completed processing all files: {overall_stats}")
            return overall_stats
            
        except Exception as e:
            logger.error(f"Failed to process immigration data: {e}")
            raise
