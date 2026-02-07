"""Symbolic reasoning engine for the Knowledge Graph application.

Provides Cypher-based graph traversal, constraint reasoning, vector search,
SHACL validation, and attraction similarity/profiling.
"""

import logging
from typing import List, Dict, Any, Optional

from neo4j import Driver

logger = logging.getLogger(__name__)


class ReasoningOrchestrator:
    """Dispatches symbolic (Cypher) and lightweight predictive reasoning
    and builds explanation trails.
    """

    def __init__(self, driver: Driver):
        self.driver = driver

    # ------------------------------------------------------------------
    # Symbolic path reasoning
    # ------------------------------------------------------------------

    def symbolic_reason(self, start: str, end: str) -> Dict[str, Any]:
        """Find multi-hop paths between a Province and a District."""
        try:
            logger.info(f"Starting symbolic reasoning from {start} to {end}")

            cypher = (
                "MATCH path=shortestPath((p:Province {name:$start})-[*..4]-(t:District {name:$end})) "
                "RETURN [n IN nodes(path) | {id:elementId(n), labels:labels(n), name:coalesce(n.name,'')} ] AS nodes, "
                "[r IN relationships(path) | type(r)] AS rels LIMIT 1"
            )

            with self.driver.session() as session:
                result = session.run(cypher, {"start": start, "end": end})
                rows = [record.data() for record in result]

            explanation: list[dict] = []
            path_result = None

            if rows:
                path_result = rows[0]
                explanation.append({
                    "rule": "multi-hop-shortestPath",
                    "path_nodes": path_result.get("nodes"),
                    "path_rels": path_result.get("rels"),
                    "evidence_count": len(path_result.get("nodes", [])),
                })
                logger.info(f"Found path with {len(path_result.get('nodes', []))} nodes")
            else:
                explanation.append({
                    "rule": "no-path-found",
                    "message": f"No connecting path found between {start} and {end}",
                })
                logger.info(f"No path found between {start} and {end}")

            return {"result": path_result, "explanation": explanation}

        except Exception as e:
            logger.error(f"Symbolic reasoning failed: {e}")
            return {
                "result": None,
                "explanation": [{"rule": "error", "message": f"Reasoning failed: {str(e)}"}],
            }

    # ------------------------------------------------------------------
    # Constraint-based reasoning
    # ------------------------------------------------------------------

    def constraint_reason(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Find districts/provinces matching criteria (province, pattern, counts)."""
        try:
            logger.info(f"Starting constraint-based reasoning with constraints: {constraints}")

            base_query = "MATCH (p:Province)-[:HAS_DISTRICT]->(d:District)"
            where_clauses: list[str] = []
            params: dict = {}

            if "province" in constraints:
                where_clauses.append("p.name = $province")
                params["province"] = constraints["province"]

            if "district_pattern" in constraints:
                where_clauses.append("d.name =~ $pattern")
                params["pattern"] = constraints["district_pattern"]

            if where_clauses:
                base_query += " WHERE " + " AND ".join(where_clauses)

            query = base_query + " RETURN p.name AS province, collect(d.name) AS districts"

            if "min_districts" in constraints or "max_districts" in constraints:
                query += ", size(collect(d)) AS district_count"
                if "min_districts" in constraints:
                    query += f" AND size(collect(d)) >= {constraints['min_districts']}"
                if "max_districts" in constraints:
                    query += f" AND size(collect(d)) <= {constraints['max_districts']}"

            query += " ORDER BY province"

            with self.driver.session() as session:
                result = session.run(query, params)
                data = [record.data() for record in result]

            logger.info(f"Constraint reasoning found {len(data)} results")
            return {
                "result": data,
                "explanation": {
                    "method": "constraint-based-filtering",
                    "constraints_applied": constraints,
                    "results_found": len(data),
                    "evidence": "Direct graph traversal with filters",
                },
            }

        except Exception as e:
            logger.error(f"Constraint reasoning failed: {e}")
            return {
                "result": [],
                "explanation": {
                    "method": "error",
                    "constraints": constraints,
                    "error": str(e),
                },
            }

    # ------------------------------------------------------------------
    # Vector reasoning
    # ------------------------------------------------------------------

    def vector_reason_similar(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Find similar attractions using vector search."""
        try:
            from services.embeddings import embedding_service
            from core.config import settings

            logger.info(f"Starting vector reasoning for query: '{query}'")
            query_embedding = embedding_service.generate_embedding(query)

            if not query_embedding:
                return {
                    "result": [],
                    "explanation": {
                        "method": "vector-search",
                        "message": "Failed to generate embedding for query",
                    },
                }

            cypher = f"""
            CALL db.index.vector.queryNodes('{settings.vector_index_name}', $top_k, $embedding)
            YIELD node, score
            RETURN node.title AS title,
                   node.description AS description,
                   node.imageUrl AS imageUrl,
                   node.rating AS rating,
                   node.latitude AS latitude,
                   node.longitude AS longitude,
                   node.district AS district,
                   node.province AS province,
                   node.formattedAddress AS formattedAddress,
                   node.googlePlaceId AS googlePlaceId,
                   node.website AS website,
                   node.phoneNumber AS phoneNumber,
                   node.priceLevel AS priceLevel,
                   node.placeTypes AS placeTypes,
                   node.googleMapsUrl AS googleMapsUrl,
                   node.googleMapsDirectionsUrl AS googleMapsDirectionsUrl,
                   node.googleEarthUrl AS googleEarthUrl,
                   node.userRatingsTotal AS userRatingsTotal,
                   node.editorialSummary AS editorialSummary,
                   node.placeUrl AS placeUrl,
                   score
            """

            with self.driver.session() as session:
                result = session.run(cypher, {"embedding": query_embedding, "top_k": top_k})
                matches = [record.data() for record in result]

            logger.info(f"Vector search found {len(matches)} results")
            return {
                "result": matches,
                "explanation": {
                    "method": "cosine-similarity-vector-search",
                    "query": query,
                    "results_found": len(matches),
                    "model": settings.embedding_model_name,
                },
            }

        except Exception as e:
            logger.error(f"Vector reasoning failed: {e}")
            return {
                "result": [],
                "explanation": {"method": "error", "query": query, "error": str(e)},
            }

    # ------------------------------------------------------------------
    # SHACL validation
    # ------------------------------------------------------------------

    def shacl_validate(self) -> Dict[str, Any]:
        """Run SHACL validation via n10s and return violations."""
        try:
            logger.info("Running SHACL validation...")
            with self.driver.session() as session:
                result = session.run("CALL n10s.validation.shacl.validate();")
                violations = [record.data() for record in result]

            logger.info(f"SHACL validation completed with {len(violations)} violations")
            return {
                "conforms": len(violations) == 0,
                "violations": violations,
                "violation_count": len(violations),
            }

        except Exception as e:
            logger.error(f"SHACL validation failed: {e}")
            return {
                "conforms": False,
                "violations": [],
                "violation_count": 0,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Attraction helpers
    # ------------------------------------------------------------------

    def find_attractions_near_path(
        self, start: str, end: str, max_distance_km: float = 50
    ) -> Dict[str, Any]:
        """Find attractions near the path between two districts."""
        try:
            logger.info(f"Finding attractions near path from {start} to {end}")

            cypher = """
            MATCH (d1:District {name: $start})
            MATCH (d2:District {name: $end})
            MATCH (a:Attraction)
            WHERE a.latitude IS NOT NULL AND a.longitude IS NOT NULL
            OPTIONAL MATCH (a)-[:LOCATED_IN]->(d:District)
            WHERE d.name = $start OR d.name = $end
            WITH a, d, d1, d2,
                 CASE WHEN d IS NOT NULL THEN 0 ELSE 1 END AS priority
            RETURN a.title AS attraction,
                   a.description AS description,
                   a.latitude AS latitude,
                   a.longitude AS longitude,
                   a.rating AS rating,
                   d.name AS district,
                   priority
            ORDER BY priority, a.rating DESC
            LIMIT 10
            """

            with self.driver.session() as session:
                result = session.run(cypher, {
                    "start": start,
                    "end": end,
                    "max_distance": max_distance_km,
                })
                attractions = [record.data() for record in result]

            logger.info(f"Found {len(attractions)} attractions near path")
            return {
                "result": attractions,
                "explanation": {
                    "method": "geospatial-path-reasoning",
                    "start_district": start,
                    "end_district": end,
                    "max_distance_km": max_distance_km,
                    "attractions_found": len(attractions),
                },
            }

        except Exception as e:
            logger.error(f"Failed to find attractions near path: {e}")
            return {
                "result": [],
                "explanation": {"method": "error", "error": str(e)},
            }

    def recommend_attractions_by_similarity(
        self, attraction_name: str, top_k: int = 5
    ) -> Dict[str, Any]:
        """Recommend similar attractions based on district, province, and rating."""
        try:
            logger.info(f"Finding similar attractions to '{attraction_name}'")

            cypher = """
            MATCH (a1:Attraction {title: $attraction_name})
            MATCH (a2:Attraction)
            WHERE a1 <> a2
            OPTIONAL MATCH (a1)-[:LOCATED_IN]->(d1:District)
            OPTIONAL MATCH (a2)-[:LOCATED_IN]->(d2:District)
            OPTIONAL MATCH (a1)-[:IN_PROVINCE]->(p1:Province)
            OPTIONAL MATCH (a2)-[:IN_PROVINCE]->(p2:Province)
            WITH a1, a2, d1, d2, p1, p2,
                 CASE WHEN d1 = d2 THEN 0.5 ELSE 0 END AS district_score,
                 CASE WHEN p1 = p2 THEN 0.3 ELSE 0 END AS province_score,
                 CASE
                     WHEN a1.rating IS NOT NULL AND a2.rating IS NOT NULL
                     THEN 0.2 * (1 - abs(a1.rating - a2.rating) / 5.0)
                     ELSE 0
                 END AS rating_score
            WITH a2,
                 d2.name AS district,
                 p2.name AS province,
                 a2.rating AS rating,
                 a2.description AS description,
                 (district_score + province_score + rating_score) AS similarity_score
            WHERE similarity_score > 0
            RETURN a2.title AS attraction,
                   description,
                   rating,
                   district,
                   province,
                   similarity_score
            ORDER BY similarity_score DESC
            LIMIT $top_k
            """

            with self.driver.session() as session:
                result = session.run(cypher, {
                    "attraction_name": attraction_name,
                    "top_k": top_k,
                })
                similar = [record.data() for record in result]

            logger.info(f"Found {len(similar)} similar attractions")
            return {
                "result": similar,
                "explanation": {
                    "method": "multi-factor-similarity",
                    "query": attraction_name,
                    "factors": ["district_match", "province_match", "rating_similarity"],
                    "results_found": len(similar),
                },
            }

        except Exception as e:
            logger.error(f"Failed to recommend similar attractions: {e}")
            return {
                "result": [],
                "explanation": {"method": "error", "error": str(e)},
            }

    def analyze_district_tourism_profile(self, district_name: str) -> Dict[str, Any]:
        """Analyze tourism profile of a district based on its attractions."""
        try:
            logger.info(f"Analyzing tourism profile for district: {district_name}")

            cypher = """
            MATCH (d:District {name: $district_name})
            OPTIONAL MATCH (d)<-[:LOCATED_IN]-(a:Attraction)
            WITH d, collect(a) AS attractions,
                 count(a) AS attraction_count,
                 avg(a.rating) AS avg_rating,
                 sum(CASE WHEN a.latitude IS NOT NULL THEN 1 ELSE 0 END) AS geocoded_count
            MATCH (d)-[:IN_PROVINCE]->(p:Province)
            RETURN d.name AS district,
                   p.name AS province,
                   attraction_count,
                   avg_rating,
                   geocoded_count,
                   [a IN attractions | a.title] AS attraction_names,
                   CASE
                       WHEN attraction_count = 0 THEN 'No data'
                       WHEN attraction_count < 3 THEN 'Low tourism'
                       WHEN attraction_count < 6 THEN 'Moderate tourism'
                       ELSE 'High tourism'
                   END AS tourism_level
            """

            with self.driver.session() as session:
                result = session.run(cypher, {"district_name": district_name})
                profile_data = [record.data() for record in result]

            if not profile_data:
                return {
                    "result": None,
                    "explanation": {
                        "method": "tourism-profile-analysis",
                        "district": district_name,
                        "message": "District not found",
                    },
                }

            profile = profile_data[0]
            logger.info(f"Tourism profile analysis complete for {district_name}")
            return {
                "result": profile,
                "explanation": {
                    "method": "tourism-profile-analysis",
                    "district": district_name,
                    "metrics": {
                        "total_attractions": profile["attraction_count"],
                        "average_rating": (
                            round(profile["avg_rating"], 2) if profile["avg_rating"] else None
                        ),
                        "geocoded_percentage": round(
                            (profile["geocoded_count"] / max(profile["attraction_count"], 1)) * 100,
                            1,
                        ),
                        "tourism_level": profile["tourism_level"],
                    },
                },
            }

        except Exception as e:
            logger.error(f"Failed to analyze tourism profile: {e}")
            return {
                "result": None,
                "explanation": {"method": "error", "error": str(e)},
            }
