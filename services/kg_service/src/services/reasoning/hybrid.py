"""
Hybrid Reasoning Engine combining Symbolic (Cypher) and Neural (GNN) reasoning.

Provides explainable, confidence-scored reasoning by:
1. Symbolic: Deterministic rule-based Cypher queries
2. Neural: GNN embeddings for soft matching and predictions
3. Ensemble: Weighted combination with confidence scoring
4. Explainability: Evidence trails and reasoning chains
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

import numpy as np
from neo4j import Driver

from services.gnn_embeddings import GNNEmbeddingService

logger = logging.getLogger(__name__)


class HybridReasoningEngine:
    """Advanced reasoning engine combining symbolic and neural approaches.

    Features:
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
        neural_weight: float = 0.4,
    ):
        self.driver = driver
        self.gnn_service = gnn_service

        total = symbolic_weight + neural_weight
        self.symbolic_weight = symbolic_weight / total
        self.neural_weight = neural_weight / total

        logger.info(
            f"Hybrid Reasoning Engine initialized "
            f"(symbolic: {self.symbolic_weight:.2f}, neural: {self.neural_weight:.2f})"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reason_itinerary(
        self,
        start_location: str,
        end_location: str,
        constraints: Optional[Dict[str, Any]] = None,
        query_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Multi-domain reasoning for travel itinerary planning.

        Considers: Visa -> Transport -> Attractions -> Hotels -> Events
        """
        logger.info(f"Reasoning itinerary: {start_location} -> {end_location}")

        constraints = constraints or {}
        explanation_chain: list[dict] = []

        # Step 1: Symbolic path finding
        symbolic_result = self._symbolic_path_reasoning(start_location, end_location, constraints)
        explanation_chain.append({
            "step": 1,
            "method": "symbolic_path_finding",
            "result": symbolic_result.get("found", False),
            "confidence": symbolic_result.get("confidence", 0.0),
            "evidence": symbolic_result.get("path", []),
        })

        # Step 2: Neural similarity enhancement
        if self.gnn_service and self.gnn_service.node_embeddings is not None:
            neural_result = self._neural_similarity_reasoning(start_location, end_location)
            explanation_chain.append({
                "step": 2,
                "method": "neural_similarity",
                "result": neural_result.get("similar_entities", []),
                "confidence": neural_result.get("avg_confidence", 0.0),
            })

        # Step 3: Attraction discovery
        districts_on_route = symbolic_result.get("districts", [])
        attractions_result = self._find_attractions_on_route(
            districts_on_route, constraints.get("interests", [])
        )
        attraction_confidence = (
            attractions_result.get("confidence", 0.0) if districts_on_route else 0.0
        )
        explanation_chain.append({
            "step": 3,
            "method": "attraction_discovery",
            "result": len(attractions_result.get("attractions", [])),
            "confidence": attraction_confidence,
        })

        # Step 4: Temporal validity
        if query_date:
            temporal_result = self._check_temporal_validity(
                attractions_result.get("attractions", []), query_date
            )
            explanation_chain.append({
                "step": 4,
                "method": "temporal_validation",
                "result": temporal_result.get("valid_count", 0),
                "total_checked": len(attractions_result.get("attractions", [])),
                "confidence": 1.0,
            })

        # Step 5: Apply constraints
        final_itinerary = self._apply_constraints(
            attractions_result.get("attractions", []), constraints
        )

        # Confidence calculation
        overall_confidence = self._calculate_ensemble_confidence(explanation_chain)

        symbolic_confs = [
            s["confidence"] for s in explanation_chain if "symbolic" in s.get("method", "")
        ]
        neural_confs = [
            s["confidence"] for s in explanation_chain if "neural" in s.get("method", "")
        ]
        symbolic_avg = float(np.nanmean(symbolic_confs)) if symbolic_confs else 0.0
        neural_avg = float(np.nanmean(neural_confs)) if neural_confs else 0.0
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
                    "neural": self.neural_weight,
                },
            },
            "metadata": {
                "reasoning_engine": "HybridReasoningEngine",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    def predict_missing_relationship(
        self,
        entity1_name: str,
        entity2_name: str,
        relationship_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Predict if a relationship exists between two entities (hybrid approach)."""
        logger.info(f"Predicting relationship: {entity1_name} -> {entity2_name}")

        symbolic_result = self._check_relationship_exists(
            entity1_name, entity2_name, relationship_type
        )

        neural_result: Dict[str, Any] = {"exists": False, "confidence": 0.0}
        if self.gnn_service:
            neural_result = self._neural_link_prediction(entity1_name, entity2_name)

        if symbolic_result["exists"]:
            final_confidence = 1.0
            final_exists = True
            method = "symbolic_confirmed"
        else:
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
                    "neural": self.neural_weight,
                },
            },
        }

    # ------------------------------------------------------------------
    # Private: Symbolic reasoning
    # ------------------------------------------------------------------

    def _symbolic_path_reasoning(
        self, start: str, end: str, constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Cypher-based shortest-path finding."""
        try:
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
                    "confidence": 1.0,
                    "method": "cypher_shortest_path",
                }
            return {"found": False, "confidence": 0.0, "message": "No path found in knowledge graph"}

        except Exception as e:
            logger.error(f"Symbolic path reasoning failed: {e}")
            return {"found": False, "confidence": 0.0, "error": str(e)}

    def _check_relationship_exists(
        self, entity1: str, entity2: str, rel_type: Optional[str]
    ) -> Dict[str, Any]:
        """Check if a relationship exists in Neo4j."""
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
                    "method": "cypher_query",
                }
            return {"exists": False, "confidence": 0.0}

        except Exception as e:
            logger.error(f"Relationship check failed: {e}")
            return {"exists": False, "confidence": 0.0, "error": str(e)}

    # ------------------------------------------------------------------
    # Private: Neural reasoning
    # ------------------------------------------------------------------

    def _neural_similarity_reasoning(self, start: str, end: str) -> Dict[str, Any]:
        """Use GNN embeddings to find semantically similar entities."""
        try:
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

            similar_to_start = self.gnn_service.find_similar_entities(
                start_result["neo4j_id"], top_k=3
            )
            similar_to_end = self.gnn_service.find_similar_entities(
                end_result["neo4j_id"], top_k=3
            )

            all_sims = similar_to_start + similar_to_end
            avg_conf = float(np.mean([e["similarity"] for e in all_sims])) if all_sims else 0.0

            return {
                "similar_entities": {"near_start": similar_to_start, "near_end": similar_to_end},
                "avg_confidence": avg_conf,
                "method": "gnn_embedding_similarity",
            }

        except Exception as e:
            logger.error(f"Neural similarity reasoning failed: {e}")
            return {"similar_entities": [], "avg_confidence": 0.0, "error": str(e)}

    def _neural_link_prediction(self, entity1: str, entity2: str) -> Dict[str, Any]:
        """Use GNN to predict link probability."""
        try:
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

            return self.gnn_service.predict_link(e1_result["neo4j_id"], e2_result["neo4j_id"])

        except Exception as e:
            logger.error(f"Neural link prediction failed: {e}")
            return {"exists": False, "confidence": 0.0, "error": str(e)}

    # ------------------------------------------------------------------
    # Private: Route helpers
    # ------------------------------------------------------------------

    def _find_attractions_on_route(
        self, districts: List[str], interests: List[str]
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

            if interests:
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
                "confidence": 0.8,
                "method": "cypher_district_attractions",
            }

        except Exception as e:
            logger.error(f"Attraction discovery failed: {e}")
            return {"attractions": [], "count": 0, "confidence": 0.0}

    @staticmethod
    def _check_temporal_validity(
        entities: List[Dict[str, Any]], query_date: datetime
    ) -> Dict[str, Any]:
        """Check if entities are valid/available on *query_date* (placeholder)."""
        return {
            "valid_entities": entities,
            "invalid_entities": [],
            "valid_count": len(entities),
            "total_count": len(entities),
            "query_date": query_date.isoformat(),
            "method": "temporal_validity_check",
        }

    @staticmethod
    def _apply_constraints(
        entities: List[Dict[str, Any]], constraints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply user constraints to filter and rank entities."""
        filtered = list(entities)

        if "min_rating" in constraints:
            filtered = [e for e in filtered if (e.get("rating") or 0) >= constraints["min_rating"]]

        if "max_results" in constraints:
            filtered = filtered[: constraints["max_results"]]

        return filtered

    def _calculate_ensemble_confidence(self, explanation_chain: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence by combining symbolic and neural scores."""
        symbolic_confs = [
            s["confidence"]
            for s in explanation_chain
            if "symbolic" in s.get("method", "") and not np.isnan(s["confidence"])
        ]
        neural_confs = [
            s["confidence"]
            for s in explanation_chain
            if "neural" in s.get("method", "") and not np.isnan(s["confidence"])
        ]

        sym_avg = float(np.nanmean(symbolic_confs)) if symbolic_confs else 0.0
        neu_avg = float(np.nanmean(neural_confs)) if neural_confs else 0.0
        sym_avg = 0.0 if np.isnan(sym_avg) else sym_avg
        neu_avg = 0.0 if np.isnan(neu_avg) else neu_avg

        return float(self.symbolic_weight * sym_avg + self.neural_weight * neu_avg)
