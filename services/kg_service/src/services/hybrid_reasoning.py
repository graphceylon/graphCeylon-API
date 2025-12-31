"""
Hybrid Reasoning Engine combining Symbolic (Cypher) and Neural (GNN) reasoning.

This module provides explainable, confidence-scored reasoning by:
1. Symbolic: Deterministic rule-based Cypher queries
2. Neural: GNN embeddings for soft matching and predictions
3. Ensemble: Weighted combination with confidence scoring
4. Explainability: Evidence trails and reasoning chains
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from neo4j import Driver
import numpy as np

from .gnn_embeddings import GNNEmbeddingService
from models.graph.temporal import TemporalMetadata, ProvenanceMetadata

logger = logging.getLogger(__name__)


class HybridReasoningEngine:
    """
    Advanced reasoning engine combining symbolic and neural approaches.
    
    Key Features:
    - Multi-hop path finding with confidence scores
    - Temporal reasoning (valid on specific dates)
    - Constraint-aware planning (budget, time, preferences)
    - Link prediction and knowledge completion
    - Full explainability with evidence trails
    """
    
    def __init__(
        self,
        driver: Driver,
        gnn_service: Optional[GNNEmbeddingService] = None,
        symbolic_weight: float = 0.6,
        neural_weight: float = 0.4
    ):
        """
        Initialize hybrid reasoning engine.
        
        Args:
            driver: Neo4j driver
            gnn_service: GNN embedding service (optional)
            symbolic_weight: Weight for symbolic reasoning (0-1)
            neural_weight: Weight for neural reasoning (0-1)
        """
        self.driver = driver
        self.gnn_service = gnn_service
        self.symbolic_weight = symbolic_weight
        self.neural_weight = neural_weight
        
        # Ensure weights sum to 1
        total = symbolic_weight + neural_weight
        self.symbolic_weight /= total
        self.neural_weight /= total
        
        logger.info(
            f"Hybrid Reasoning Engine initialized "
            f"(symbolic: {self.symbolic_weight:.2f}, neural: {self.neural_weight:.2f})"
        )
    
    def reason_itinerary(
        self,
        start_location: str,
        end_location: str,
        constraints: Optional[Dict[str, Any]] = None,
        query_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Multi-domain reasoning for travel itinerary planning.
        
        Considers: Visa -> Transport -> Attractions -> Hotels -> Events
        
        Args:
            start_location: Starting location (District/Province)
            end_location: Destination location
            constraints: Optional constraints (budget, time, interests, etc.)
            query_date: Date for temporal validity checks
            
        Returns:
            Comprehensive itinerary with reasoning explanation
        """
        logger.info(f"Reasoning itinerary: {start_location} -> {end_location}")
        
        constraints = constraints or {}
        explanation_chain = []
        
        # Step 1: Symbolic - Find geographic path
        symbolic_result = self._symbolic_path_reasoning(
            start_location, end_location, constraints
        )
        
        explanation_chain.append({
            "step": 1,
            "method": "symbolic_path_finding",
            "result": symbolic_result.get("found", False),
            "confidence": symbolic_result.get("confidence", 0.0),
            "evidence": symbolic_result.get("path", [])
        })
        
        # Step 2: Neural - Enhance with similarity-based suggestions
        if self.gnn_service and self.gnn_service.node_embeddings is not None:
            neural_result = self._neural_similarity_reasoning(
                start_location, end_location
            )
            
            explanation_chain.append({
                "step": 2,
                "method": "neural_similarity",
                "result": neural_result.get("similar_entities", []),
                "confidence": neural_result.get("avg_confidence", 0.0)
            })
        
        # Step 3: Find attractions along the route
        districts_on_route = symbolic_result.get("districts", [])
        attractions_result = self._find_attractions_on_route(
            districts_on_route,
            constraints.get("interests", [])
        )
        
        # Default to 0 confidence if no districts found
        attraction_confidence = attractions_result.get("confidence", 0.0) if districts_on_route else 0.0
        
        explanation_chain.append({
            "step": 3,
            "method": "attraction_discovery",
            "result": len(attractions_result.get("attractions", [])),
            "confidence": attraction_confidence
        })
        
        # Step 4: Check temporal validity
        if query_date:
            temporal_result = self._check_temporal_validity(
                attractions_result.get("attractions", []),
                query_date
            )
            
            explanation_chain.append({
                "step": 4,
                "method": "temporal_validation",
                "result": temporal_result.get("valid_count", 0),
                "total_checked": len(attractions_result.get("attractions", [])),
                "confidence": 1.0
            })
        
        # Step 5: Apply constraints
        final_itinerary = self._apply_constraints(
            attractions_result.get("attractions", []),
            constraints
        )
        
        # Calculate overall confidence and breakdown
        overall_confidence = self._calculate_ensemble_confidence(explanation_chain)
        
        # Calculate symbolic and neural confidence separately
        symbolic_confidences = [
            step["confidence"]
            for step in explanation_chain
            if "symbolic" in step.get("method", "")
        ]
        neural_confidences = [
            step["confidence"]
            for step in explanation_chain
            if "neural" in step.get("method", "")
        ]
        
        symbolic_avg = float(np.nanmean(symbolic_confidences)) if symbolic_confidences else 0.0
        neural_avg = float(np.nanmean(neural_confidences)) if neural_confidences else 0.0
        
        # Ensure no NaN
        symbolic_avg = 0.0 if np.isnan(symbolic_avg) else symbolic_avg
        neural_avg = 0.0 if np.isnan(neural_avg) else neural_avg
        
        return {
            "itinerary": final_itinerary,
            "attractions": attractions_result.get("attractions", []),
            "start": start_location,
            "end": end_location,
            "query_date": query_date.isoformat() if query_date else None,
            "overall_confidence": overall_confidence,
            "symbolic_confidence": symbolic_avg,
            "neural_confidence": neural_avg,
            "explanation": {
                "method": "hybrid_symbolic_neural_reasoning",
                "chain": explanation_chain,
                "weights": {
                    "symbolic": self.symbolic_weight,
                    "neural": self.neural_weight
                }
            },
            "metadata": {
                "reasoning_engine": "HybridReasoningEngine",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    
    def _symbolic_path_reasoning(
        self,
        start: str,
        end: str,
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute symbolic Cypher-based path finding."""
        try:
            # Multi-hop query considering districts and provinces
            cypher = """
            MATCH (start)
            WHERE (start:District OR start:Province) AND start.name = $start
            MATCH (end)
            WHERE (end:District OR end:Province) AND end.name = $end
            MATCH path = shortestPath((start)-[*1..5]-(end))
            
            WITH path, nodes(path) AS path_nodes, relationships(path) AS path_rels
            
            OPTIONAL MATCH (d:District) WHERE d IN path_nodes
            
            RETURN 
                [n IN path_nodes | {
                    id: elementId(n),
                    labels: labels(n),
                    name: coalesce(n.name, n.title, 'Unknown')
                }] AS nodes,
                [r IN path_rels | type(r)] AS relationships,
                collect(DISTINCT d.name) AS districts
            LIMIT 1
            """
            
            with self.driver.session() as session:
                result = session.run(cypher, {"start": start, "end": end})
                record = result.single()
            
            if record:
                return {
                    "found": True,
                    "path": record["nodes"],
                    "relationships": record["relationships"],
                    "districts": record["districts"],
                    "confidence": 1.0,  # Symbolic reasoning is deterministic
                    "method": "cypher_shortest_path"
                }
            else:
                return {
                    "found": False,
                    "confidence": 0.0,
                    "message": "No path found in knowledge graph"
                }
                
        except Exception as e:
            logger.error(f"Symbolic path reasoning failed: {e}")
            return {"found": False, "confidence": 0.0, "error": str(e)}
    
    def _neural_similarity_reasoning(
        self,
        start: str,
        end: str
    ) -> Dict[str, Any]:
        """Use GNN embeddings to find semantically similar entities."""
        try:
            # Get Neo4j IDs for start and end
            cypher = """
            MATCH (n) 
            WHERE n.name = $name OR n.title = $name
            RETURN elementId(n) AS neo4j_id
            LIMIT 1
            """
            
            with self.driver.session() as session:
                start_result = session.run(cypher, {"name": start}).single()
                end_result = session.run(cypher, {"name": end}).single()
            
            if not start_result or not end_result:
                return {"similar_entities": [], "avg_confidence": 0.0}
            
            start_id = start_result["neo4j_id"]
            end_id = end_result["neo4j_id"]
            
            # Find similar entities using GNN
            similar_to_start = self.gnn_service.find_similar_entities(start_id, top_k=3)
            similar_to_end = self.gnn_service.find_similar_entities(end_id, top_k=3)
            
            avg_conf = np.mean([e["similarity"] for e in similar_to_start + similar_to_end])
            
            return {
                "similar_entities": {
                    "near_start": similar_to_start,
                    "near_end": similar_to_end
                },
                "avg_confidence": float(avg_conf),
                "method": "gnn_embedding_similarity"
            }
            
        except Exception as e:
            logger.error(f"Neural similarity reasoning failed: {e}")
            return {"similar_entities": [], "avg_confidence": 0.0, "error": str(e)}
    
    def _find_attractions_on_route(
        self,
        districts: List[str],
        interests: List[str]
    ) -> Dict[str, Any]:
        """Find attractions in districts along route."""
        try:
            cypher = """
            MATCH (d:District)-[:HAS_ATTRACTION|LOCATED_IN*1..2]-(a:Attraction)
            WHERE d.name IN $districts
            
            WITH a, d
            ORDER BY a.rating DESC
            
            RETURN 
                a.title AS title,
                a.description AS description,
                a.rating AS rating,
                a.latitude AS latitude,
                a.longitude AS longitude,
                d.name AS district,
                labels(a) AS types
            LIMIT 20
            """
            
            with self.driver.session() as session:
                result = session.run(cypher, {"districts": districts})
                attractions = [dict(record) for record in result]
            
            # Filter by interests if provided
            if interests:
                # Simple keyword matching (can be enhanced with NLP)
                filtered = [
                    a for a in attractions
                    if any(
                        interest.lower() in (a.get("description") or "").lower()
                        for interest in interests
                    )
                ]
                attractions = filtered if filtered else attractions
            
            return {
                "attractions": attractions,
                "count": len(attractions),
                "confidence": 0.8,  # High confidence for direct queries
                "method": "cypher_district_attractions"
            }
            
        except Exception as e:
            logger.error(f"Attraction discovery failed: {e}")
            return {"attractions": [], "count": 0, "confidence": 0.0}
    
    def _check_temporal_validity(
        self,
        entities: List[Dict[str, Any]],
        query_date: datetime
    ) -> Dict[str, Any]:
        """Check if entities are valid/available on query date."""
        # In production, query Neo4j for temporal properties
        # For now, assume all are valid (placeholder)
        
        valid_entities = []
        invalid_entities = []
        
        for entity in entities:
            # Placeholder logic - in production, check actual temporal metadata
            is_valid = True  # Query from Neo4j
            
            if is_valid:
                valid_entities.append(entity)
            else:
                invalid_entities.append(entity)
        
        return {
            "valid_entities": valid_entities,
            "invalid_entities": invalid_entities,
            "valid_count": len(valid_entities),
            "total_count": len(entities),
            "query_date": query_date.isoformat(),
            "method": "temporal_validity_check"
        }
    
    def _apply_constraints(
        self,
        entities: List[Dict[str, Any]],
        constraints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply user constraints to filter and rank entities."""
        filtered = entities.copy()
        
        # Budget constraint
        if "max_budget" in constraints:
            # Filter by price (placeholder - needs actual pricing data)
            pass
        
        # Time constraint
        if "max_time_hours" in constraints:
            # Filter by travel time (placeholder)
            pass
        
        # Rating constraint
        if "min_rating" in constraints:
            min_rating = constraints["min_rating"]
            filtered = [e for e in filtered if (e.get("rating") or 0) >= min_rating]
        
        # Limit results
        if "max_results" in constraints:
            filtered = filtered[:constraints["max_results"]]
        
        return filtered
    
    def _calculate_ensemble_confidence(
        self,
        explanation_chain: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall confidence by combining symbolic and neural scores."""
        symbolic_confidences = [
            step["confidence"]
            for step in explanation_chain
            if "symbolic" in step.get("method", "") and not np.isnan(step["confidence"])
        ]
        
        neural_confidences = [
            step["confidence"]
            for step in explanation_chain
            if "neural" in step.get("method", "") and not np.isnan(step["confidence"])
        ]
        
        # Use nanmean to handle any remaining NaN values safely
        symbolic_avg = float(np.nanmean(symbolic_confidences)) if symbolic_confidences else 0.0
        neural_avg = float(np.nanmean(neural_confidences)) if neural_confidences else 0.0
        
        # Ensure no NaN in averages
        symbolic_avg = 0.0 if np.isnan(symbolic_avg) else symbolic_avg
        neural_avg = 0.0 if np.isnan(neural_avg) else neural_avg
        
        # Weighted ensemble
        overall = (
            self.symbolic_weight * symbolic_avg +
            self.neural_weight * neural_avg
        )
        
        return float(overall)
    
    def predict_missing_relationship(
        self,
        entity1_name: str,
        entity2_name: str,
        relationship_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Predict if a relationship exists between two entities.
        
        Uses hybrid approach:
        1. Check if relationship exists in KG (symbolic)
        2. Use GNN to predict likelihood (neural)
        3. Combine results with confidence
        """
        logger.info(f"Predicting relationship: {entity1_name} -> {entity2_name}")
        
        # Step 1: Symbolic check
        symbolic_result = self._check_relationship_exists(
            entity1_name, entity2_name, relationship_type
        )
        
        # Step 2: Neural prediction
        neural_result = {"exists": False, "confidence": 0.0}
        if self.gnn_service:
            neural_result = self._neural_link_prediction(entity1_name, entity2_name)
        
        # Step 3: Ensemble
        if symbolic_result["exists"]:
            # Relationship confirmed in KG
            final_confidence = 1.0
            final_exists = True
            method = "symbolic_confirmed"
        else:
            # Use neural prediction
            final_confidence = neural_result["confidence"]
            final_exists = neural_result["exists"]
            method = "neural_prediction"
        
        return {
            "entity1": entity1_name,
            "entity2": entity2_name,
            "relationship_type": relationship_type,
            "exists": final_exists,
            "confidence": final_confidence,
            "explanation": {
                "method": method,
                "symbolic": symbolic_result,
                "neural": neural_result,
                "ensemble_weights": {
                    "symbolic": self.symbolic_weight,
                    "neural": self.neural_weight
                }
            }
        }
    
    def _check_relationship_exists(
        self,
        entity1: str,
        entity2: str,
        rel_type: Optional[str]
    ) -> Dict[str, Any]:
        """Check if relationship exists in Neo4j."""
        try:
            rel_filter = f":{rel_type}" if rel_type else ""
            
            cypher = f"""
            MATCH (a)-[r{rel_filter}]-(b)
            WHERE (a.name = $e1 OR a.title = $e1)
              AND (b.name = $e2 OR b.title = $e2)
            RETURN type(r) AS rel_type, count(r) AS count
            """
            
            with self.driver.session() as session:
                result = session.run(cypher, {"e1": entity1, "e2": entity2})
                record = result.single()
            
            if record and record["count"] > 0:
                return {
                    "exists": True,
                    "relationship_type": record["rel_type"],
                    "confidence": 1.0,
                    "method": "cypher_query"
                }
            else:
                return {"exists": False, "confidence": 0.0}
                
        except Exception as e:
            logger.error(f"Relationship check failed: {e}")
            return {"exists": False, "confidence": 0.0, "error": str(e)}
    
    def _neural_link_prediction(
        self,
        entity1: str,
        entity2: str
    ) -> Dict[str, Any]:
        """Use GNN to predict link probability."""
        try:
            # Get Neo4j IDs
            cypher = """
            MATCH (n) 
            WHERE n.name = $name OR n.title = $name
            RETURN elementId(n) AS neo4j_id
            LIMIT 1
            """
            
            with self.driver.session() as session:
                e1_result = session.run(cypher, {"name": entity1}).single()
                e2_result = session.run(cypher, {"name": entity2}).single()
            
            if not e1_result or not e2_result:
                return {"exists": False, "confidence": 0.0}
            
            e1_id = e1_result["neo4j_id"]
            e2_id = e2_result["neo4j_id"]
            
            # Predict link using GNN
            result = self.gnn_service.predict_link(e1_id, e2_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Neural link prediction failed: {e}")
            return {"exists": False, "confidence": 0.0, "error": str(e)}
