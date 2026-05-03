"""
Sub-Attraction Vector Embedding Service

State-of-the-art (2026) vector embedding service for sub-attractions using:
- Sentence Transformers with latest multilingual models
- Hybrid embedding strategy (semantic + metadata)
- Efficient batch processing
- Neo4j vector index integration
"""

import logging
from typing import List, Dict, Any, Optional
import json
from threading import Lock

import numpy as np
from sentence_transformers import SentenceTransformer
from neo4j import Driver

logger = logging.getLogger(__name__)


class SubAttractionEmbeddingService:
    """
    Advanced vector embedding service for POI/sub-attraction semantic search.
    
    Features:
    - Uses state-of-the-art multilingual embedding model
    - Generates rich semantic representations from multiple fields
    - Supports batch embedding generation
    - Integrates with Neo4j vector indexes
    """
    
    # Latest high-performance multilingual model (2026)
    DEFAULT_MODEL = "sentence-transformers/all-mpnet-base-v2"
    EMBEDDING_DIMENSION = 768  # Model-specific dimension
    _MODEL_CACHE: Dict[tuple[str, str], SentenceTransformer] = {}
    _MODEL_CACHE_LOCK = Lock()

    @classmethod
    def _get_or_load_model(cls, model_name: str, device: str) -> SentenceTransformer:
        """Load model once per process and reuse it across requests."""
        cache_key = (model_name, device)
        if cache_key in cls._MODEL_CACHE:
            return cls._MODEL_CACHE[cache_key]

        with cls._MODEL_CACHE_LOCK:
            if cache_key in cls._MODEL_CACHE:
                return cls._MODEL_CACHE[cache_key]

            logger.info(f"Loading embedding model: {model_name} on device={device}")

            # Prevent meta-tensor initialization path that can fail under some
            # containerized CPU deployments with specific torch/transformers combos.
            try:
                model = SentenceTransformer(
                    model_name,
                    device=device,
                    model_kwargs={"low_cpu_mem_usage": False},
                )
            except TypeError:
                model = SentenceTransformer(model_name, device=device)

            cls._MODEL_CACHE[cache_key] = model
            return model
    
    def __init__(
        self,
        driver: Driver,
        model_name: str = None,
        device: str = None
    ):
        """
        Initialize the embedding service.
        
        Args:
            driver: Neo4j driver instance
            model_name: Sentence transformer model name (defaults to latest)
            device: 'cuda', 'mps', or 'cpu' (auto-detected if None)
        """
        self.driver = driver
        self.model_name = model_name or self.DEFAULT_MODEL

        resolved_device = device or "cpu"
        self.model = self._get_or_load_model(self.model_name, resolved_device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        
        logger.info(
            f"Embedding service initialized: "
            f"model={self.model_name}, "
            f"dimension={self.embedding_dim}, "
            f"device={self.model.device}"
        )
    
    # ------------------------------------------------------------------
    # Text Generation for Embeddings
    # ------------------------------------------------------------------
    
    def _build_embedding_text(self, sub_attraction: Dict[str, Any]) -> str:
        """
        Build rich text representation for embedding generation.
        
        Combines multiple fields to create a semantic-rich representation:
        - Name and description
        - Category and type information
        - Location context
        - User sentiment (ratings, reviews)
        - Operational metadata
        
        Args:
            sub_attraction: Sub-attraction node data from Neo4j
            
        Returns:
            Rich text string for embedding
        """
        parts = []
        
        # Core identity
        name = sub_attraction.get("name", "")
        if name:
            parts.append(f"Place: {name}")
        
        # Editorial description (rich semantic content)
        description = sub_attraction.get("editorialSummary", "")
        if description:
            parts.append(f"Description: {description}")
        
        # Category and type information
        categories = []
        if sub_attraction.get("amenityType"):
            categories.append(sub_attraction["amenityType"])
        if sub_attraction.get("tourismType"):
            categories.append(sub_attraction["tourismType"])
        if sub_attraction.get("primaryType"):
            categories.append(sub_attraction["primaryType"])
        if sub_attraction.get("religion"):
            categories.append(f"{sub_attraction['religion']} place of worship")
        if sub_attraction.get("cuisine"):
            categories.append(f"{sub_attraction['cuisine']} cuisine")
        
        if categories:
            parts.append(f"Type: {', '.join(categories)}")
        
        # POI Groups (tourism categories)
        groups_raw = sub_attraction.get("groups", "")
        if groups_raw:
            try:
                if isinstance(groups_raw, str):
                    groups = json.loads(groups_raw) if groups_raw.startswith('[') else [groups_raw]
                else:
                    groups = groups_raw if isinstance(groups_raw, list) else []
                
                if groups:
                    parts.append(f"Categories: {', '.join(groups)}")
            except json.JSONDecodeError:
                pass
        
        # Location context
        location_parts = []
        if sub_attraction.get("city"):
            location_parts.append(sub_attraction["city"])
        if sub_attraction.get("district"):
            location_parts.append(sub_attraction["district"])
        if sub_attraction.get("province"):
            location_parts.append(sub_attraction["province"])
        
        if location_parts:
            parts.append(f"Location: {', '.join(location_parts)}")
        
        # Vicinity for contextual information
        if sub_attraction.get("vicinity"):
            parts.append(f"Area: {sub_attraction['vicinity']}")
        
        # User sentiment signals
        rating = sub_attraction.get("rating")
        ratings_total = sub_attraction.get("userRatingsTotal")
        if rating:
            sentiment = "highly rated" if rating >= 4.5 else "well-rated" if rating >= 4.0 else "rated"
            parts.append(f"Quality: {sentiment} ({rating}/5)")
            if ratings_total:
                parts.append(f"based on {ratings_total} reviews")
        
        # Price level context
        price_level = sub_attraction.get("priceLevel")
        if price_level is not None:
            price_desc = ["budget-friendly", "affordable", "moderate", "upscale", "luxury"]
            if 0 <= price_level < len(price_desc):
                parts.append(f"Price range: {price_desc[price_level]}")
        
        # Opening status (important for user experience)
        business_status = sub_attraction.get("businessStatus", "")
        if business_status == "OPERATIONAL":
            parts.append("Currently open to visitors")
        
        return " | ".join(parts)
    
    # ------------------------------------------------------------------
    # Embedding Generation
    # ------------------------------------------------------------------
    
    def generate_embedding(self, sub_attraction: Dict[str, Any]) -> np.ndarray:
        """
        Generate vector embedding for a single sub-attraction.
        
        Args:
            sub_attraction: Sub-attraction data dictionary
            
        Returns:
            Embedding vector as numpy array
        """
        text = self._build_embedding_text(sub_attraction)
        embedding = self.model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return embedding
    
    def generate_embeddings_batch(
        self,
        sub_attractions: List[Dict[str, Any]],
        batch_size: int = 32
    ) -> np.ndarray:
        """
        Generate embeddings for multiple sub-attractions efficiently.
        
        Args:
            sub_attractions: List of sub-attraction data dictionaries
            batch_size: Batch size for encoding (optimize for GPU memory)
            
        Returns:
            Array of embeddings with shape (num_attractions, embedding_dim)
        """
        texts = [self._build_embedding_text(sa) for sa in sub_attractions]
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=True
        )
        return embeddings
    
    def generate_query_embedding(self, query: str) -> np.ndarray:
        """
        Generate embedding for a search query.
        
        Args:
            query: Natural language search query
            
        Returns:
            Query embedding vector
        """
        embedding = self.model.encode(query, convert_to_numpy=True, show_progress_bar=False)
        return embedding
    
    # ------------------------------------------------------------------
    # Neo4j Integration
    # ------------------------------------------------------------------
    
    def store_embedding(
        self,
        place_id: str,
        embedding: np.ndarray
    ) -> bool:
        """
        Store embedding vector in Neo4j SubAttraction node.
        
        Args:
            place_id: Google Place ID (unique identifier)
            embedding: Embedding vector to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert numpy array to list for Neo4j storage
            embedding_list = embedding.tolist()
            
            cypher = """
            MATCH (s:SubAttraction {googlePlaceId: $placeId})
            SET s.embedding = $embedding,
                s.embeddingModel = $model,
                s.embeddingDimension = $dimension,
                s.embeddingUpdatedAt = datetime()
            RETURN s.name AS name
            """
            
            with self.driver.session() as session:
                result = session.run(
                    cypher,
                    placeId=place_id,
                    embedding=embedding_list,
                    model=self.model_name,
                    dimension=self.embedding_dim
                )
                record = result.single()
                if record:
                    logger.debug(f"Stored embedding for: {record['name']}")
                    return True
                else:
                    logger.warning(f"SubAttraction not found: {place_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to store embedding for {place_id}: {e}")
            return False
    
    def generate_and_store_all_embeddings(
        self,
        batch_size: int = 32,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate and store embeddings for all sub-attractions in the database.
        
        Args:
            batch_size: Batch size for processing
            limit: Optional limit on number of sub-attractions to process
            
        Returns:
            Statistics about the embedding generation process
        """
        logger.info("Starting batch embedding generation for all sub-attractions")
        
        try:
            # Fetch all sub-attractions
            cypher = """
            MATCH (s:SubAttraction)
            WHERE s.businessStatus IS NULL 
               OR s.businessStatus = '' 
               OR s.businessStatus = 'OPERATIONAL'
            RETURN s.googlePlaceId AS googlePlaceId,
                   s.name AS name,
                   s.editorialSummary AS editorialSummary,
                   s.amenityType AS amenityType,
                   s.tourismType AS tourismType,
                   s.primaryType AS primaryType,
                   s.religion AS religion,
                   s.cuisine AS cuisine,
                   s.groups AS groups,
                   s.city AS city,
                   s.district AS district,
                   s.province AS province,
                   s.vicinity AS vicinity,
                   s.rating AS rating,
                   s.userRatingsTotal AS userRatingsTotal,
                   s.priceLevel AS priceLevel,
                   s.businessStatus AS businessStatus
            """ + (f"LIMIT {limit}" if limit else "")
            
            with self.driver.session() as session:
                result = session.run(cypher)
                sub_attractions = [record.data() for record in result]
            
            if not sub_attractions:
                return {
                    "success": True,
                    "total": 0,
                    "processed": 0,
                    "failed": 0,
                    "message": "No sub-attractions found"
                }
            
            logger.info(f"Found {len(sub_attractions)} sub-attractions to process")
            
            # Process in batches
            total = len(sub_attractions)
            processed = 0
            failed = 0
            
            for i in range(0, total, batch_size):
                batch = sub_attractions[i:i + batch_size]
                
                try:
                    # Generate embeddings for batch
                    embeddings = self.generate_embeddings_batch(batch, batch_size=batch_size)
                    
                    # Store each embedding
                    for sub_attraction, embedding in zip(batch, embeddings):
                        place_id = sub_attraction["googlePlaceId"]
                        if self.store_embedding(place_id, embedding):
                            processed += 1
                        else:
                            failed += 1
                    
                    logger.info(f"Progress: {processed}/{total} embeddings stored")
                    
                except Exception as e:
                    logger.error(f"Batch processing failed at index {i}: {e}")
                    failed += len(batch)
            
            success_rate = (processed / total * 100) if total > 0 else 0
            
            logger.info(
                f"Embedding generation complete: "
                f"{processed}/{total} successful ({success_rate:.1f}%), "
                f"{failed} failed"
            )
            
            return {
                "success": True,
                "total": total,
                "processed": processed,
                "failed": failed,
                "success_rate": success_rate,
                "model": self.model_name,
                "dimension": self.embedding_dim,
                "message": f"Successfully generated embeddings for {processed} sub-attractions"
            }
            
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Embedding generation failed"
            }
    
    # ------------------------------------------------------------------
    # Vector Search
    # ------------------------------------------------------------------
    
    def vector_search(
        self,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        rejected_categories: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using Neo4j vector index.
        
        Args:
            query: Natural language search query
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of matching sub-attractions with similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self.generate_query_embedding(query)

            category_fields = (
                "node.groups",
                "node.amenityType",
                "node.shopType",
                "node.tourismType",
                "node.naturalType",
                "node.historicType",
                "node.primaryType",
                "node.placeTypes",
                "node.religion",
            )

            params: Dict[str, Any] = {
                "queryEmbedding": query_embedding.tolist(),
                "limit": limit,
                "threshold": similarity_threshold,
            }

            rejection_clauses = []
            for idx, rejected in enumerate(rejected_categories or []):
                reject_param = f"rejected{idx}"
                reject_conditions = " OR ".join(
                    f"toLower({field}) CONTAINS toLower(${reject_param})"
                    for field in category_fields
                )
                rejection_clauses.append(f"NOT ({reject_conditions})")
                params[reject_param] = rejected

            rejection_where = "\n            AND ".join(rejection_clauses)
            rejection_where = f"\n            AND {rejection_where}" if rejection_where else ""
            
            # Use Neo4j vector index for efficient similarity search
            cypher = f"""
            CALL db.index.vector.queryNodes(
                'sub_attraction_embeddings',
                $limit,
                $queryEmbedding
            ) YIELD node, score
            WHERE score >= $threshold
            {rejection_where}
            MATCH (node)-[:SUB_ATTRACTION_OF]->(a:Attraction)
            OPTIONAL MATCH (node)-[:LOCATED_IN]->(d:District)
            OPTIONAL MATCH (d)-[:IN_PROVINCE]->(p:Province)
            RETURN node.googlePlaceId AS googlePlaceId,
                   node.name AS name,
                   node.editorialSummary AS description,
                   node.primaryType AS category,
                   node.city AS city,
                   node.vicinity AS vicinity,
                   d.name AS district,
                   p.name AS province,
                   node.rating AS rating,
                   node.userRatingsTotal AS userRatingsTotal,
                   node.latitude AS latitude,
                   node.longitude AS longitude,
                   node.website AS website,
                   node.phone AS phone,
                   a.title AS parentAttraction,
                   score AS similarity
            ORDER BY score DESC
            LIMIT $limit
            """
            
            with self.driver.session() as session:
                result = session.run(cypher, params)
                results = [record.data() for record in result]
            
            logger.info(f"Vector search returned {len(results)} results for query: '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
