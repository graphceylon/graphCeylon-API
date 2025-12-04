"""Tourism News API endpoints."""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List

from ..database.manager import DatabaseManager
from ..models.schemas import (
    WriteResponse,
    NewsQueryRequest,
    NewsResponse,
    CreateNewsRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["Tourism News"])


def get_db_manager():
    """Dependency to get database manager - will be overridden by main app."""
    raise HTTPException(status_code=503, detail="Database manager not initialized")


@router.get("", response_model=NewsResponse)
def get_all_news(
    limit: int = 20,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all news articles with optional limit."""
    try:
        logger.info(f"Getting all news with limit={limit}")
        
        articles = db.query_news({"limit": limit})
        
        return NewsResponse(
            articles=articles,
            count=len(articles),
            query_info={"limit": limit}
        )
    except Exception as e:
        logger.error(f"Failed to get news: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get news: {str(e)}")


@router.post("/query", response_model=NewsResponse)
def query_news(
    request: NewsQueryRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Query news articles with various filters.
    
    Filters:
    - title: Search by article title (case-insensitive)
    - category: Filter by category
    - date_from: Filter articles from this date (YYYY-MM-DD)
    - date_to: Filter articles to this date (YYYY-MM-DD)
    - year: Filter by year
    - month: Filter by month (1-12)
    - limit: Maximum number of results
    """
    try:
        filters = request.dict(exclude_none=True)
        logger.info(f"Querying news with filters: {filters}")
        
        articles = db.query_news(filters)
        
        return NewsResponse(
            articles=articles,
            count=len(articles),
            query_info={
                "filters_applied": {k: v for k, v in filters.items() if k != "limit"},
                "limit": filters.get("limit", 20)
            }
        )
    except Exception as e:
        logger.error(f"Failed to query news: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query news: {str(e)}")


@router.get("/categories", response_model=Dict[str, Any])
def get_news_categories(db: DatabaseManager = Depends(get_db_manager)):
    """Get all news categories with counts."""
    try:
        logger.info("Getting news categories")
        
        result = db.execute_cypher("""
            MATCH (n:NewsArticle)
            WHERE n.category IS NOT NULL
            WITH n.category as category, count(n) as count
            ORDER BY count DESC
            RETURN category, count
        """)
        
        return {
            "categories": result,
            "total_categories": len(result)
        }
    except Exception as e:
        logger.error(f"Failed to get categories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


@router.get("/year/{year}", response_model=NewsResponse)
def get_news_by_year(
    year: int,
    limit: int = 50,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all news articles for a specific year."""
    try:
        logger.info(f"Getting news for year: {year}")
        
        articles = db.query_news({"year": year, "limit": limit})
        
        return NewsResponse(
            articles=articles,
            count=len(articles),
            query_info={"year": year, "limit": limit}
        )
    except Exception as e:
        logger.error(f"Failed to get news by year: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get news: {str(e)}")


@router.get("/month/{year}/{month}", response_model=NewsResponse)
def get_news_by_month(
    year: int,
    month: int,
    limit: int = 50,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all news articles for a specific month."""
    try:
        if month < 1 or month > 12:
            raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
        
        logger.info(f"Getting news for {year}-{month:02d}")
        
        articles = db.query_news({"year": year, "month": month, "limit": limit})
        
        return NewsResponse(
            articles=articles,
            count=len(articles),
            query_info={"year": year, "month": month, "limit": limit}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get news by month: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get news: {str(e)}")


@router.get("/recent", response_model=NewsResponse)
def get_recent_news(
    limit: int = 10,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get recent news articles sorted by date."""
    try:
        logger.info(f"Getting {limit} most recent news articles")
        
        result = db.execute_cypher("""
            MATCH (n:NewsArticle)
            WHERE n.date IS NOT NULL
            RETURN n {
                .*,
                id: id(n)
            } as article
            ORDER BY n.date DESC
            LIMIT $limit
        """, {"limit": limit})
        
        articles = [r["article"] for r in result]
        
        return NewsResponse(
            articles=articles,
            count=len(articles),
            query_info={"limit": limit, "sort": "recent"}
        )
    except Exception as e:
        logger.error(f"Failed to get recent news: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recent news: {str(e)}")


@router.post("/initialize", response_model=Dict[str, Any])
def initialize_news(db: DatabaseManager = Depends(get_db_manager)):
    """Initialize news schema and load news articles from JSON."""
    try:
        logger.info("Initializing tourism news...")
        
        # Load schema
        schema_result = db.load_news_schema()
        
        # Load news data
        load_result = db.load_news_from_json()
        
        return {
            "success": True,
            "schema": schema_result,
            "data": load_result,
            "message": "Tourism news initialized successfully"
        }
    except Exception as e:
        logger.error(f"Failed to initialize news: {e}")
        raise HTTPException(status_code=500, detail=f"News initialization failed: {str(e)}")


@router.post("", response_model=WriteResponse)
def create_news(
    request: CreateNewsRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new news article."""
    try:
        logger.info(f"Creating news article: {request.title}")
        
        result = db.create_news(request.dict(exclude_none=True))
        
        return WriteResponse(
            success=True,
            node_id=result.get("node_id"),
            provenance={
                "operation": "create_news",
                "source": "api",
                "timestamp": result.get("timestamp")
            }
        )
    except Exception as e:
        logger.error(f"Failed to create news: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create news: {str(e)}")


@router.get("/{article_id}", response_model=Dict[str, Any])
def get_news_by_id(
    article_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get a specific news article by ID."""
    try:
        logger.info(f"Getting news article by ID: {article_id}")
        
        result = db.execute_cypher("""
            MATCH (n:NewsArticle)
            WHERE n.id = $id OR id(n) = toInteger($id)
            OPTIONAL MATCH (n)-[:PUBLISHED_IN_YEAR]->(y:Year)
            OPTIONAL MATCH (n)-[:PUBLISHED_IN_MONTH]->(m:Month)
            RETURN n {
                .*,
                year: y.year,
                month: m.month
            } as article
        """, {"id": article_id})
        
        if not result:
            raise HTTPException(status_code=404, detail="News article not found")
        
        return result[0]["article"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get news article: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get news article: {str(e)}")


@router.get("/statistics/overview", response_model=Dict[str, Any])
def get_news_statistics(db: DatabaseManager = Depends(get_db_manager)):
    """Get news statistics."""
    try:
        logger.info("Getting news statistics")
        
        stats = db.get_news_statistics()
        
        return stats
    except Exception as e:
        logger.error(f"Failed to get news statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get("/timeline/overview", response_model=Dict[str, Any])
def get_news_timeline(db: DatabaseManager = Depends(get_db_manager)):
    """Get news articles timeline by year and month."""
    try:
        logger.info("Getting news timeline")
        
        result = db.execute_cypher("""
            MATCH (n:NewsArticle)
            WHERE n.year IS NOT NULL
            WITH n.year as year, 
                 COALESCE(n.month, 0) as month,
                 count(n) as article_count
            ORDER BY year DESC, month DESC
            RETURN year, month, article_count
        """)
        
        # Group by year
        timeline = {}
        for row in result:
            year = row["year"]
            month = row["month"]
            count = row["article_count"]
            
            if year not in timeline:
                timeline[year] = {"total": 0, "months": {}}
            
            timeline[year]["total"] += count
            if month > 0:
                timeline[year]["months"][month] = count
        
        return {
            "timeline": timeline,
            "total_years": len(timeline),
            "total_articles": sum(y["total"] for y in timeline.values())
        }
    except Exception as e:
        logger.error(f"Failed to get news timeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get timeline: {str(e)}")
