"""GraphRAG service for entity extraction and knowledge graph construction."""

import logging
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from neo4j import Driver

from ..core.config import settings
from .embeddings import embedding_service

logger = logging.getLogger(__name__)


# Pydantic Models for Structured Extraction
class GraphNode(BaseModel):
    """Represents a node in the knowledge graph."""
    id: str = Field(description="Unique identifier for the node")
    type: str = Field(description="Type of the node (Policy, Requirement, Document, VisaType, etc.)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Node properties")


class GraphRelationship(BaseModel):
    """Represents a relationship in the knowledge graph."""
    source_id: str = Field(description="ID of the source node")
    target_id: str = Field(description="ID of the target node")
    type: str = Field(description="Type of relationship")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Relationship properties")


class GraphExtraction(BaseModel):
    """Container for extracted graph elements."""
    nodes: List[GraphNode]
    relationships: List[GraphRelationship]


class GraphRAGService:
    """Service for GraphRAG operations: ingestion and retrieval."""
    
    # Schema definitions for Economic & Policy domain
    ALLOWED_NODES = [
        "Policy", "VisaType", "Document", "Requirement", "Fee", 
        "Procedure", "CitizenshipService", "PassportService", 
        "ImmigrationService", "Authority", "Location", "TimeFrame"
    ]
    
    ALLOWED_RELATIONSHIPS = [
        "REQUIRES_DOCUMENT", "HAS_FEE", "HAS_REQUIREMENT", "HAS_PROCEDURE",
        "APPLIES_TO", "ISSUED_BY", "PROCESSED_AT", "TAKES_TIME",
        "PREREQUISITE_FOR", "RELATED_TO", "PART_OF", "GOVERNED_BY"
    ]
    
    def __init__(self, driver: Driver, openai_api_key: Optional[str] = None):
        """Initialize GraphRAG service.
        
        Args:
            driver: Neo4j driver instance
            openai_api_key: OpenAI API key for entity extraction
        """
        self.driver = driver
        self.openai_api_key = openai_api_key
        
        # Initialize LLM if API key provided
        if openai_api_key:
            try:
                self.llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0,
                    api_key=openai_api_key
                )
                logger.info("LLM initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            self.llm = None
            logger.warning("No OpenAI API key provided. Entity extraction will be unavailable.")
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def ensure_vector_index(self) -> Dict[str, Any]:
        """Create vector index for chunk embeddings if it doesn't exist."""
        try:
            index_name = "economic_policy_chunk_embeddings"
            
            with self.driver.session() as session:
                # Check if index exists
                result = session.run(
                    "SHOW INDEXES WHERE name = $name",
                    {"name": index_name}
                )
                
                if result.single():
                    logger.info(f"Vector index '{index_name}' already exists")
                    return {"success": True, "message": "Index already exists"}
                
                # Create vector index
                session.run(f"""
                    CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                    FOR (c:Chunk) ON (c.embedding)
                    OPTIONS {{indexConfig: {{
                        `vector.dimensions`: {settings.vector_dimensions},
                        `vector.similarity_function`: 'cosine'
                    }}}}
                """)
                
                logger.info(f"Vector index '{index_name}' created successfully")
                return {"success": True, "message": "Index created"}
                
        except Exception as e:
            logger.error(f"Failed to create vector index: {e}")
            raise
    
    def extract_entities_from_text(self, text: str) -> GraphExtraction:
        """Extract entities and relationships from text using LLM.
        
        Args:
            text: Text to extract entities from
            
        Returns:
            GraphExtraction with nodes and relationships
        """
        if not self.llm:
            raise ValueError("LLM not initialized. Provide OpenAI API key.")
        
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert Knowledge Graph extractor for Sri Lankan immigration and policy data.
                Extract entities and relationships from the text focusing on Economic & Policy domain.
                
                Allowed Node Types: {', '.join(self.ALLOWED_NODES)}
                Allowed Relationship Types: {', '.join(self.ALLOWED_RELATIONSHIPS)}
                
                Focus on extracting:
                - Policies and regulations
                - Visa types and requirements
                - Required documents
                - Fees and costs (with amounts and currency)
                - Procedures and steps
                - Government authorities and locations
                - Time frames and deadlines
                
                Return structured JSON following the GraphExtraction schema.
                """),
                ("user", "{text}")
            ])
            
            chain = prompt | self.llm.with_structured_output(
                GraphExtraction, 
                method="function_calling"
            )
            
            result = chain.invoke({"text": text})
            logger.info(f"Extracted {len(result.nodes)} nodes and {len(result.relationships)} relationships")
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract entities: {e}")
            # Return empty extraction on failure
            return GraphExtraction(nodes=[], relationships=[])
    
    def ingest_chunk(
        self, 
        text: str, 
        source_file: str, 
        chunk_id: str,
        extraction: GraphExtraction,
        domain_name: str = "Economic & Policy"
    ) -> None:
        """Ingest a text chunk with extracted entities into Neo4j.
        
        Args:
            text: Chunk text
            source_file: Source file name
            chunk_id: Unique chunk identifier
            extraction: Extracted entities and relationships
            domain_name: Domain to link chunk to (default: Economic & Policy)
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
                
                # 2. Link chunk to Economic & Policy domain
                session.run("""
                    MATCH (c:Chunk {id: $chunk_id})
                    MATCH (d:Domain {name: $domain_name})
                    MERGE (c)-[:BELONGS_TO_DOMAIN]->(d)
                    """,
                    {"chunk_id": chunk_id, "domain_name": domain_name}
                )
                
                # 3. Create extracted entity nodes
                for node in extraction.nodes:
                    # Validate node type
                    if node.type not in self.ALLOWED_NODES:
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
                        MERGE (n)-[:BELONGS_TO_DOMAIN]->(d)
                        """,
                        {"node_id": node.id, "domain_name": domain_name}
                    )
                
                # 4. Create relationships between entities
                for rel in extraction.relationships:
                    # Validate relationship type
                    if rel.type not in self.ALLOWED_RELATIONSHIPS:
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
        """Process a JSON file and ingest into knowledge graph.
        
        Args:
            file_path: Path to JSON file
            domain_name: Domain to link data to
            
        Returns:
            Processing statistics
        """
        if not self.llm:
            raise ValueError("LLM not initialized. Provide OpenAI API key.")
        
        logger.info(f"Processing file: {file_path}")
        
        try:
            # Load JSON data
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract all text content recursively
            full_text = ""
            
            def extract_text(item):
                nonlocal full_text
                if isinstance(item, dict):
                    # Extract from content arrays
                    if "content" in item and isinstance(item["content"], list):
                        for block in item["content"]:
                            if isinstance(block, dict) and "text" in block:
                                full_text += block["text"] + "\n\n"
                    
                    # Extract from content_text fields
                    if "content_text" in item and isinstance(item["content_text"], str):
                        full_text += item["content_text"] + "\n\n"
                    
                    # Recurse into nested structures
                    for v in item.values():
                        extract_text(v)
                        
                elif isinstance(item, list):
                    for i in item:
                        extract_text(i)
            
            extract_text(data)
            
            if not full_text.strip():
                logger.warning(f"No text content found in {file_path}")
                return {
                    "file": file_path,
                    "chunks_processed": 0,
                    "nodes_created": 0,
                    "relationships_created": 0
                }
            
            # Split into chunks
            chunks = self.text_splitter.split_text(full_text)
            logger.info(f"Split into {len(chunks)} chunks")
            
            total_nodes = 0
            total_relationships = 0
            source_file = Path(file_path).name
            
            # Process each chunk
            for i, chunk_text in enumerate(chunks):
                chunk_id = f"{source_file}_{i}"
                logger.info(f"Processing chunk {i+1}/{len(chunks)}")
                
                # Extract entities
                extraction = self.extract_entities_from_text(chunk_text)
                total_nodes += len(extraction.nodes)
                total_relationships += len(extraction.relationships)
                
                # Ingest into graph
                self.ingest_chunk(
                    text=chunk_text,
                    source_file=source_file,
                    chunk_id=chunk_id,
                    extraction=extraction,
                    domain_name=domain_name
                )
            
            stats = {
                "file": file_path,
                "chunks_processed": len(chunks),
                "nodes_created": total_nodes,
                "relationships_created": total_relationships
            }
            
            logger.info(f"Completed processing: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            raise
    
    def process_immigration_data(
        self,
        data_dir: str = "data/immigration",
        domain_name: str = "Economic & Policy"
    ) -> Dict[str, Any]:
        """Process all immigration JSON files in a directory.
        
        Args:
            data_dir: Directory containing JSON files
            domain_name: Domain to link data to
            
        Returns:
            Overall processing statistics
        """
        logger.info(f"Processing immigration data from: {data_dir}")
        
        # Ensure vector index exists
        self.ensure_vector_index()
        
        data_path = Path(data_dir)
        if not data_path.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")
        
        # Find all JSON files
        json_files = list(data_path.glob("**/*.json"))
        logger.info(f"Found {len(json_files)} JSON files")
        
        overall_stats = {
            "total_files": len(json_files),
            "files_processed": 0,
            "total_chunks": 0,
            "total_nodes": 0,
            "total_relationships": 0,
            "files": []
        }
        
        for json_file in json_files:
            try:
                file_stats = self.process_json_file(
                    str(json_file),
                    domain_name=domain_name
                )
                
                overall_stats["files_processed"] += 1
                overall_stats["total_chunks"] += file_stats["chunks_processed"]
                overall_stats["total_nodes"] += file_stats["nodes_created"]
                overall_stats["total_relationships"] += file_stats["relationships_created"]
                overall_stats["files"].append(file_stats)
                
            except Exception as e:
                logger.error(f"Failed to process {json_file}: {e}")
                overall_stats["files"].append({
                    "file": str(json_file),
                    "error": str(e)
                })
        
        logger.info(f"Processing complete: {overall_stats}")
        return overall_stats
    
    def query_with_rag(
        self, 
        question: str, 
        top_k: int = 5,
        domain_name: str = "Economic & Policy"
    ) -> Dict[str, Any]:
        """Query knowledge graph using RAG (Retrieval-Augmented Generation).
        
        Args:
            question: User question
            top_k: Number of similar chunks to retrieve
            domain_name: Domain to search within
            
        Returns:
            Answer with context and metadata
        """
        if not self.llm:
            raise ValueError("LLM not initialized. Provide OpenAI API key.")
        
        try:
            # 1. Generate query embedding
            query_embedding = embedding_service.generate_embedding(question)
            
            # 2. Vector search for similar chunks in Economic & Policy domain
            with self.driver.session() as session:
                result = session.run("""
                    CALL db.index.vector.queryNodes('economic_policy_chunk_embeddings', $top_k, $embedding)
                    YIELD node AS chunk, score
                    WHERE EXISTS {
                        MATCH (chunk)-[:BELONGS_TO_DOMAIN]->(d:Domain {name: $domain_name})
                    }
                    MATCH (chunk)-[:MENTIONS]->(entity)
                    RETURN chunk.text AS text, 
                           chunk.source AS source,
                           collect(DISTINCT {
                               type: labels(entity)[0],
                               id: entity.id,
                               properties: properties(entity)
                           }) AS entities, 
                           score
                    ORDER BY score DESC
                    """,
                    {
                        "top_k": top_k,
                        "embedding": query_embedding,
                        "domain_name": domain_name
                    }
                )
                
                chunks = list(result)
            
            if not chunks:
                return {
                    "answer": "I couldn't find any relevant information in the Economic & Policy domain knowledge graph.",
                    "context": [],
                    "metadata": {
                        "chunks_found": 0,
                        "domain": domain_name
                    }
                }
            
            # 3. Build context from retrieved chunks
            context = ""
            for i, chunk in enumerate(chunks, 1):
                context += f"--- Source {i} (Relevance: {chunk['score']:.2f}, File: {chunk['source']}) ---\n"
                context += f"{chunk['text']}\n"
                context += f"Related Entities: {len(chunk['entities'])} entities\n\n"
            
            # 4. Generate answer using LLM
            answer_prompt = ChatPromptTemplate.from_template("""
You are a helpful assistant for Sri Lankan immigration and policy information.
Use the following context to answer the user's question accurately and concisely.
Provide specific details like fees, requirements, and procedures when available.
If the answer is not in the context, say you don't know.

Context:
{context}

Question: {question}

Answer:
""")
            
            chain = answer_prompt | self.llm
            response = chain.invoke({
                "context": context,
                "question": question
            })
            
            answer = response.content
            
            return {
                "answer": answer,
                "context": [
                    {
                        "text": chunk["text"],
                        "source": chunk["source"],
                        "relevance_score": chunk["score"],
                        "entities_count": len(chunk["entities"])
                    }
                    for chunk in chunks
                ],
                "metadata": {
                    "chunks_found": len(chunks),
                    "domain": domain_name,
                    "top_k": top_k
                }
            }
            
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            raise
