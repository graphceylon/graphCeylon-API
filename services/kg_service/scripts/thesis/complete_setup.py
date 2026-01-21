"""
Complete Setup and Testing Suite

Runs all setup, validation, training, and testing in one go:
1. Analyze database schema
2. Install SHACL validation shapes
3. Train GNN on ALL entity types
4. Run hybrid reasoning tests
5. Validate all endpoints
6. Generate performance report
"""

import sys
from pathlib import Path
from neo4j import GraphDatabase
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path.cwd() / "src"))

from services.gnn_embeddings import GNNEmbeddingService
from services.hybrid_reasoning import HybridReasoningEngine
from setup_shacl import ComprehensiveSHACLShapes

# Configuration
NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # UPDATE THIS!

def print_header(title):
    """Print section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")

def main():
    print("=" * 70)
    print("🚀 COMPLETE SYSTEM SETUP & VALIDATION")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            session.run("RETURN 1").single()
        print("✓ Connected to Neo4j\n")
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        return
    
    # ========================================================================
    # STEP 1: Database Analysis
    # ========================================================================
    print_header("STEP 1: Database Schema Analysis")
    
    with driver.session() as session:
        # Count labels
        labels_result = session.run("CALL db.labels()")
        labels = [r["label"] for r in labels_result]
        
        # Count nodes
        total_nodes = 0
        label_counts = {}
        for label in labels:
            count_result = session.run(f"MATCH (n:`{label}`) RETURN count(n) as count")
            count = count_result.single()["count"]
            label_counts[label] = count
            total_nodes += count
        
        # Count relationships
        rel_count_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
        total_rels = rel_count_result.single()["count"]
    
    print(f"📊 Database Statistics:")
    print(f"  • Total Labels: {len(labels)}")
    print(f"  • Total Nodes: {total_nodes:,}")
    print(f"  • Total Relationships: {total_rels:,}")
    
    print(f"\n📦 Top Node Types:")
    sorted_labels = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for label, count in sorted_labels:
        print(f"  • {label:<25} {count:>6,} nodes")
    
    # ========================================================================
    # STEP 2: SHACL Validation Setup
    # ========================================================================
    print_header("STEP 2: SHACL Validation Installation")
    
    shacl = ComprehensiveSHACLShapes(driver)
    
    print("📝 Installing SHACL shapes...")
    install_results = shacl.install_all_shapes()
    
    installed = sum(1 for status in install_results.values() if status == "installed")
    print(f"✓ Installed {installed}/{len(install_results)} shapes")
    
    # Run validation
    print("\n🔍 Running initial validation...")
    validation_results = shacl.validate_all()
    
    conforming = sum(1 for r in validation_results.values() 
                    if isinstance(r, dict) and r.get("conforms", True))
    
    print(f"✓ {conforming}/{len(validation_results)} entity types conform to SHACL")
    
    # Show violations
    violations_found = False
    for label, result in validation_results.items():
        if isinstance(result, dict) and not result.get("conforms", True):
            if not violations_found:
                print("\n⚠ Violations Found:")
                violations_found = True
            violations = result.get("violations", [])
            print(f"  • {label}: {len(violations)} violation(s)")
            for v in violations[:2]:  # Show first 2
                print(f"      - {v.get('message', 'Unknown violation')}")
    
    if not violations_found:
        print("\n✅ No data quality violations found!")
    
    # ========================================================================
    # STEP 3: GNN Training on ALL Entities
    # ========================================================================
    print_header("STEP 3: GNN Training (All Entity Types)")
    
    print("🧠 Initializing GNN service...")
    gnn_service = GNNEmbeddingService(driver, embedding_dim=32, device='cpu')
    
    print("📊 Extracting complete graph...")
    # Use ALL labels for comprehensive training
    all_labels = list(labels)
    
    start_extract = time.time()
    data, node_map = gnn_service.extract_graph_from_neo4j(
        node_labels=all_labels,  # Use ALL entity types!
        limit=5000  # Increase limit
    )
    extract_time = time.time() - start_extract
    
    print(f"✓ Extracted {data.num_nodes} nodes and {data.edge_index.size(1)} edges")
    print(f"  Extraction time: {extract_time:.2f}s")
    
    if data.num_nodes == 0:
        print("⚠ No nodes extracted! Check node labels.")
    else:
        print("\n🏋️ Training GNN embeddings...")
        start_train = time.time()
        stats = gnn_service.train_embeddings(data, epochs=100, lr=0.001)
        train_time = time.time() - start_train
        
        print(f"✓ Training completed in {train_time:.2f}s")
        print(f"  Final loss: {stats['final_loss']:.4f}")
        print(f"  Average loss: {stats['avg_loss']:.4f}")
        
        # Test link predictions
        print("\n🔗 Testing link predictions...")
        test_nodes = list(node_map.keys())[:min(10, len(node_map))]
        predictions = []
        
        for i in range(0, len(test_nodes)-1, 2):
            pred = gnn_service.predict_link(test_nodes[i], test_nodes[i+1])
            predictions.append(pred)
        
        avg_confidence = sum(p['confidence'] for p in predictions) / len(predictions) if predictions else 0
        print(f"✓ Tested {len(predictions)} predictions")
        print(f"  Average confidence: {avg_confidence:.3f}")
    
    # ========================================================================
    # STEP 4: Hybrid Reasoning Tests
    # ========================================================================
    print_header("STEP 4: Hybrid Reasoning Engine Tests")
    
    reasoner = HybridReasoningEngine(driver, gnn_service, symbolic_weight=0.6, neural_weight=0.4)
    
    test_queries = [
        {"start": "Western Province", "end": "Colombo"},
        {"start": "Colombo", "end": "Kandy"},
        {"start": "Galle", "end": "Ella"}
    ]
    
    reasoning_results = []
    for query in test_queries:
        print(f"📍 Testing: {query['start']} → {query['end']}")
        result = reasoner.reason_itinerary(
            start_location=query["start"],
            end_location=query["end"],
            constraints={"interests": ["history"], "min_rating": 4.0},
            query_date=datetime(2026, 2, 15)
        )
        reasoning_results.append(result)
        print(f"  Confidence: {result['overall_confidence']:.3f}")
        print(f"  Steps: {len(result['explanation']['chain'])}")
    
    avg_reasoning_confidence = sum(r['overall_confidence'] for r in reasoning_results) / len(reasoning_results)
    print(f"\n✓ Average reasoning confidence: {avg_reasoning_confidence:.3f}")
    
    # ========================================================================
    # STEP 5: API Endpoint Validation
    # ========================================================================
    print_header("STEP 5: API Endpoint Validation")
    
    try:
        import httpx
        
        endpoints = [
            ("GET", "http://localhost:8000/health"),
            ("POST", "http://localhost:8000/ail/query", {"cypher": "MATCH (n) RETURN count(n) LIMIT 1"}),
            ("POST", "http://localhost:8000/ail/validate", {"entity_type": None})
        ]
        
        print("🌐 Testing API endpoints...")
        for method, url, *payload in endpoints:
            try:
                if method == "GET":
                    response = httpx.get(url, timeout=5.0)
                else:
                    response = httpx.post(url, json=payload[0] if payload else {}, timeout=5.0)
                
                status = "✓" if response.status_code < 400 else "✗"
                print(f"  {status} {method} {url.split('/')[-1]}: {response.status_code}")
            except Exception as e:
                print(f"  ✗ {method} {url.split('/')[-1]}: {str(e)[:50]}")
    
    except ImportError:
        print("⚠ httpx not installed, skipping API tests")
        print("  Install with: uv pip install httpx")
    
    # ========================================================================
    # FINAL REPORT
    # ========================================================================
    print_header("SUMMARY REPORT")
    
    report = {
        "Database": {
            "Total Nodes": total_nodes,
            "Total Relationships": total_rels,
            "Entity Types": len(labels)
        },
        "SHACL Validation": {
            "Shapes Installed": installed,
            "Conforming Types": conforming,
            "Validation Pass Rate": f"{(conforming/len(validation_results)*100):.1f}%"
        },
        "GNN Training": {
            "Nodes Trained": data.num_nodes if 'data' in locals() else 0,
            "Edges": data.edge_index.size(1) if 'data' in locals() else 0,
            "Final Loss": f"{stats['final_loss']:.4f}" if 'stats' in locals() else "N/A",
            "Training Time": f"{train_time:.2f}s" if 'train_time' in locals() else "N/A"
        },
        "Link Prediction": {
            "Tests": len(predictions) if 'predictions' in locals() else 0,
            "Avg Confidence": f"{avg_confidence:.3f}" if 'avg_confidence' in locals() else "N/A"
        },
        "Hybrid Reasoning": {
            "Test Queries": len(reasoning_results),
            "Avg Confidence": f"{avg_reasoning_confidence:.3f}"
        }
    }
    
    print("📊 System Performance Metrics:\n")
    for category, metrics in report.items():
        print(f"  {category}:")
        for metric, value in metrics.items():
            print(f"    • {metric}: {value}")
        print()
    
    # Save report
    import json
    report_file = f"system_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Add detailed breakdown
    report["Detailed_Breakdown"] = {
        "Top_Node_Types": dict(sorted_labels[:5]),
        "GNN_Node_Coverage": f"{data.num_nodes}/{total_nodes} nodes ({(data.num_nodes/total_nodes*100):.1f}%)" if total_nodes > 0 else "N/A",
        "Training_Stats": stats if 'stats' in locals() else {},
        "Reasoning_Tests": [
            {
                "query": f"{q['start']} → {q['end']}",
                "confidence": r['overall_confidence']
            }
            for q, r in zip(test_queries, reasoning_results)
        ] if 'reasoning_results' in locals() else []
    }
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"💾 Full report saved: {report_file}")
    
    # Next steps
    print("\n" + "=" * 70)
    print("✅ SETUP COMPLETE!")
    print("=" * 70)
    print("\n💡 Next Steps:")
    print("  1. Run thesis visualizations: uv run demo_with_viz.py")
    print("  2. Explore API: http://localhost:8000/docs")
    print("  3. Test validation: http://localhost:8000/ail/validate")
    print("  4. Run ablation studies for research paper")
    print("  5. Collect user study data")
    
    # Cleanup
    driver.close()
    
    print(f"\n🎉 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
