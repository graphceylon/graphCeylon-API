"""
Test suite for Hybrid Reasoning System with GNN Embeddings.

Run with: python -m pytest test_hybrid_system.py -v
"""

import pytest
from datetime import datetime
from neo4j import GraphDatabase

from services.gnn_embeddings import GNNEmbeddingService
from services.hybrid_reasoning import HybridReasoningEngine
from models.temporal import TemporalMetadata, ProvenanceMetadata


@pytest.fixture
def neo4j_driver():
    """Create Neo4j driver for testing."""
    driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "password")  # Update with your credentials
    )
    yield driver
    driver.close()


@pytest.fixture
def gnn_service(neo4j_driver):
    """Initialize GNN service."""
    return GNNEmbeddingService(neo4j_driver, embedding_dim=32)


@pytest.fixture
def hybrid_reasoner(neo4j_driver, gnn_service):
    """Initialize hybrid reasoning engine."""
    return HybridReasoningEngine(neo4j_driver, gnn_service)


class TestGNNEmbeddings:
    """Test GNN embedding functionality."""
    
    def test_extract_graph(self, gnn_service):
        """Test graph extraction from Neo4j."""
        data, node_map = gnn_service.extract_graph_from_neo4j(
            node_labels=["District", "Province"],
            limit=100
        )
        
        assert data.num_nodes > 0, "No nodes extracted"
        assert data.edge_index.size(1) > 0, "No edges extracted"
        assert len(node_map) == data.num_nodes, "Node map mismatch"
        
        print(f"✓ Extracted {data.num_nodes} nodes and {data.edge_index.size(1)} edges")
    
    def test_train_embeddings(self, gnn_service):
        """Test GNN training."""
        data, node_map = gnn_service.extract_graph_from_neo4j(limit=100)
        
        stats = gnn_service.train_embeddings(
            data,
            epochs=10,  # Quick test
            lr=0.001
        )
        
        assert stats["epochs"] == 10
        assert stats["final_loss"] > 0
        assert gnn_service.node_embeddings is not None
        
        print(f"✓ Training completed: loss={stats['final_loss']:.4f}")
    
    def test_link_prediction(self, gnn_service):
        """Test link prediction."""
        # First train
        data, node_map = gnn_service.extract_graph_from_neo4j(limit=100)
        gnn_service.train_embeddings(data, epochs=5)
        
        # Get two node IDs
        node_ids = list(node_map.keys())
        if len(node_ids) >= 2:
            pred = gnn_service.predict_link(node_ids[0], node_ids[1])
            
            assert "exists" in pred
            assert "confidence" in pred
            assert 0 <= pred["confidence"] <= 1
            
            print(f"✓ Link prediction: {pred}")
    
    def test_similarity_search(self, gnn_service):
        """Test entity similarity search."""
        data, node_map = gnn_service.extract_graph_from_neo4j(limit=100)
        gnn_service.train_embeddings(data, epochs=5)
        
        node_ids = list(node_map.keys())
        if node_ids:
            similar = gnn_service.find_similar_entities(node_ids[0], top_k=3)
            
            assert isinstance(similar, list)
            assert len(similar) <= 3
            
            for entity in similar:
                assert "similarity" in entity
                assert 0 <= entity["similarity"] <= 1
            
            print(f"✓ Found {len(similar)} similar entities")


class TestHybridReasoning:
    """Test hybrid reasoning functionality."""
    
    def test_symbolic_reasoning(self, hybrid_reasoner):
        """Test symbolic path finding."""
        result = hybrid_reasoner._symbolic_path_reasoning(
            start="Western Province",
            end="Colombo",
            constraints={}
        )
        
        assert "found" in result
        assert "confidence" in result
        
        if result["found"]:
            assert "path" in result
            assert len(result["path"]) > 0
            print(f"✓ Symbolic reasoning: found path with {len(result['path'])} nodes")
        else:
            print(f"✓ Symbolic reasoning: no path found (expected for some queries)")
    
    def test_itinerary_reasoning(self, hybrid_reasoner):
        """Test full itinerary reasoning."""
        result = hybrid_reasoner.reason_itinerary(
            start_location="Colombo",
            end_location="Kandy",
            constraints={
                "interests": ["history"],
                "min_rating": 4.0
            },
            query_date=datetime(2026, 2, 15)
        )
        
        assert "itinerary" in result
        assert "overall_confidence" in result
        assert "explanation" in result
        assert 0 <= result["overall_confidence"] <= 1
        
        print(f"✓ Itinerary reasoning: confidence={result['overall_confidence']:.2f}")
        print(f"  Steps in reasoning chain: {len(result['explanation']['chain'])}")
    
    def test_relationship_prediction(self, hybrid_reasoner):
        """Test relationship prediction."""
        result = hybrid_reasoner.predict_missing_relationship(
            entity1_name="Colombo",
            entity2_name="Kandy"
        )
        
        assert "exists" in result
        assert "confidence" in result
        assert "explanation" in result
        
        print(f"✓ Relationship prediction: exists={result['exists']}, conf={result['confidence']:.2f}")


