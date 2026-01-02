"""
Rebuild Knowledge Graph Script
Clears the entire Neo4j database and rebuilds it using existing API endpoints.
"""

import requests
import time
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Configuration
BASE_URL = "http://localhost:8000"
API_ENDPOINTS = {
    "health": f"{BASE_URL}/health",
    "statistics": f"{BASE_URL}/kg/statistics",
    "query": f"{BASE_URL}/kg/query",
    
    # Domain endpoints
    "initialize_domains": f"{BASE_URL}/domains/initialize",
    "domain_structure": f"{BASE_URL}/domains/structure",
    
    # Temporal/Holiday endpoints
    "initialize_temporal": f"{BASE_URL}/holidays/initialize-temporal",
    "load_holidays": f"{BASE_URL}/holidays/load",
    "holiday_stats": f"{BASE_URL}/holidays/statistics",
    
    # Attractions endpoints
    "initialize_attractions": f"{BASE_URL}/attractions/initialize",
    "attractions_stats": f"{BASE_URL}/attractions/statistics",
    
    # Projects endpoints
    "initialize_projects": f"{BASE_URL}/projects/initialize",
    "projects_stats": f"{BASE_URL}/projects/statistics/overview",
    
    # News endpoints
    "initialize_news": f"{BASE_URL}/news/initialize",
    "news_stats": f"{BASE_URL}/news/statistics/overview",
}


