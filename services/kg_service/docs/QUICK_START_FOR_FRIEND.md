# Quick Start Guide - GNN System for Tourism KG

Hey! 👋 Here's everything you need to get started with the GNN (Graph Neural Network) system for our Tourism Knowledge Graph.

## 🎯 What This System Does

This system uses **AI to predict connections** in our tourism knowledge graph. Instead of only finding explicit relationships in the database, it learns patterns and can predict:
- Which hotels are near which attractions (even if not explicitly linked)
- Similar destinations based on features
- Missing relationships in the knowledge graph
- Smart travel itineraries combining rules + AI

## 📦 What You Received

All GNN-related code and docs have been committed to the `dana/feat/knowledge-graph-service` branch:

### Core Implementation Files:
1. **`src/models/temporal.py`** - Time and metadata handling
2. **`src/services/config/gnn_config.py`** - GNN hyperparameters
3. **`src/services/gnn_embeddings.py`** - Main GNN training & inference (810 lines!)
4. **`src/services/hybrid_reasoning.py`** - Combines rules + AI (566 lines)
5. **`src/api/research.py`** - REST API endpoints (570 lines)
6. **`tests/test_hybrid_system.py`** - Comprehensive tests

### Documentation (Start Here!):
1. **`GNN_TRAINING_AND_USAGE_GUIDE.md`** ⭐ **START HERE** - Complete training & usage tutorial
2. **`GNN_MODULE_README.md`** - Technical architecture overview
3. **`HETEROGENEOUS_GNN_COMPLETE_GUIDE.md`** - Deep dive into the GNN design
4. **`GNN_FOR_KNOWLEDGE_GRAPHS_EXPLAINED.md`** - Theory behind GNNs
5. **`WHY_GNN_FOR_TOURISM_KG.md`** - Why we chose this approach
6. **`HYBRID_REASONING.md`** - How symbolic + neural reasoning works
7. **`GNN_PRODUCTION_CONFIG.md`** - Production deployment guide

### Testing Tools:
- **`GNN_Postman_Collection.json`** - API test collection
- **`scripts/`** - Utility scripts for analysis and visualization

## 🚀 Quick Start (3 Steps)

### Step 1: Setup Environment
```bash
cd services/kg_service
pip install torch torch-geometric neo4j fastapi uvicorn
```

### Step 2: Start Service
```bash
cd src
uvicorn api.main:app --reload --port 8000
```

### Step 3: Train GNN
```bash
curl -X POST http://localhost:8000/research/gnn/train -d '{}'
```

That's it! Training takes ~45 seconds. You'll see:
```json
{
  "status": "success",
  "training_stats": {
    "accuracy": 0.87,
    "nodes_processed": 383,
    "training_time_seconds": 45.2
  }
}
```

## 🎓 How to Use After Training

### 1. Predict if Two Places Should Be Connected
```bash
curl -X POST http://localhost:8000/research/link_prediction \
  -H "Content-Type: application/json" \
  -d '{
    "entity1": "Sigiriya",
    "entity2": "Dambulla"
  }'
```

**Result:** Confidence score (0-1) showing how likely they should be connected.

### 2. Find Similar Attractions
```bash
curl -X POST http://localhost:8000/research/similar_entities \
  -H "Content-Type: application/json" \
  -d '{
    "entity_name": "Galle Fort",
    "top_k": 5
  }'
```

**Result:** Top 5 most similar attractions with similarity scores.

### 3. Smart Itinerary Planning (Hybrid AI)
```bash
curl -X POST http://localhost:8000/research/hybrid_reason \
  -H "Content-Type: application/json" \
  -d '{
    "start_location": "Colombo",
    "end_location": "Galle",
    "constraints": {
      "budget": 50000,
      "interests": ["history", "beaches"]
    }
  }'
```

**Result:** Complete itinerary using both database rules + AI predictions.

## 📚 Learning Path

1. **Day 1**: Read `GNN_TRAINING_AND_USAGE_GUIDE.md` - Get comfortable with basic training
2. **Day 2**: Try all API endpoints using Postman collection
3. **Day 3**: Read `HETEROGENEOUS_GNN_COMPLETE_GUIDE.md` - Understand the architecture
4. **Day 4**: Read `HYBRID_REASONING.md` - Understand how symbolic + neural work together
5. **Day 5**: Experiment with hyperparameters in `gnn_config.py`

## 🔧 Key Configuration

Edit `src/services/config/gnn_config.py`:

```python
gnn_config = {
    "embedding_dim": 64,        # Higher = more detail (but slower)
    "epochs": 200,              # More epochs = better accuracy (but slower)
    "learning_rate": 0.001,     # Lower = more stable training
    "node_limit": 5000,         # Max nodes to train on
    
    # Hybrid reasoning weights
    "symbolic_weight": 0.6,     # 60% rule-based
    "neural_weight": 0.4        # 40% AI predictions
}
```

