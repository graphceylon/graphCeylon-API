"""
Comprehensive GNN API Testing & Score Analysis

Tests all GNN endpoints, analyzes prediction scores, and provides recommendations.
"""

import requests
import json
import time
from typing import Dict, List, Any
from collections import defaultdict

# Configuration
BASE_URL = "http://localhost:8000"
API_PREFIX = "/research"


class GNNAPITester:
    """Test and analyze GNN API performance."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results = {
            "training": None,
            "link_predictions": [],
            "cross_type_predictions": [],
            "analysis": {}
        }
    
    def print_section(self, title: str):
        """Print formatted section header."""
        print("\n" + "="*80)
        print(f"  {title}")
        print("="*80)
    
    def test_health(self) -> bool:
        """Test API health."""
        self.print_section("1. Health Check")
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                print("✅ API is healthy")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to API: {e}")
            return False
    
    def get_initial_status(self) -> Dict[str, Any]:
        """Get GNN status before training."""
        self.print_section("2. Initial GNN Status (Before Training)")
        try:
            response = requests.get(f"{self.base_url}{API_PREFIX}/gnn/status")
            status = response.json()
            print(f"Trained: {status.get('trained', False)}")
            print(f"Embedding Dim: {status.get('embedding_dim', 'N/A')}")
            print(f"Device: {status.get('device', 'N/A')}")
            return status
        except Exception as e:
            print(f"❌ Error getting status: {e}")
            return {}
    
    def train_gnn(self, epochs: int = 200) -> Dict[str, Any]:
        """Train GNN model."""
        self.print_section(f"3. Training GNN ({epochs} epochs)")
        
        train_request = {
            "embedding_dim": 64,
            "epochs": epochs,
            "learning_rate": 0.001,
            "node_limit": 5000
        }
        
        print(f"Training parameters: {json.dumps(train_request, indent=2)}")
        print("\nTraining... (this may take a few seconds)")
        
        start_time = time.time()
        try:
            response = requests.post(
                f"{self.base_url}{API_PREFIX}/gnn/train",
                json=train_request,
                timeout=60
            )
            training_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                self.results["training"] = result
                
                stats = result.get("training_stats", {})
                print(f"\n✅ Training completed in {training_time:.2f}s")
                print(f"   Final Loss: {stats.get('final_loss', 'N/A'):.4f}")
                print(f"   Num Nodes: {stats.get('num_nodes', 'N/A')}")
                print(f"   Num Edges: {stats.get('num_edges', 'N/A')}")
                
                node_dist = stats.get('node_type_distribution', {})
                if node_dist:
                    print(f"\n   Node Type Distribution:")
                    for node_type, count in sorted(node_dist.items(), key=lambda x: x[1], reverse=True):
                        print(f"      {node_type}: {count}")
                
                return result
            else:
                print(f"❌ Training failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return {}
        except Exception as e:
            print(f"❌ Training error: {e}")
            return {}
    
    def get_trained_status(self) -> Dict[str, Any]:
        """Get GNN status after training."""
        self.print_section("4. GNN Status (After Training)")
        try:
            response = requests.get(f"{self.base_url}{API_PREFIX}/gnn/status")
            status = response.json()
            
            print(f"Trained: {status.get('trained', False)}")
            print(f"Model Type: {status.get('model_type', 'N/A')}")
            print(f"Num Embeddings: {status.get('num_embeddings', 'N/A')}")
            print(f"Node Types Trained: {status.get('node_types_trained', 'N/A')}")
            
            sample_entities = status.get('sample_entities', [])
            if sample_entities:
                print(f"\nSample Entities (first 10):")
                for entity in sample_entities[:10]:
                    print(f"   - {entity.get('name', 'N/A')} ({', '.join(entity.get('labels', []))})")
            
            return status
        except Exception as e:
            print(f"❌ Error getting status: {e}")
            return {}
    
    def test_link_predictions(self) -> List[Dict[str, Any]]:
        """Test same-type link predictions."""
        self.print_section("5. Link Predictions (Same Type)")
        
        test_cases = [
            ("Sigiriya", "Kandy"),
            ("Dambulla", "Horton Plains"),
            ("Yala National Park", "Colombo"),
            ("Anuradhapura", "Polonnaruwa"),
            ("Bentota", "Colombo")
        ]
        
        results = []
        for entity1, entity2 in test_cases:
            try:
                response = requests.post(
                    f"{self.base_url}{API_PREFIX}/gnn/predict-link",
                    json={"entity1": entity1, "entity2": entity2},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    confidence = result.get('confidence', 0.0)
                    exists = result.get('exists', False)
                    
                    # Categorize score quality
                    quality = self._score_quality(confidence)
                    
                    print(f"\n{entity1} ↔ {entity2}")
                    print(f"   Confidence: {confidence:.4f} ({quality})")
                    print(f"   Exists: {exists}")
                    
                    results.append({
                        "entity1": entity1,
                        "entity2": entity2,
                        "confidence": confidence,
                        "exists": exists,
                        "quality": quality
                    })
                else:
                    print(f"\n❌ {entity1} ↔ {entity2}: {response.status_code}")
                    print(f"   Error: {response.text[:200]}")
            
            except Exception as e:
                print(f"\n❌ {entity1} ↔ {entity2}: {e}")
        
        self.results["link_predictions"] = results
        return results
    
    def test_cross_type_predictions(self) -> List[Dict[str, Any]]:
        """Test cross-type predictions."""
        self.print_section("6. Cross-Type Predictions (Heterogeneous)")
        
        test_cases = [
            ("Sigiriya", "District", 3, "Geographic inference"),
            ("Kandy", "Attraction", 5, "Reverse lookup"),
            ("Yala National Park", "Month", 5, "Temporal patterns"),
            ("Dambulla", "District", 3, "Geographic inference"),
            ("Colombo", "Attraction", 5, "Nearby attractions"),
        ]
        
        results = []
        for source, target_type, top_k, description in test_cases:
            try:
                response = requests.post(
                    f"{self.base_url}{API_PREFIX}/gnn/predict-cross-type",
                    json={
                        "source_entity": source,
                        "target_type": target_type,
                        "top_k": top_k
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    predictions = result.get('predictions', [])
                    
                    print(f"\n{source} → {target_type} ({description})")
                    print(f"   Found {len(predictions)} predictions:")
                    
                    avg_confidence = 0
                    for i, pred in enumerate(predictions[:5], 1):
                        name = pred.get('name', 'N/A')
                        conf = pred.get('confidence', 0.0)
                        avg_confidence += conf
                        quality = self._score_quality(conf)
                        print(f"      {i}. {name}: {conf:.4f} ({quality})")
                    
                    if predictions:
                        avg_confidence /= len(predictions[:5])
                        avg_quality = self._score_quality(avg_confidence)
                        
                        results.append({
                            "source": source,
                            "target_type": target_type,
                            "description": description,
                            "num_predictions": len(predictions),
                            "top_prediction": predictions[0].get('name', 'N/A') if predictions else None,
                            "top_confidence": predictions[0].get('confidence', 0.0) if predictions else 0.0,
                            "avg_confidence": avg_confidence,
                            "avg_quality": avg_quality
                        })
                else:
                    print(f"\n❌ {source} → {target_type}: {response.status_code}")
                    print(f"   Error: {response.text[:200]}")
            
            except Exception as e:
                print(f"\n❌ {source} → {target_type}: {e}")
        
        self.results["cross_type_predictions"] = results
        return results
    
    def _score_quality(self, score: float) -> str:
        """Categorize prediction score quality."""
        if score >= 0.8:
            return "EXCELLENT ⭐⭐⭐"
        elif score >= 0.65:
            return "GOOD ⭐⭐"
        elif score >= 0.5:
            return "FAIR ⭐"
        else:
            return "POOR ⚠️"
    
    def analyze_results(self):
        """Analyze all test results and provide recommendations."""
        self.print_section("7. ANALYSIS & RECOMMENDATIONS")
        
        # Analyze training
        print("\n📊 TRAINING ANALYSIS")
        if self.results["training"]:
            stats = self.results["training"].get("training_stats", {})
            final_loss = stats.get("final_loss", float('inf'))
            num_nodes = stats.get("num_nodes", 0)
            num_edges = stats.get("num_edges", 0)
            
            print(f"   Final Loss: {final_loss:.4f}")
            if final_loss < 0.8:
                print("   ✅ Loss is good (< 0.8) - model converged well")
            elif final_loss < 1.2:
                print("   ⚠️  Loss is moderate (0.8-1.2) - could be improved")
            else:
                print("   ❌ Loss is high (> 1.2) - needs improvement")
            
            print(f"\n   Graph Scale: {num_nodes} nodes, {num_edges} edges")
            if num_nodes > 300:
                print("   ✅ Good graph size for heterogeneous learning")
            else:
                print("   ⚠️  Small graph - consider adding more nodes")
        
        # Analyze link predictions
        print("\n📊 LINK PREDICTION ANALYSIS")
        if self.results["link_predictions"]:
            confidences = [r['confidence'] for r in self.results["link_predictions"]]
            avg_conf = sum(confidences) / len(confidences)
            
            quality_counts = defaultdict(int)
            for r in self.results["link_predictions"]:
                quality_counts[r['quality']] += 1
            
            print(f"   Average Confidence: {avg_conf:.4f}")
            print(f"   Quality Distribution:")
            for quality, count in sorted(quality_counts.items()):
                print(f"      {quality}: {count}/{len(confidences)}")
            
            if avg_conf >= 0.65:
                print("   ✅ Link predictions are strong")
            elif avg_conf >= 0.5:
                print("   ⚠️  Link predictions are moderate - room for improvement")
            else:
                print("   ❌ Link predictions are weak - needs improvement")
        
        # Analyze cross-type predictions
        print("\n📊 CROSS-TYPE PREDICTION ANALYSIS")
        if self.results["cross_type_predictions"]:
            avg_confidences = [r['avg_confidence'] for r in self.results["cross_type_predictions"]]
            top_confidences = [r['top_confidence'] for r in self.results["cross_type_predictions"]]
            
            overall_avg = sum(avg_confidences) / len(avg_confidences)
            top_avg = sum(top_confidences) / len(top_confidences)
            
            print(f"   Average Confidence (all predictions): {overall_avg:.4f}")
            print(f"   Average Top-1 Confidence: {top_avg:.4f}")
            
            quality_counts = defaultdict(int)
            for r in self.results["cross_type_predictions"]:
                quality_counts[r['avg_quality']] += 1
            
            print(f"   Quality Distribution:")
            for quality, count in sorted(quality_counts.items()):
                print(f"      {quality}: {count}/{len(avg_confidences)}")
            
            if overall_avg >= 0.65:
                print("   ✅ Cross-type predictions are strong")
            elif overall_avg >= 0.5:
                print("   ⚠️  Cross-type predictions are moderate")
            else:
                print("   ❌ Cross-type predictions are weak")
        
        # Recommendations
        self._provide_recommendations()
    
    def _provide_recommendations(self):
        """Provide improvement recommendations."""
        print("\n🔧 RECOMMENDATIONS FOR IMPROVEMENT")
        
        issues = []
        recommendations = []
        
        # Check training
        if self.results["training"]:
            stats = self.results["training"].get("training_stats", {})
            final_loss = stats.get("final_loss", float('inf'))
            
            if final_loss > 1.0:
                issues.append("High training loss")
                recommendations.append(
                    "1. INCREASE TRAINING EPOCHS\n"
                    "   - Current: 200 epochs\n"
                    "   - Try: 500-1000 epochs\n"
                    "   - Or train until loss < 0.8"
                )
                recommendations.append(
                    "2. ADJUST LEARNING RATE\n"
                    "   - Current: 0.001\n"
                    "   - Try: 0.0005 (slower, more stable)\n"
                    "   - Or use learning rate scheduler"
                )
        
        # Check link predictions
        if self.results["link_predictions"]:
            confidences = [r['confidence'] for r in self.results["link_predictions"]]
            avg_conf = sum(confidences) / len(confidences)
            
            if avg_conf < 0.6:
                issues.append("Low link prediction confidence")
                recommendations.append(
                    "3. IMPROVE FEATURE ENGINEERING\n"
                    "   - Add more node properties (ratings, categories, coordinates)\n"
                    "   - Use text embeddings (TF-IDF or BERT) for descriptions\n"
                    "   - Encode temporal features (dates, seasons)"
                )
                recommendations.append(
                    "4. ADJUST MODEL ARCHITECTURE\n"
                    "   - Increase hidden dimensions (64 → 128)\n"
                    "   - Add more GAT layers (3 → 4 or 5)\n"
                    "   - Increase attention heads (4 → 8)"
                )
        
        # Check cross-type predictions
        if self.results["cross_type_predictions"]:
            avg_confidences = [r['avg_confidence'] for r in self.results["cross_type_predictions"]]
            overall_avg = sum(avg_confidences) / len(avg_confidences)
            
            if overall_avg < 0.6:
                issues.append("Low cross-type prediction confidence")
                recommendations.append(
                    "5. ENHANCE TYPE-AWARE FEATURES\n"
                    "   - Improve one-hot encoding (current: 27 dims)\n"
                    "   - Add type-specific features (current: 5 dims)\n"
                    "   - Use type embeddings instead of one-hot"
                )
                recommendations.append(
                    "6. ADD MORE GRAPH RELATIONSHIPS\n"
                    "   - Ensure District-Attraction edges exist\n"
                    "   - Add temporal edges (Month-Attraction, Holiday-Month)\n"
                    "   - Create Policy-Location edges"
                )
        
        if issues:
            print(f"\n⚠️  ISSUES DETECTED:")
            for issue in issues:
                print(f"   - {issue}")
            
            print(f"\n💡 RECOMMENDED ACTIONS:")
            for rec in recommendations:
                print(f"\n{rec}")
        else:
            print("\n✅ All scores look good! Model is performing well.")
            print("\n💡 OPTIONAL ENHANCEMENTS:")
            print("\n1. FINE-TUNE FOR PRODUCTION\n   - Train for more epochs (500+)\n   - Use GPU if available\n   - Implement early stopping")
            print("\n2. ADD VALIDATION SET\n   - Split edges into train/val/test\n   - Monitor validation accuracy\n   - Prevent overfitting")
            print("\n3. EXPERIMENT WITH HYPERPARAMETERS\n   - Try different embedding dimensions (32, 64, 128)\n   - Test different attention heads (2, 4, 8)\n   - Adjust dropout (0.1, 0.2, 0.3)")
    
    def save_results(self, filename: str = "gnn_test_results.json"):
        """Save test results to file."""
        self.print_section("8. Saving Results")
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"✅ Results saved to: {filename}")
        except Exception as e:
            print(f"❌ Error saving results: {e}")
    
    def run_full_test(self):
        """Run complete test suite."""
        print("\n" + "="*80)
        print("  GNN API COMPREHENSIVE TEST & ANALYSIS")
        print("="*80)
        
        # Health check
        if not self.test_health():
            print("\n❌ API not available. Please start the server first:")
            print("   cd services/kg_service/src")
            print("   uvicorn main:app --reload --port 8000")
            return
        
        # Get initial status
        self.get_initial_status()
        
        # Train GNN
        training_result = self.train_gnn(epochs=200)
        if not training_result:
            print("\n❌ Training failed. Cannot continue tests.")
            return
        
        # Get trained status
        self.get_trained_status()
        
        # Test link predictions
        self.test_link_predictions()
        
        # Test cross-type predictions
        self.test_cross_type_predictions()
        
        # Analyze results
        self.analyze_results()
        
        # Save results
        self.save_results()
        
        print("\n" + "="*80)
        print("  TEST COMPLETE")
        print("="*80)


if __name__ == "__main__":
    tester = GNNAPITester()
    tester.run_full_test()