def check_api_health() -> bool:
    """Check if the API is running and healthy."""
    try:
        response = requests.get(API_ENDPOINTS["health"], timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✓ API is healthy - Version: {data.get('version', 'unknown')}")
            return True
        else:
            logger.error(f"✗ API health check failed with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Cannot connect to API: {e}")
        return False


def clear_database() -> bool:
    """Clear the entire Neo4j database."""
    logger.info("=" * 60)
    logger.info("STEP 1: CLEARING DATABASE")
    logger.info("=" * 60)
    
    try:
        # Delete all nodes and relationships
        clear_query = """
        CALL apoc.periodic.iterate(
            'MATCH (n) RETURN n',
            'DETACH DELETE n',
            {batchSize: 1000}
        )
        """
        
        response = requests.post(
            API_ENDPOINTS["query"],
            json={"query": clear_query},
            timeout=60
        )
        
        if response.status_code == 200:
            logger.info("✓ Successfully cleared all nodes and relationships")
            
            # Verify deletion
            verify_query = "MATCH (n) RETURN count(n) AS node_count"
            verify_response = requests.post(
                API_ENDPOINTS["query"],
                json={"query": verify_query},
                timeout=10
            )
            
            if verify_response.status_code == 200:
                data = verify_response.json()
                count = data.get("data", [{}])[0].get("node_count", 0)
                logger.info(f"  Remaining nodes: {count}")
                
                if count == 0:
                    logger.info("✓ Database is completely empty")
                    return True
                else:
                    logger.warning(f"⚠ {count} nodes still exist")
                    return False
        else:
            logger.error(f"✗ Failed to clear database: {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error clearing database: {e}")
        return False


def initialize_domains_and_geography() -> bool:
    """Initialize domain structure and load provinces/districts using Cypher script."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 2: INITIALIZING DOMAINS & GEOGRAPHY")
    logger.info("=" * 60)
    
    try:
        # Step 2a: Initialize domain structure
        logger.info("  2a. Creating domain structure...")
        response = requests.post(API_ENDPOINTS["initialize_domains"], timeout=30)
        
        if response.status_code != 200:
            logger.error(f"✗ Failed to initialize domains: {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return False
        
        data = response.json()
        domains_created = data.get("domains_created", [])
        logger.info(f"  ✓ Created {len(domains_created)} domains")
        
        # Step 2b: Load provinces and districts using Cypher script
        logger.info("  2b. Loading provinces and districts...")
        
        # Read the seed script
        import os
        from pathlib import Path
        script_path = Path(__file__).parent.parent / "neo4j" / "import" / "scripts" / "seed_provinces_districts.cypher"
        if not script_path.exists():
            logger.error(f"✗ Seed script not found: {script_path}")
            return False
        
        with open(script_path, 'r', encoding='utf-8') as f:
            cypher_content = f.read()
        
        # Split by semicolons and execute each statement separately
        statements = []
        for stmt in cypher_content.split(';'):
            # Remove comments and whitespace
            cleaned = '\n'.join(
                line for line in stmt.split('\n') 
                if line.strip() and not line.strip().startswith('//')
            )
            if cleaned.strip():
                statements.append(cleaned.strip())
        
        logger.info(f"  Executing {len(statements)} statements...")
        
        # Execute each statement separately
        success_count = 0
        skip_count = 0
        for i, stmt in enumerate(statements, 1):
            try:
                response = requests.post(
                    API_ENDPOINTS["query"],
                    json={"query": stmt},
                    timeout=30
                )
                
                if response.status_code == 200:
                    success_count += 1
                    if i <= 5 or i % 10 == 0:  # Log first 5 and every 10th
                        logger.info(f"    Statement {i}/{len(statements)}: Success")
                elif "already exists" in response.text.lower():
                    skip_count += 1
                    if i <= 5:
                        logger.info(f"    Statement {i}/{len(statements)}: Already exists (skipping)")
                else:
                    logger.warning(f"    Statement {i}/{len(statements)}: Failed - {response.text[:100]}")
                    
            except Exception as e:
                logger.warning(f"    Statement {i}/{len(statements)}: Error - {str(e)[:100]}")
                continue
        
        logger.info(f"  ✓ Executed {success_count} statements successfully, {skip_count} skipped")
        
        # Verify by getting structure
        structure_response = requests.get(API_ENDPOINTS["domain_structure"], timeout=10)
        if structure_response.status_code == 200:
            structure = structure_response.json()
            provinces = structure.get("province_count", 0)
            districts = structure.get("district_count", 0)
            logger.info(f"  ✓ Provinces: {provinces}")
            logger.info(f"  ✓ Districts: {districts}")
        
        logger.info("✓ Domain structure and geography initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error initializing domains/geography: {e}")
        return False


def initialize_temporal_structure() -> bool:
    """Initialize temporal structure (years and months)."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 3: INITIALIZING TEMPORAL STRUCTURE")
    logger.info("=" * 60)
    
    try:
        response = requests.post(API_ENDPOINTS["initialize_temporal"], timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✓ Temporal structure initialized successfully")
            
            years = data.get("years_created", 0)
            months = data.get("months_created", 0)
            logger.info(f"  Years: {years}")
            logger.info(f"  Months: {months}")
            
            return True
        else:
            logger.error(f"✗ Failed to initialize temporal structure: {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error initializing temporal structure: {e}")
        return False


def load_holidays() -> bool:
    """Load holidays into the graph."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 4: LOADING HOLIDAYS")
    logger.info("=" * 60)
    
    try:
        response = requests.post(API_ENDPOINTS["load_holidays"], timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✓ Holidays loaded successfully")
            
            holidays = data.get("holidays_loaded", 0)
            logger.info(f"  Holidays: {holidays}")
            
            # Get holiday statistics
            stats_response = requests.get(API_ENDPOINTS["holiday_stats"], timeout=10)
            if stats_response.status_code == 200:
                stats = stats_response.json()
                logger.info("  Holiday Statistics:")
                logger.info(f"    Total: {stats.get('total_holidays', 0)}")
                
                by_category = stats.get('by_category', {})
                if by_category:
                    logger.info("    By Category:")
                    # Handle both dict and list formats
                    if isinstance(by_category, dict):
                        for category, count in by_category.items():
                            logger.info(f"      - {category}: {count}")
                    elif isinstance(by_category, list):
                        for item in by_category:
                            if isinstance(item, dict) and 'category' in item:
                                logger.info(f"      - {item['category']}: {item.get('count', 0)}")
            
            return True
        else:
            logger.error(f"✗ Failed to load holidays: {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error loading holidays: {e}")
        return False


def load_attractions() -> bool:
    """Load attractions into the graph."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 5: LOADING ATTRACTIONS")
    logger.info("=" * 60)
    
    try:
        response = requests.post(API_ENDPOINTS["initialize_attractions"], timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✓ Attractions loaded successfully")
            
            # Check for data structure
            load_result = data.get("data", {})
            attractions = load_result.get("attractions_loaded", 0)
            logger.info(f"  Attractions: {attractions}")
            
            # Get attraction statistics
            stats_response = requests.get(API_ENDPOINTS["attractions_stats"], timeout=10)
            if stats_response.status_code == 200:
                stats = stats_response.json()
                logger.info("  Attraction Statistics:")
                logger.info(f"    Total: {stats.get('total_attractions', 0)}")
                
                by_type = stats.get('by_type', {})
                if by_type:
                    logger.info("    By Type:")
                    for attr_type, count in by_type.items():
                        logger.info(f"      - {attr_type}: {count}")
                
                by_district = stats.get('by_district', {})
                if by_district:
                    top_districts = sorted(by_district.items(), key=lambda x: x[1], reverse=True)[:5]
                    logger.info("    Top 5 Districts:")
                    for district, count in top_districts:
                        logger.info(f"      - {district}: {count}")
            
            return True
        else:
            logger.error(f"✗ Failed to load attractions: {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error loading attractions: {e}")
        return False


def load_projects() -> bool:
    """Load tourism projects into the graph."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 6: LOADING TOURISM PROJECTS")
    logger.info("=" * 60)
    
    try:
        response = requests.post(API_ENDPOINTS["initialize_projects"], timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✓ Projects loaded successfully")
            
            # Check for data structure
            load_result = data.get("data", {})
            stats_data = load_result.get("statistics", {})
            projects = stats_data.get("total_projects", 0)
            logger.info(f"  Projects: {projects}")
            
            # Get project statistics
            stats_response = requests.get(API_ENDPOINTS["projects_stats"], timeout=10)
            if stats_response.status_code == 200:
                stats = stats_response.json()
                logger.info("  Project Statistics:")
                logger.info(f"    Total: {stats.get('total_projects', 0)}")
                
                by_type = stats.get('by_type', [])
                if by_type:
                    logger.info("    By Type:")
                    for item in by_type:
                        if isinstance(item, dict):
                            logger.info(f"      - {item.get('type', 'Unknown')}: {item.get('count', 0)}")
                
                by_province = stats.get('by_province', [])
                if by_province:
                    logger.info("    By Province:")
                    for item in sorted(by_province, key=lambda x: x.get('count', 0), reverse=True)[:5]:
                        if isinstance(item, dict):
                            logger.info(f"      - {item.get('province', 'Unknown')}: {item.get('count', 0)}")
            
            return True
        else:
            logger.error(f"✗ Failed to load projects: {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error loading projects: {e}")
        return False


def load_news() -> bool:
    """Load tourism news into the graph."""
    logger.info("\n" + "=" * 60)
    logger.info("STEP 7: LOADING TOURISM NEWS")
    logger.info("=" * 60)
    
    try:
        response = requests.post(API_ENDPOINTS["initialize_news"], timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✓ News loaded successfully")
            
            # Check for data structure
            load_result = data.get("data", {})
            stats_data = load_result.get("statistics", {})
            news_count = stats_data.get("total_articles", 0)
            logger.info(f"  News Articles: {news_count}")
            
            # Get news statistics
            stats_response = requests.get(API_ENDPOINTS["news_stats"], timeout=10)
            if stats_response.status_code == 200:
                stats = stats_response.json()
                logger.info("  News Statistics:")
                logger.info(f"    Total: {stats.get('total_articles', 0)}")
                
                by_category = stats.get('by_category', [])
                if by_category:
                    logger.info("    By Category:")
                    for item in by_category:
                        if isinstance(item, dict):
                            logger.info(f"      - {item.get('category', 'Unknown')}: {item.get('count', 0)}")
                
                by_year = stats.get('by_year', [])
                if by_year:
                    logger.info("    By Year:")
                    for item in sorted(by_year, key=lambda x: x.get('year', 0), reverse=True)[:3]:
                        if isinstance(item, dict):
                            logger.info(f"      - {item.get('year', 'Unknown')}: {item.get('count', 0)}")
            
            return True
        else:
            logger.error(f"✗ Failed to load news: {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error loading news: {e}")
        return False


def verify_final_state() -> Dict[str, Any]:
    """Verify the final state of the graph."""
    logger.info("\n" + "=" * 60)
    logger.info("FINAL VERIFICATION")
    logger.info("=" * 60)
    
    try:
        response = requests.get(API_ENDPOINTS["statistics"], timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get("statistics", {})
            
            logger.info("✓ Final Graph Statistics:")
            logger.info(f"  Total Nodes: {stats.get('node_count', 0)}")
            logger.info(f"  Total Relationships: {stats.get('relationship_count', 0)}")
            
            # Node counts by label
            node_labels = stats.get('node_labels', {})
            if node_labels:
                logger.info("  Nodes by Label:")
                for label, count in sorted(node_labels.items(), key=lambda x: x[1], reverse=True):
                    logger.info(f"    - {label}: {count}")
            
            # Relationship counts by type
            rel_types = stats.get('relationship_types', {})
            if rel_types:
                logger.info("  Relationships by Type:")
                for rel_type, count in sorted(rel_types.items(), key=lambda x: x[1], reverse=True):
                    logger.info(f"    - {rel_type}: {count}")
            
            return stats
        else:
            logger.error(f"✗ Failed to get statistics: {response.status_code}")
            return {}
            
    except Exception as e:
        logger.error(f"✗ Error getting statistics: {e}")
        return {}


def main():
    """Main rebuild function."""
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 10 + "KNOWLEDGE GRAPH REBUILD SCRIPT" + " " * 17 + "║")
    logger.info("╚" + "=" * 58 + "╝")
    logger.info("\n")
    
    start_time = time.time()
    
    # Step 0: Check API health
    logger.info("STEP 0: CHECKING API HEALTH")
    logger.info("=" * 60)
    if not check_api_health():
        logger.error("\n❌ API is not available. Please start the server first:")
        logger.error("   cd c:\\Users\\DananjayaAbey\\Desktop\\knowledge-graph")
        logger.error("   uv run uvicorn src.knowledge_graph.api.main:app --reload")
        return
    
    # Step 1: Clear database
    if not clear_database():
        logger.error("\n❌ Failed to clear database. Aborting.")
        return
    
    time.sleep(1)  # Brief pause
    
    # Step 2: Initialize domains and geography
    if not initialize_domains_and_geography():
        logger.error("\n❌ Failed to initialize domains/geography. Aborting.")
        return
    
    time.sleep(1)
    
    # Step 3: Initialize temporal structure
    if not initialize_temporal_structure():
        logger.error("\n❌ Failed to initialize temporal structure. Aborting.")
        return
    
    time.sleep(1)
    
    # Step 4: Load holidays
    if not load_holidays():
        logger.warning("\n⚠ Failed to load holidays. Continuing...")
    
    time.sleep(1)
    
    # Step 5: Load attractions
    if not load_attractions():
        logger.warning("\n⚠ Failed to load attractions. Continuing...")
    
    time.sleep(1)
    
    # Step 6: Load projects
    if not load_projects():
        logger.warning("\n⚠ Failed to load projects. Continuing...")
    
    time.sleep(1)
    
    # Step 7: Load news
    if not load_news():
        logger.warning("\n⚠ Failed to load news. Continuing...")
    
    time.sleep(1)
    
    # Final verification
    stats = verify_final_state()
    
    # Summary
    elapsed_time = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info("REBUILD SUMMARY")
    logger.info("=" * 60)
    
    if stats:
        logger.info("✓ Graph rebuild completed successfully!")
        logger.info(f"  Total Time: {elapsed_time:.2f} seconds")
        logger.info(f"  Total Nodes: {stats.get('node_count', 0)}")
        logger.info(f"  Total Relationships: {stats.get('relationship_count', 0)}")
    else:
        logger.warning("⚠ Graph rebuild completed with warnings")
        logger.info(f"  Total Time: {elapsed_time:.2f} seconds")
    
    logger.info("\n" + "=" * 60)
    logger.info("You can now explore the graph at:")
    logger.info("  - Neo4j Browser: http://localhost:7474")
    logger.info("  - API Docs: http://localhost:8000/docs")
    logger.info("=" * 60 + "\n")


if __name__ == "__main__":
    main()
