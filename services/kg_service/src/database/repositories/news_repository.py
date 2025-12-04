"""Repository for news article-related database operations."""

import logging
import datetime
from typing import Dict, List, Any
from pathlib import Path
from .base import BaseRepository

logger = logging.getLogger(__name__)


class NewsRepository(BaseRepository):
    """Handle all news article-related database operations."""
    
    def load_schema(self) -> Dict[str, Any]:
        """Load tourism news schema (constraints and indexes)."""
        try:
            logger.info("Loading news schema...")
            schema_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "scripts" / "init_news_schema.cypher"
            
            if not schema_path.exists():
                raise FileNotFoundError(f"News schema file not found: {schema_path}")
            
            self.execute_cypher_file(str(schema_path))
            
            logger.info("News schema loaded successfully")
            return {"success": True, "message": "News schema loaded"}
            
        except Exception as e:
            logger.error(f"Failed to load news schema: {e}")
            raise
    
    def load_from_json(self) -> Dict[str, Any]:
        """Load tourism news from JSON file."""
        try:
            logger.info("Loading news from JSON...")
            
            apoc_check = self.execute_cypher("RETURN apoc.version() AS version;")
            if not apoc_check:
                raise Exception("APOC plugin is not available. Please ensure it's installed.")
            
            logger.info(f"APOC version: {apoc_check[0].get('version', 'unknown')}")
            
            load_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "scripts" / "load_news.cypher"
            
            if not load_path.exists():
                raise FileNotFoundError(f"News load script not found: {load_path}")
            
            with open(load_path, 'r', encoding='utf-8') as file:
                cypher_content = file.read()
            
            cypher_content = cypher_content.replace("'file: ///", "'file:///")
            lines = cypher_content.split('\n')
            cleaned_lines = [line for line in lines if line.strip() and not line.strip().startswith('//')]
            cleaned_content = '\n'.join(cleaned_lines)
            
            statements = [stmt.strip() for stmt in cleaned_content.split(';') if stmt.strip()]
            
            logger.info(f"Found {len(statements)} statements to execute")
            
            for i, stmt in enumerate(statements):
                if stmt:
                    try:
                        result = self.execute_cypher(stmt)
                        if i < 3:
                            logger.debug(f"Statement {i+1} executed successfully")
                    except Exception as e:
                        logger.warning(f"Statement {i+1} execution warning: {e}")
                        continue
            
            stats = self.get_statistics()
            
            logger.info(f"News loaded successfully")
            return {
                "success": True,
                "message": "News loaded from JSON",
                "statistics": stats
            }
            
        except Exception as e:
            logger.error(f"Failed to load news: {e}")
            raise
    
    def query(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query news articles with various filters."""
        try:
            logger.info(f"Querying news with filters: {filters}")
            
            match_clause = "MATCH (n:NewsArticle)"
            where_clauses = []
            params = {}
            
            if filters.get("title"):
                where_clauses.append("toLower(n.title) CONTAINS toLower($title)")
                params["title"] = filters["title"]
            
            if filters.get("category"):
                where_clauses.append("n.category = $category")
                params["category"] = filters["category"]
            
            if filters.get("year"):
                where_clauses.append("n.year = $year")
                params["year"] = filters["year"]
            
            if filters.get("month"):
                where_clauses.append("n.month = $month")
                params["month"] = filters["month"]
            
            if filters.get("date_from"):
                where_clauses.append("n.date >= date($date_from)")
                params["date_from"] = filters["date_from"]
            
            if filters.get("date_to"):
                where_clauses.append("n.date <= date($date_to)")
                params["date_to"] = filters["date_to"]
            
            where_clause = ""
            if where_clauses:
                where_clause = "WHERE " + " AND ".join(where_clauses)
            
            return_clause = """
            RETURN n {
                .*,
                id: id(n),
                date: toString(n.date)
            } as article
            ORDER BY n.date DESC
            """
            
            limit = filters.get("limit", 20)
            params["limit"] = limit
            limit_clause = "LIMIT $limit"
            
            cypher = f"{match_clause} {where_clause} {return_clause} {limit_clause}"
            
            result = self.execute_cypher(cypher, params)
            articles = [r["article"] for r in result]
            
            return articles
            
        except Exception as e:
            logger.error(f"Failed to query news: {e}")
            raise
    
    def create(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new news article."""
        try:
            logger.info(f"Creating news article: {news_data.get('title')}")
            
            article_id = f"news_{news_data['title'].lower().replace(' ', '_')[:50]}_{datetime.datetime.now().timestamp()}"
            
            date_obj = None
            year, month, day = None, None, None
            if news_data.get("date"):
                try:
                    date_obj = datetime.datetime.strptime(news_data["date"], "%Y-%m-%d")
                    year = date_obj.year
                    month = date_obj.month
                    day = date_obj.day
                except:
                    logger.warning(f"Invalid date format: {news_data['date']}")
            
            cypher = """
            CREATE (n:NewsArticle {
                id: $id,
                title: $title,
                date: CASE WHEN $date IS NOT NULL THEN date($date) ELSE NULL END,
                image_url: $image_url,
                content: $content,
                read_more_url: $read_more_url,
                category: $category,
                tags: $tags,
                year: $year,
                month: $month,
                day: $day,
                created_at: datetime()
            })
            RETURN id(n) as node_id, n.id as article_id
            """
            
            params = {
                "id": article_id,
                "title": news_data["title"],
                "date": news_data.get("date"),
                "image_url": news_data.get("image_url"),
                "content": news_data.get("content"),
                "read_more_url": news_data.get("read_more_url"),
                "category": news_data.get("category"),
                "tags": news_data.get("tags", []),
                "year": year,
                "month": month,
                "day": day
            }
            
            result = self.execute_cypher(cypher, params)
            
            if year:
                self.execute_cypher("""
                    MATCH (n:NewsArticle {id: $article_id})
                    MERGE (y:Year {year: $year})
                    MERGE (n)-[:PUBLISHED_IN_YEAR]->(y)
                """, {"article_id": article_id, "year": year})
                
                if month:
                    self.execute_cypher("""
                        MATCH (n:NewsArticle {id: $article_id})
                        MATCH (y:Year {year: $year})
                        MERGE (m:Month {month: $month, year: $year})
                        MERGE (n)-[:PUBLISHED_IN_MONTH]->(m)
                        MERGE (y)-[:HAS_MONTH]->(m)
                    """, {"article_id": article_id, "year": year, "month": month})
            
            return {
                "success": True,
                "article_id": result[0]["article_id"] if result else article_id,
                "node_id": result[0]["node_id"] if result else None,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to create news article: {e}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get news article statistics."""
        try:
            logger.info("Getting news statistics")
            
            total = self.execute_cypher("""
                MATCH (n:NewsArticle)
                RETURN count(n) as total
            """)
            
            by_year = self.execute_cypher("""
                MATCH (n:NewsArticle)
                WHERE n.year IS NOT NULL
                RETURN n.year as year, count(n) as count
                ORDER BY year DESC
            """)
            
            by_category = self.execute_cypher("""
                MATCH (n:NewsArticle)
                WHERE n.category IS NOT NULL
                RETURN n.category as category, count(n) as count
                ORDER BY count DESC
            """)
            
            by_month = self.execute_cypher("""
                MATCH (n:NewsArticle)
                WHERE n.month IS NOT NULL
                RETURN n.month as month, count(n) as count
                ORDER BY month
            """)
            
            return {
                "total_articles": total[0]["total"] if total else 0,
                "by_year": by_year,
                "by_category": by_category,
                "by_month": by_month
            }
            
        except Exception as e:
            logger.error(f"Failed to get news statistics: {e}")
            raise
    
    def get_latest(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest news articles."""
        try:
            logger.info(f"Getting latest {limit} news articles")
            
            cypher = """
            MATCH (n:NewsArticle)
            WHERE n.date IS NOT NULL
            RETURN n {
                .*,
                id: id(n),
                date: toString(n.date)
            } as article
            ORDER BY n.date DESC
            LIMIT $limit
            """
            
            result = self.execute_cypher(cypher, {"limit": limit})
            articles = [r["article"] for r in result]
            
            return articles
            
        except Exception as e:
            logger.error(f"Failed to get latest news: {e}")
            raise
    
    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search news articles by title or content."""
        try:
            logger.info(f"Searching news with query: {query}")
            
            cypher = """
            MATCH (n:NewsArticle)
            WHERE toLower(n.title) CONTAINS toLower($query)
               OR toLower(n.content) CONTAINS toLower($query)
            RETURN n {
                .*,
                id: id(n),
                date: toString(n.date)
            } as article
            ORDER BY n.date DESC
            LIMIT $limit
            """
            
            result = self.execute_cypher(cypher, {"query": query, "limit": limit})
            articles = [r["article"] for r in result]
            
            return articles
            
        except Exception as e:
            logger.error(f"Failed to search news: {e}")
            raise
