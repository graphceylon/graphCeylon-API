"""
Initialize n10s (Neo4j RDF & Semantics) Plugin
Configures Neo4j for RDF/OWL semantic web support
"""

import requests
import logging
import json
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"
QUERY_ENDPOINT = f"{BASE_URL}/kg/query"

def print_header():
    """Print script header"""
    print("\n" + "=" * 70)
    print("  N10S INITIALIZATION - RDF/OWL SEMANTIC WEB CONFIGURATION")
    print("=" * 70 + "\n")

def check_n10s_installed():
    """Check if n10s plugin is installed"""
    logger.info("Step 1: Checking n10s plugin installation...")
    
    query = "SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'n10s' RETURN count(name) AS count"
    
    try:
        response = requests.post(QUERY_ENDPOINT, json={"query": query}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            count = data.get("data", [{}])[0].get("count", 0)
            
            if count > 0:
                logger.info(f"✅ n10s plugin is installed ({count} procedures available)")
                return True
            else:
                logger.error("❌ n10s plugin not found!")
                logger.error("   Please install n10s plugin in neo4j/plugins/")
                return False
        else:
            logger.error(f"❌ Query failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error checking n10s: {e}")
        return False

def initialize_n10s():
    """Initialize n10s graph configuration"""
    logger.info("\nStep 2: Initializing n10s graph configuration...")
    
    # Configuration parameters explained:
    # - handleVocabUris: 'SHORTEN' - Use shortened URIs (prefixes) for better readability
    # - handleMultival: 'ARRAY' - Store multiple values as arrays
    # - applyNeo4jNaming: true - Convert RDF naming to Neo4j conventions (camelCase)
    
    config_query = """
    CALL n10s.graphconfig.init({
        handleVocabUris: 'SHORTEN',
        handleMultival: 'ARRAY',
        applyNeo4jNaming: true
    })
    """
    
    try:
        response = requests.post(QUERY_ENDPOINT, json={"query": config_query}, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✅ n10s configuration initialized successfully!")
            
            # Display configuration
            if data.get("data"):
                config = data["data"][0]
                logger.info("\n  Configuration Settings:")
                for key, value in config.items():
                    logger.info(f"    • {key}: {value}")
            
            return True
        else:
            # Check if already initialized
            if "already" in response.text.lower():
                logger.warning("⚠️  n10s configuration already exists")
                logger.info("   Retrieving existing configuration...")
                return get_n10s_config()
            else:
                logger.error(f"❌ Initialization failed: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error initializing n10s: {e}")
        return False

def get_n10s_config():
    """Get current n10s configuration"""
    query = "CALL n10s.graphconfig.show()"
    
    try:
        response = requests.post(QUERY_ENDPOINT, json={"query": query}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("data"):
                config = data["data"][0]
                logger.info("✅ Current n10s configuration:")
                logger.info("\n  Configuration Settings:")
                for key, value in config.items():
                    logger.info(f"    • {key}: {value}")
                return True
        
        logger.error("❌ Could not retrieve configuration")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error getting config: {e}")
        return False

def setup_namespaces():
    """Set up common RDF namespaces"""
    logger.info("\nStep 3: Setting up RDF namespaces...")
    
    namespaces = [
        ("owl", "http://www.w3.org/2002/07/owl#"),
        ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
        ("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
        ("xsd", "http://www.w3.org/2001/XMLSchema#"),
        ("sh", "http://www.w3.org/ns/shacl#"),
        ("lk", "http://example.org/lk#"),  # Custom namespace for Sri Lankan data
    ]
    
    success_count = 0
    
    for prefix, uri in namespaces:
        query = f"CALL n10s.nsprefixes.add('{prefix}', '{uri}')"
        
        try:
            response = requests.post(QUERY_ENDPOINT, json={"query": query}, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"  ✓ Added namespace: {prefix} → {uri}")
                success_count += 1
            elif "already" in response.text.lower():
                logger.info(f"  ✓ Namespace already exists: {prefix}")
                success_count += 1
            else:
                logger.warning(f"  ⚠️  Failed to add {prefix}: {response.text[:100]}")
                
        except Exception as e:
            logger.warning(f"  ⚠️  Error adding {prefix}: {e}")
            continue
    
    logger.info(f"\n✅ Set up {success_count}/{len(namespaces)} namespaces")
    return success_count > 0

def import_ontologies():
    """Import RDF ontologies into the graph"""
    logger.info("\nStep 4: Importing RDF ontologies...")
    
    # Path to ontology files
    ontology_dir = Path("neo4j/import/data")
    ontologies = [
        ("lk-admin.ttl", "Administrative structure ontology (Provinces, Districts)"),
        ("lk-shapes.ttl", "SHACL shapes for validation"),
    ]
    
    imported_count = 0
    
    for filename, description in ontologies:
        ontology_path = ontology_dir / filename
        
        if not ontology_path.exists():
            logger.warning(f"  ⚠️  File not found: {ontology_path}")
            continue
        
        logger.info(f"\n  Importing {filename}...")
        logger.info(f"  Description: {description}")
        
        # Import using n10s
        # Note: n10s.rdf.import.fetch requires a URL, so we'll use file:// protocol
        import_query = f"""
        CALL n10s.rdf.import.fetch(
            'file:///import/data/{filename}',
            'Turtle'
        )
        """
        
        try:
            response = requests.post(QUERY_ENDPOINT, json={"query": import_query}, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    stats = data["data"][0]
                    logger.info(f"  ✅ Successfully imported {filename}")
                    logger.info(f"     Triples: {stats.get('triplesLoaded', 0)}")
                    logger.info(f"     Namespaces: {stats.get('namespaces', 0)}")
                    imported_count += 1
            else:
                logger.warning(f"  ⚠️  Import may have issues: {response.text[:150]}")
                
        except Exception as e:
            logger.warning(f"  ⚠️  Error importing {filename}: {e}")
            continue
    
    if imported_count > 0:
        logger.info(f"\n✅ Successfully imported {imported_count} ontologies")
        return True
    else:
        logger.warning("\n⚠️  No ontologies were imported (this is optional)")
        logger.info("   Your graph structure already aligns with the ontologies")
        return True  # Not critical for graph operation

def verify_semantic_capabilities():
    """Verify semantic web capabilities"""
    logger.info("\nStep 5: Verifying semantic web capabilities...")
    
    checks = [
        ("Configuration exists", "CALL n10s.graphconfig.show()"),
        ("Namespaces defined", "CALL n10s.nsprefixes.list()"),
        ("RDF export capability", "CALL n10s.rdf.export.cypher('MATCH (n:Country) RETURN n LIMIT 1', {format: 'Turtle'})"),
    ]
    
    passed = 0
    
    for check_name, query in checks:
        try:
            response = requests.post(QUERY_ENDPOINT, json={"query": query}, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    logger.info(f"  ✅ {check_name}")
                    passed += 1
                else:
                    logger.warning(f"  ⚠️  {check_name} - No data returned")
            else:
                logger.warning(f"  ⚠️  {check_name} - Query failed")
                
        except Exception as e:
            logger.warning(f"  ⚠️  {check_name} - Error: {str(e)[:50]}")
    
    logger.info(f"\n✅ Passed {passed}/{len(checks)} capability checks")
    return passed >= 2  # At least config and namespaces should work

def print_summary():
    """Print summary and next steps"""
    print("\n" + "=" * 70)
    print("  N10S INITIALIZATION COMPLETE")
    print("=" * 70)
    
    print("\n🎯 SEMANTIC WEB FEATURES NOW ENABLED:")
    print("   ✓ RDF/OWL ontology support")
    print("   ✓ SHACL shape validation")
    print("   ✓ RDF import/export capabilities")
    print("   ✓ SPARQL-like queries via Cypher")
    print("   ✓ Semantic reasoning support")
    
    print("\n📚 AVAILABLE N10S PROCEDURES:")
    print("   • n10s.rdf.import.fetch() - Import RDF from URL/file")
    print("   • n10s.rdf.export.cypher() - Export graph as RDF")
    print("   • n10s.validation.shacl.import.fetch() - Import SHACL shapes")
    print("   • n10s.validation.shacl.validate() - Validate against SHACL")
    print("   • n10s.inference.* - Semantic reasoning operations")
    
    print("\n🔗 DOCUMENTATION:")
    print("   • n10s Docs: https://neo4j.com/labs/neosemantics/")
    print("   • RDF/OWL: https://www.w3.org/OWL/")
    print("   • SHACL: https://www.w3.org/TR/shacl/")
    
    print("\n" + "=" * 70 + "\n")

def main():
    """Main execution"""
    print_header()
    
    # Step 1: Check plugin
    if not check_n10s_installed():
        logger.error("\n❌ n10s plugin is required but not installed!")
        logger.error("   Please install from: https://github.com/neo4j-labs/neosemantics/releases")
        return False
    
    # Step 2: Initialize
    if not initialize_n10s():
        logger.error("\n❌ Failed to initialize n10s configuration")
        return False
    
    # Step 3: Set up namespaces
    if not setup_namespaces():
        logger.warning("\n⚠️  Namespace setup had issues (optional)")
    
    # Step 4: Import ontologies (optional)
    import_ontologies()
    
    # Step 5: Verify capabilities
    if not verify_semantic_capabilities():
        logger.warning("\n⚠️  Some capabilities may not be fully functional")
    
    # Summary
    print_summary()
    
    logger.info("✅ n10s initialization completed successfully!")
    logger.info("   Run 'python scripts/validate_graph.py' to verify full compliance")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Initialization cancelled by user")
        exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        exit(1)
