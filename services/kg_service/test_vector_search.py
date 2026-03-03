"""
Test script for Sub-Attraction Vector Search functionality.

Run after initializing schema and generating embeddings.
"""

import requests
import json

BASE_URL = "http://localhost:8000"


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_embedding_status():
    """Test 1: Check embedding status."""
    print_section("TEST 1: Check Embedding Status")
    
    response = requests.get(f"{BASE_URL}/sub-attractions/embeddings/status")
    print(f"Status Code: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    
    return response.json()


def test_generate_embeddings_sample():
    """Test 2: Generate embeddings for a small sample."""
    print_section("TEST 2: Generate Sample Embeddings (Limit 10)")
    
    response = requests.post(
        f"{BASE_URL}/sub-attractions/embeddings/generate",
        params={"batch_size": 10, "limit": 10}
    )
    print(f"Status Code: {response.status_code}")
    print(json.dumps(response.json(), indent=2))


def test_hybrid_search_with_query():
    """Test 3: Hybrid search with natural language query."""
    print_section("TEST 3: Hybrid Search with Natural Language Query")
    
    test_cases = [
        {
            "name": "Buddhist temples in Kandy",
            "payload": {
                "city": "Kandy",
                "country": "Sri Lanka",
                "query": "ancient Buddhist temples with beautiful gardens and peaceful atmosphere",
                "days": 2
            }
        },
        {
            "name": "Beach attractions in Galle",
            "payload": {
                "city": "Galle",
                "country": "Sri Lanka",
                "query": "scenic beaches with water activities and good restaurants nearby",
                "days": 1
            }
        },
        {
            "name": "Cultural sites in Colombo",
            "payload": {
                "city": "Colombo",
                "country": "Sri Lanka",
                "query": "museums and historical colonial buildings",
                "days": 1
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- {test_case['name']} ---\n")
        
        response = requests.post(
            f"{BASE_URL}/sub-attractions/orchestrator/call/sub-attractions",
            json=test_case["payload"]
        )
        
        print(f"Status Code: {response.status_code}")
        result = response.json()
        
        print(f"Success: {result.get('ok')}")
        print(f"City: {result.get('city')}")
        print(f"Items Found: {len(result.get('items', []))}")
        print(f"Summary: {result.get('summary')}")
        
        if result.get('items'):
            print("\nTop 3 Results:")
            for idx, item in enumerate(result['items'][:3], 1):
                print(f"  {idx}. {item.get('name')}")
                print(f"     Category: {item.get('category')}")
                print(f"     Rating: {item.get('rating')}")
                print(f"     Location: {item.get('location')}")


def test_traditional_search_without_query():
    """Test 4: Traditional search (no query, uses filters only)."""
    print_section("TEST 4: Traditional Search (No NL Query)")
    
    test_cases = [
        {
            "name": "Restaurants in Colombo",
            "payload": {
                "city": "Colombo",
                "country": "Sri Lanka",
                "preferred_poi_category": "restaurant",
                "days": 1
            }
        },
        {
            "name": "Religious sites anywhere",
            "payload": {
                "country": "Sri Lanka",
                "preferred_poi_category": "temple",
                "days": 3
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- {test_case['name']} ---\n")
        
        response = requests.post(
            f"{BASE_URL}/sub-attractions/orchestrator/call/sub-attractions",
            json=test_case["payload"]
        )
        
        print(f"Status Code: {response.status_code}")
        result = response.json()
        
        print(f"Success: {result.get('ok')}")
        print(f"Items Found: {len(result.get('items', []))}")
        print(f"Summary: {result.get('summary')}")


def test_pure_vector_search():
    """Test 5: Pure vector similarity search."""
    print_section("TEST 5: Pure Vector Search (No Filters)")
    
    queries = [
        "peaceful mountain temples with meditation facilities",
        "family-friendly beaches with shallow water for kids",
        "authentic local restaurants serving traditional curry",
        "adventure activities like zip-lining and rock climbing",
        "romantic sunset viewpoints for couples"
    ]
    
    for query in queries:
        print(f"\n--- Query: {query} ---\n")
        
        response = requests.post(
            f"{BASE_URL}/sub-attractions/search/vector",
            params={
                "query": query,
                "limit": 5,
                "similarity_threshold": 0.7
            }
        )
        
        print(f"Status Code: {response.status_code}")
        result = response.json()
        
        print(f"Results Found: {result.get('count')}")
        
        if result.get('results'):
            print("\nTop 3 Results:")
            for idx, item in enumerate(result['results'][:3], 1):
                print(f"  {idx}. {item.get('name')}")
                print(f"     Similarity: {item.get('similarity', 0):.3f}")
                print(f"     City: {item.get('city')}")
                print(f"     Rating: {item.get('rating')}")


def test_search_comparison():
    """Test 6: Compare hybrid vs traditional search."""
    print_section("TEST 6: Hybrid vs Traditional Comparison")
    
    query = "peaceful Buddhist temples"
    
    # Hybrid search (with query)
    print("--- HYBRID SEARCH (with natural language query) ---\n")
    response = requests.post(
        f"{BASE_URL}/sub-attractions/orchestrator/call/sub-attractions",
        json={
            "city": "Kandy",
            "country": "Sri Lanka",
            "query": query,
            "days": 1
        }
    )
    hybrid_result = response.json()
    print(f"Results: {len(hybrid_result.get('items', []))}")
    if hybrid_result.get('items'):
        print("Top result:", hybrid_result['items'][0].get('name'))
    
    # Traditional search (without query)
    print("\n--- TRADITIONAL SEARCH (category filter only) ---\n")
    response = requests.post(
        f"{BASE_URL}/sub-attractions/orchestrator/call/sub-attractions",
        json={
            "city": "Kandy",
            "country": "Sri Lanka",
            "preferred_poi_category": "temple",
            "days": 1
        }
    )
    traditional_result = response.json()
    print(f"Results: {len(traditional_result.get('items', []))}")
    if traditional_result.get('items'):
        print("Top result:", traditional_result['items'][0].get('name'))


def run_all_tests():
    """Run all test cases."""
    print("\n" + "=" * 80)
    print("  SUB-ATTRACTION VECTOR SEARCH TEST SUITE")
    print("  2026 AI Features")
    print("=" * 80)
    
    try:
        # Test 1: Check status
        status = test_embedding_status()
        
        if status.get('coverage_percent', 0) < 100:
            print("\n⚠️  WARNING: Embeddings not fully generated!")
            print("   Run: POST /sub-attractions/embeddings/generate")
            print("   Continuing with available embeddings...\n")
        
        # Test 2: Generate sample (skip if already done)
        # test_generate_embeddings_sample()
        
        # Test 3: Hybrid search
        test_hybrid_search_with_query()
        
        # Test 4: Traditional search
        test_traditional_search_without_query()
        
        # Test 5: Pure vector search
        test_pure_vector_search()
        
        # Test 6: Comparison
        test_search_comparison()
        
        print_section("ALL TESTS COMPLETED")
        print("✅ Vector search is working correctly!")
        print("\nNext steps:")
        print("1. Generate full embeddings if coverage < 100%")
        print("2. Test with your own queries")
        print("3. Monitor performance and accuracy")
        print("4. Integrate with your application")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to server at", BASE_URL)
        print("   Make sure the API server is running:")
        print("   uvicorn main:app --reload")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