class TestTemporalProvenance:
    """Test temporal and provenance models."""
    
    def test_temporal_metadata(self):
        """Test temporal metadata creation."""
        temporal = TemporalMetadata(
            valid_from=datetime(2026, 1, 1),
            valid_to=None,
            seasonal_availability=["Nov-Mar"],
            closure_dates=["2026-01-15"]
        )
        
        assert temporal.valid_from.year == 2026
        assert temporal.valid_to is None
        assert len(temporal.seasonal_availability) == 1
        
        print("✓ Temporal metadata validated")
    
    def test_provenance_metadata(self):
        """Test provenance metadata creation."""
        provenance = ProvenanceMetadata(
            source="Test Source",
            source_url="https://example.com",
            confidence=0.95,
            verified=True
        )
        
        assert provenance.source == "Test Source"
        assert provenance.confidence == 0.95
        assert provenance.verified is True
        
        print("✓ Provenance metadata validated")


class TestIntegration:
    """Integration tests for full system."""
    
    @pytest.mark.slow
    def test_full_pipeline(self, neo4j_driver):
        """Test complete pipeline: extract -> train -> reason."""
        print("\n=== Running Full Pipeline Test ===")
        
        # 1. Initialize services
        gnn_service = GNNEmbeddingService(neo4j_driver, embedding_dim=32)
        hybrid_reasoner = HybridReasoningEngine(neo4j_driver, gnn_service)
        
        # 2. Extract and train
        print("Step 1: Extracting graph...")
        data, node_map = gnn_service.extract_graph_from_neo4j(limit=500)
        print(f"  → {data.num_nodes} nodes, {data.edge_index.size(1)} edges")
        
        print("Step 2: Training GNN...")
        stats = gnn_service.train_embeddings(data, epochs=20)
        print(f"  → Loss: {stats['final_loss']:.4f}")
        
        # 3. Test reasoning
        print("Step 3: Testing reasoning...")
        result = hybrid_reasoner.reason_itinerary(
            start_location="Colombo",
            end_location="Sigiriya",
            constraints={"interests": ["history", "culture"]},
            query_date=datetime(2026, 3, 1)
        )
        print(f"  → Confidence: {result['overall_confidence']:.2f}")
        print(f"  → Attractions found: {len(result.get('itinerary', []))}")
        
        # 4. Test link prediction
        print("Step 4: Testing link prediction...")
        pred = hybrid_reasoner.predict_missing_relationship(
            entity1_name="Sigiriya",
            entity2_name="Dambulla"
        )
        print(f"  → Relationship exists: {pred['exists']}, confidence: {pred['confidence']:.2f}")
        
        print("\n✓ Full pipeline test completed successfully!")


# Performance benchmarks
class TestPerformance:
    """Performance and benchmarking tests."""
    
    def test_query_performance(self, hybrid_reasoner, benchmark):
        """Benchmark reasoning query performance."""
        def reasoning_query():
            return hybrid_reasoner.reason_itinerary(
                start_location="Colombo",
                end_location="Kandy",
                constraints={}
            )
        
        result = benchmark(reasoning_query)
        assert result is not None
        print(f"✓ Query performance benchmark completed")
    
    def test_embedding_generation_speed(self, gnn_service, benchmark):
        """Benchmark embedding generation speed."""
        data, _ = gnn_service.extract_graph_from_neo4j(limit=100)
        
        def train():
            return gnn_service.train_embeddings(data, epochs=5)
        
        result = benchmark(train)
        print(f"✓ Embedding generation benchmark completed")


if __name__ == "__main__":
    """Run tests directly."""
    pytest.main([__file__, "-v", "--tb=short"])