## 🎯 Expected Performance

| Metric | Value |
|--------|-------|
| Training Time | 30-60 seconds (CPU) |
| Link Prediction Accuracy | 85-90% |
| API Response Time | < 50ms |
| Memory Usage | ~300 MB |

## ⚠️ Common Issues & Solutions

### Issue: "GNN Service Not Initialized"
**Solution:** You forgot to train! Run the training endpoint first.

### Issue: Training fails with "No nodes found"
**Solution:** Check Neo4j connection and ensure data exists:
```bash
curl http://localhost:8000/kg/statistics
```

### Issue: Low accuracy (< 70%)
**Solution:** Increase epochs to 500 or add more data to Neo4j.

## 📊 Understanding the Output

### Link Prediction Response
```json
{
  "confidence": 0.89,     // 89% sure they should be connected
  "exists": false,        // No edge in DB currently
  "method": "gnn"         // Prediction from neural network
}
```

**Action:** If confidence > 0.8 and exists = false → consider adding this relationship!

### Hybrid Reasoning Response
```json
{
  "explanation_chain": [
    {
      "step": 1,
      "method": "symbolic",      // Database query
      "confidence": 1.0           // 100% certain (exact match)
    },
    {
      "step": 2,
      "method": "gnn",            // AI prediction
      "confidence": 0.87          // 87% confidence
    },
    {
      "step": 3,
      "method": "ensemble",       // Combined result
      "confidence": 0.92          // Weighted average
    }
  ]
}
```

**Interpretation:** Final confidence = (0.6 × 1.0) + (0.4 × 0.87) = 0.92

## 🛠️ Development Workflow

1. **Make changes** to `gnn_embeddings.py` or `hybrid_reasoning.py`
2. **Restart server** (auto-reload should catch it)
3. **Retrain model**: `POST /research/gnn/train`
4. **Test**: Use Postman collection or `tests/test_hybrid_system.py`
5. **Commit**: Use meaningful messages!

## 📞 Need Help?

1. **Start with**: `GNN_TRAINING_AND_USAGE_GUIDE.md` (most comprehensive)
2. **API questions**: Check Postman collection examples
3. **Theory questions**: Read `GNN_FOR_KNOWLEDGE_GRAPHS_EXPLAINED.md`
4. **Production deployment**: Read `GNN_PRODUCTION_CONFIG.md`
5. **Still stuck**: Check code comments in `gnn_embeddings.py` (heavily documented!)

## 🎁 Cool Things to Try

### 1. Find Hidden Connections
Train the model, then check link predictions for unconnected nodes. You might discover relationships that should exist!

### 2. Quality Control
Use similarity search to find duplicate or near-duplicate attractions that should be merged.

### 3. Recommendation Engine
Use cross-type prediction to build "if you liked X, you'll love Y" features.

### 4. Data Augmentation
Use high-confidence predictions (> 0.9) to automatically suggest new edges for the knowledge graph.

## 📈 Next Steps After Mastery

1. **Tune hyperparameters** for your specific dataset
2. **Add more node types** (currently handles 9 types)
3. **Implement relationship type prediction** (predict which type of edge)
4. **Add attention weight visualization** (see what the model focuses on)
5. **Deploy to production** using the production config guide

## ✅ Checklist for Success

- [ ] Read `GNN_TRAINING_AND_USAGE_GUIDE.md`
- [ ] Successfully train model once
- [ ] Test all 3 main API endpoints (link prediction, similarity, hybrid reasoning)
- [ ] Understand the explanation_chain output
- [ ] Read through `gnn_embeddings.py` code comments
- [ ] Experiment with changing hyperparameters
- [ ] Run the test suite: `pytest tests/test_hybrid_system.py`

---

**Remember**: The GNN is a tool to **augment**, not replace, your knowledge graph. Use it to find patterns, suggest connections, and improve user experience - but always validate important predictions manually!

Good luck! 🚀

---

## 📝 Commit History (for reference)

All these commits are on `dana/feat/knowledge-graph-service` branch:

```
8ec4a41 Add gitignore and utility scripts
f17ec90 Add Postman collection for GNN API testing
177a8b9 Add hybrid reasoning and production configuration docs
810a1d3 Add GNN concepts and rationale documentation
b821876 Add GNN module documentation and heterogeneous guide
1bf16ea Add comprehensive GNN training and usage guide
4e9ebf2 Add comprehensive tests for hybrid reasoning system
ec92e38 Add research API endpoints for GNN training and inference
769549b Implement hybrid reasoning engine combining symbolic and neural methods
ed4cfbf Implement GNN embedding service with GAT architecture
8ef116f Add GNN configuration module
59b081f Add temporal and provenance metadata models
```

**To pull these commits:**
```bash
git fetch origin
git checkout dana/feat/knowledge-graph-service
git pull origin dana/feat/knowledge-graph-service
```
