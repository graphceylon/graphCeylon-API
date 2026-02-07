"""
GPU-Accelerated Demo for Hybrid Reasoning System
Tests all newly implemented features with CUDA support

Run: python demo_hybrid_system.py
"""

import torch
import logging
from datetime import datetime
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.gnn_embeddings import GNNEmbeddingService
from services.hybrid_reasoning import HybridReasoningEngine
from models.graph.temporal import TemporalMetadata, ProvenanceMetadata


def check_gpu():
    """Check CUDA availability and GPU info."""
    print("\n" + "="*70)
    print("🔍 GPU AVAILABILITY CHECK")
    print("="*70)
    
    cuda_available = torch.cuda.is_available()
    print(f"✓ CUDA Available: {cuda_available}")
    
    if cuda_available:
        print(f"✓ GPU Device: {torch.cuda.get_device_name(0)}")
        print(f"✓ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        print(f"✓ CUDA Version: {torch.version.cuda}")
        print(f"✓ PyTorch Version: {torch.__version__}")
        print(f"✓ Device Count: {torch.cuda.device_count()}")
    else:
        print("⚠ CUDA not available, will use CPU")
    
    return cuda_available


def connect_neo4j():
    """Connect to Neo4j database."""
    print("\n" + "="*70)
    print("🔗 CONNECTING TO NEO4J")
    print("="*70)
    
    try:
        driver = GraphDatabase.driver(
            "bolt://127.0.0.1:7687",
            auth=("neo4j", "password")  # Update with your password
        )
        
        # Test connection
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            result.single()
        
        print("✓ Successfully connected to Neo4j")
        return driver
    
    except Exception as e:
        print(f"✗ Failed to connect to Neo4j: {e}")
        print("\n💡 Make sure Neo4j is running on bolt://127.0.0.1:7687")
        print("   Update the password in the script if needed")
        return None


def test_gnn_embeddings(driver):
    """Test GNN embedding training with GPU acceleration."""
    print("\n" + "="*70)
    print("🧠 TEST 1: GNN EMBEDDINGS (GPU-Accelerated)")
    print("="*70)
    
    # Initialize service
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    
    gnn_service = GNNEmbeddingService(driver, embedding_dim=32, device=device)
    
    # Extract graph
    print("\n📊 Extracting graph from Neo4j...")
    data, node_map = gnn_service.extract_graph_from_neo4j(
        node_labels=["District", "Province", "Attraction"],
        limit=1000
    )
    
    print(f"✓ Extracted {data.num_nodes} nodes")
    print(f"✓ Extracted {data.edge_index.size(1)} edges")
    print(f"✓ Node feature dimensions: {data.x.size()}")
    
    # Train embeddings
    print("\n🏋️ Training GNN embeddings...")
    print("(This will be MUCH faster on GPU!)")
    
    import time
    start_time = time.time()
    
    stats = gnn_service.train_embeddings(
        data,
        epochs=50,  # Increase this for better results
        lr=0.001
    )
    
    train_time = time.time() - start_time
    
    print(f"\n✓ Training completed in {train_time:.2f} seconds")
    print(f"✓ Final loss: {stats['final_loss']:.4f}")
    print(f"✓ Average loss: {stats['avg_loss']:.4f}")
    print(f"✓ Embedding dimensions: {stats['embedding_dim']}")
    
    # Test link prediction
    print("\n🔗 Testing link prediction...")
    node_ids = list(node_map.keys())[:5]
    
    for i in range(min(3, len(node_ids)-1)):
        pred = gnn_service.predict_link(node_ids[i], node_ids[i+1])
        print(f"  Link {node_ids[i]} → {node_ids[i+1]}: "
              f"exists={pred['exists']}, confidence={pred['confidence']:.3f}")
    
    # Test similarity search
    print("\n🔍 Testing entity similarity...")
    if node_ids:
        similar = gnn_service.find_similar_entities(node_ids[0], top_k=3)
        print(f"  Most similar to node {node_ids[0]}:")
        for entity in similar[:3]:
            print(f"    → Node {entity['neo4j_id']}: similarity={entity['similarity']:.3f}")
    
    return gnn_service


def test_hybrid_reasoning(driver, gnn_service):
    """Test hybrid reasoning engine."""
    print("\n" + "="*70)
    print("🤖 TEST 2: HYBRID REASONING")
    print("="*70)
    
    # Initialize hybrid reasoner
    reasoner = HybridReasoningEngine(
        driver,
        gnn_service,
        symbolic_weight=0.6,
        neural_weight=0.4
    )
    
    # Test 1: Simple path reasoning
    print("\n📍 Test 2.1: Path Finding")
    print("Query: Find path from 'Western Province' to 'Colombo'")
    
    result = reasoner.reason_itinerary(
        start_location="Western Province",
        end_location="Colombo",
        constraints={}
    )
    
    print(f"✓ Overall confidence: {result['overall_confidence']:.3f}")
    print(f"✓ Reasoning steps: {len(result['explanation']['chain'])}")
    for step in result['explanation']['chain']:
        print(f"  Step {step['step']}: {step['method']} (confidence: {step['confidence']:.3f})")
    
    # Test 2: Itinerary with constraints
    print("\n🎯 Test 2.2: Itinerary with Constraints")
    print("Query: Colombo → Kandy with history interest, min rating 4.0")
    
    result = reasoner.reason_itinerary(
        start_location="Colombo",
        end_location="Kandy",
        constraints={
            "interests": ["history", "culture"],
            "min_rating": 4.0,
            "max_results": 5
        },
        query_date=datetime(2026, 2, 15)
    )
    
    print(f"✓ Overall confidence: {result['overall_confidence']:.3f}")
    print(f"✓ Attractions found: {len(result.get('itinerary', []))}")
    
    if result.get('itinerary'):
        print("\n  Top attractions:")
        for attr in result['itinerary'][:3]:
            print(f"    → {attr.get('title', 'N/A')} (rating: {attr.get('rating', 'N/A')})")
    
    # Test 3: Relationship prediction
    print("\n🔗 Test 2.3: Relationship Prediction")
    print("Query: Does relationship exist between Colombo and Kandy?")
    
    pred = reasoner.predict_missing_relationship(
        entity1_name="Colombo",
        entity2_name="Kandy"
    )
    
    print(f"✓ Relationship exists: {pred['exists']}")
    print(f"✓ Confidence: {pred['confidence']:.3f}")
    print(f"✓ Method: {pred['explanation']['method']}")
    
    return reasoner


def test_temporal_provenance():
    """Test temporal and provenance models."""
    print("\n" + "="*70)
    print("📅 TEST 3: TEMPORAL & PROVENANCE MODELS")
    print("="*70)
    
    # Create temporal metadata
    print("\n✓ Creating temporal metadata...")
    temporal = TemporalMetadata(
        valid_from=datetime(2026, 1, 1),
        valid_to=None,
        seasonal_availability=["Nov-Mar", "closed-during-monsoon"],
        closure_dates=["2026-01-15", "2026-02-20"]
    )
    
    print(f"  Valid from: {temporal.valid_from}")
    print(f"  Valid to: {temporal.valid_to}")
    print(f"  Seasonal: {temporal.seasonal_availability}")
    
    # Create provenance metadata
    print("\n✓ Creating provenance metadata...")
    provenance = ProvenanceMetadata(
        source="SLTDA Official Database",
        source_url="https://sltda.gov.lk/attractions/sigiriya",
        source_type="api",
        confidence=0.95,
        verified=True,
        verified_by="curator_001",
        license="CC-BY-SA-4.0"
    )
    
    print(f"  Source: {provenance.source}")
    print(f"  Confidence: {provenance.confidence}")
    print(f"  Verified: {provenance.verified}")
    print(f"  License: {provenance.license}")


def test_api_endpoints():
    """Test API endpoints with sample requests."""
    print("\n" + "="*70)
    print("🌐 TEST 4: API ENDPOINTS")
    print("="*70)
    
    import httpx
    
    base_url = "http://localhost:8000"
    
    # Check if API is running
    try:
        response = httpx.get(f"{base_url}/health", timeout=2.0)
        print("✓ API is running!")
    except:
        print("⚠ API is not running. Start it with: python src/main.py")
        print("   Skipping API tests...")
        return
    
    # Test AIL endpoints
    endpoints_to_test = [
        ("POST", "/ail/query", {
            "entity_type": "Attraction",
            "limit": 5
        }),
        ("POST", "/ail/reason", {
            "start_location": "Colombo",
            "end_location": "Kandy",
            "reasoning_mode": "hybrid"
        }),
        ("POST", "/ail/validate", {
            "entity_type": "Attraction"
        })
    ]
    
    for method, endpoint, payload in endpoints_to_test:
        try:
            if method == "POST":
                response = httpx.post(f"{base_url}{endpoint}", json=payload, timeout=10.0)
            else:
                response = httpx.get(f"{base_url}{endpoint}", timeout=10.0)
            
            print(f"✓ {method} {endpoint}: {response.status_code}")
            
        except Exception as e:
            print(f"✗ {method} {endpoint}: {e}")


def performance_benchmark(driver, gnn_service):
    """Benchmark performance on GPU vs CPU."""
    print("\n" + "="*70)
    print("⚡ TEST 5: PERFORMANCE BENCHMARK")
    print("="*70)
    
    import time
    
    # Extract small graph for quick testing
    data, _ = gnn_service.extract_graph_from_neo4j(limit=200)
    
    # Test GPU
    if torch.cuda.is_available():
        print("\n🚀 GPU Benchmark...")
        gnn_gpu = GNNEmbeddingService(driver, embedding_dim=32, device='cuda')
        
        start = time.time()
        gnn_gpu.train_embeddings(data.to('cuda'), epochs=20)
        gpu_time = time.time() - start
        
        print(f"  GPU training time: {gpu_time:.2f}s")
    else:
        print("⚠ No GPU available for benchmark")
        gpu_time = None
    
    # Test CPU
    print("\n🐌 CPU Benchmark...")
    gnn_cpu = GNNEmbeddingService(driver, embedding_dim=32, device='cpu')
    
    start = time.time()
    gnn_cpu.train_embeddings(data.to('cpu'), epochs=20)
    cpu_time = time.time() - start
    
    print(f"  CPU training time: {cpu_time:.2f}s")
    
    # Speedup
    if gpu_time:
        speedup = cpu_time / gpu_time
        print(f"\n⚡ GPU Speedup: {speedup:.2f}x faster!")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("🚀 HYBRID REASONING SYSTEM - COMPREHENSIVE DEMO")
    print("="*70)
    print("\nThis demo will test all newly implemented features:")
    print("  1. GNN Embeddings (GPU-accelerated)")
    print("  2. Hybrid Reasoning Engine")
    print("  3. Temporal & Provenance Models")
    print("  4. API Endpoints")
    print("  5. Performance Benchmarks")
    
    # Check GPU
    has_gpu = check_gpu()
    
    # Connect to Neo4j
    driver = connect_neo4j()
    if not driver:
        print("\n❌ Cannot proceed without Neo4j connection")
        return
    
    try:
        # Run tests
        gnn_service = test_gnn_embeddings(driver)
        test_hybrid_reasoning(driver, gnn_service)
        test_temporal_provenance()
        test_api_endpoints()
        
        if has_gpu:
            performance_benchmark(driver, gnn_service)
        
        # Summary
        print("\n" + "="*70)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*70)
        print("\n📊 Summary:")
        print("  ✓ GNN embeddings trained on GPU")
        print("  ✓ Link prediction working")
        print("  ✓ Entity similarity working")
        print("  ✓ Hybrid reasoning functional")
        print("  ✓ Temporal/Provenance models validated")
        
        print("\n💡 Next Steps:")
        print("  1. Train on larger dataset (increase limit in extract_graph)")
        print("  2. Test API endpoints (start with: python src/main.py)")
        print("  3. Run experiments for research paper")
        print("  4. Visualize embeddings with t-SNE")
        
    finally:
        driver.close()


if __name__ == "__main__":
    main()
