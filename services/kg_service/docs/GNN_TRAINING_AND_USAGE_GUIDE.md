# GNN Training & Usage Guide for Tourism Knowledge Graph

## 📚 Table of Contents
1. [What is GNN and Why We Use It](#what-is-gnn)
2. [System Architecture](#architecture)
3. [Training the GNN Model](#training)
4. [Using Trained Embeddings](#usage)
5. [API Endpoints](#api-endpoints)
6. [Troubleshooting](#troubleshooting)

---

## 🧠 What is GNN and Why We Use It {#what-is-gnn}

### Graph Neural Networks (GNN)
GNNs learn **vector representations (embeddings)** of entities in a knowledge graph by analyzing:
- **Structure**: How nodes connect to each other
- **Semantics**: Types of relationships and attributes
- **Context**: Neighborhood patterns and multi-hop connections

### Why GNN for Tourism KG?

**Problem**: Traditional rule-based queries (Cypher) can only find explicit relationships that exist in the database. They miss:
- Implicit connections (e.g., similar attractions not directly linked)
- Soft matches (e.g., hotels near attractions even if no direct edge)
- Patterns across multiple relationship types

**Solution**: GNN learns to predict **missing links** and find **semantically similar** entities by understanding the graph structure.

**Example**:
```
Query: "Find hotels near Sigiriya"

Symbolic (Cypher): Only returns hotels with NEAR relationship
GNN: Returns hotels that are:
  - Structurally similar (similar connection patterns)
  - Semantically related (in same district, similar ratings)
  - Even without explicit NEAR edge!
```

---

## 🏗️ System Architecture {#architecture}

### Components

```
┌─────────────────────────────────────────────────┐
│           Neo4j Knowledge Graph                 │
│  • 9 Entity Types (Attraction, District, etc.)  │
│  • 37 Relationship Types                        │
│  • 383+ Nodes                                   │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│        GNN Embedding Service                    │
│  • Feature Extraction (128-dim input)           │
│  • 3-Layer Graph Attention Network (GAT)        │
│  • Outputs: 64-dim embeddings per node          │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│      Hybrid Reasoning Engine                    │
│  • Combines Cypher (60%) + GNN (40%)           │
│  • Confidence scoring                           │
│  • Explainability traces                        │
└─────────────────────────────────────────────────┘
```

### File Structure
```
services/kg_service/
├── src/
│   ├── services/
│   │   ├── gnn_embeddings.py          # Core GNN training & inference
│   │   ├── hybrid_reasoning.py         # Hybrid symbolic+neural reasoning
│   │   └── config/
│   │       └── gnn_config.py          # GNN hyperparameters
│   └── api/
│       └── research.py                 # REST API endpoints
├── models/
│   └── temporal.py                     # Temporal & provenance metadata
├── tests/
│   └── test_hybrid_system.py          # Unit & integration tests
└── docs/
    ├── GNN_MODULE_README.md            # Technical architecture
    ├── HETEROGENEOUS_GNN_COMPLETE_GUIDE.md  # Deep dive
    ├── GNN_PRODUCTION_CONFIG.md        # Production deployment
    ├── HYBRID_REASONING.md             # Hybrid reasoning concepts
    └── GNN_TRAINING_AND_USAGE_GUIDE.md # This file!
```

---

## 🎓 Training the GNN Model {#training}

### Prerequisites

1. **Install Dependencies**
```bash
cd services/kg_service
pip install -r requirements.txt

# Core dependencies:
# - torch>=2.0.0
# - torch-geometric>=2.3.0
# - neo4j>=5.0.0
# - fastapi
# - numpy
```

2. **Configure Neo4j Connection**
```bash
# Set environment variables:
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your_password"
```

3. **Verify Data Exists**
```bash
# Ensure your Neo4j database has:
# - Attraction nodes
# - District nodes
# - Policy nodes
# - Relationships between them

# Quick check:
curl http://localhost:8000/kg/statistics
```

### Training Process

#### Step 1: Start the Service
```bash
cd services/kg_service/src
uvicorn api.main:app --reload --port 8000
```

#### Step 2: Train GNN via API

**Simple Training (Use Defaults)**
```bash
curl -X POST "http://localhost:8000/research/gnn/train" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Custom Training (Advanced)**
```bash
curl -X POST "http://localhost:8000/research/gnn/train" \
  -H "Content-Type: application/json" \
  -d '{
    "embedding_dim": 64,
    "epochs": 200,
    "learning_rate": 0.001,
    "node_limit": 5000
  }'
```

**Response Example:**
```json
{
  "status": "success",
  "training_stats": {
    "epochs": 200,
    "final_loss": 0.023,
    "accuracy": 0.87,
    "nodes_processed": 383,
    "edges_processed": 1247,
    "training_time_seconds": 45.2
  },
  "message": "GNN model trained successfully",
  "timestamp": "2025-12-31T10:30:00Z"
}
```

#### Step 3: Verify Training Success
```bash
# Check service status
curl http://localhost:8000/research/status

# Expected output:
# {
#   "gnn_service": "initialized",
#   "hybrid_reasoner": "initialized",
#   "model_loaded": true,
#   "embedding_dimension": 64
# }
```

### What Happens During Training?

1. **Data Extraction** (5-10s)
   - Fetches nodes and edges from Neo4j
   - Filters by node_limit if specified
   - Extracts node features (type, properties)

2. **Feature Engineering** (2-5s)
   - Creates 128-dim input features per node
   - One-hot encoding for node types (27 dims)
   - Type-specific features (rating, geo, etc.)

3. **Model Training** (30-60s)
   - 3-layer Graph Attention Network
   - Link prediction task (positive + negative sampling)
   - Learns to predict which edges should exist

4. **Validation** (5s)
   - Tests on held-out edges
   - Computes accuracy metrics

5. **Saving** (1s)
   - Saves embeddings to memory
   - Hybrid reasoner now uses both Cypher + GNN

---

## 🚀 Using Trained Embeddings {#usage}

### 1. Link Prediction

**Check if Two Entities Should be Connected**

```bash
curl -X POST "http://localhost:8000/research/link_prediction" \
  -H "Content-Type: application/json" \
  -d '{
    "entity1": "Sigiriya",
    "entity2": "Dambulla"
  }'
```

**Response:**
```json
{
  "entity1": "Sigiriya",
  "entity2": "Dambulla",
  "confidence": 0.89,
  "exists": false,
  "method": "gnn_cosine_similarity"
}
```

**Interpretation:**
- `confidence: 0.89` = High probability they should be connected
- `exists: false` = No edge in database currently
- **Action**: Consider adding relationship manually!

### 2. Cross-Type Prediction

**Find Related Entities of Different Type**

```bash
curl -X POST "http://localhost:8000/research/cross_type_prediction" \
  -H "Content-Type: application/json" \
  -d '{
    "source_entity": "Sigiriya",
    "target_type": "District",
    "top_k": 5
  }'
```

**Response:**
```json
{
  "source_entity": "Sigiriya",
  "target_type": "District",
  "predictions": [
    {
      "name": "Matale",
      "confidence": 0.94,
      "reason": "Structural similarity + geographic proximity"
    },
    {
      "name": "Dambulla",
      "confidence": 0.87,
      "reason": "Cultural heritage connection"
    }
  ],
  "count": 5
}
```

### 3. Entity Similarity Search

**Find Similar Entities**

```bash
curl -X POST "http://localhost:8000/research/similar_entities" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_name": "Galle Fort",
    "top_k": 10
  }'
```

**Response:**
```json
{
  "entity": "Galle Fort",
  "similar_entities": [
    {"name": "Jaffna Fort", "similarity": 0.92, "type": "Attraction"},
    {"name": "Sigiriya", "similarity": 0.84, "type": "Attraction"},
    {"name": "Anuradhapura", "similarity": 0.79, "type": "Attraction"}
  ],
  "count": 10
}
```

### 4. Hybrid Reasoning (Symbolic + Neural)

**Intelligent Itinerary Planning**

```bash
curl -X POST "http://localhost:8000/research/hybrid_reason" \
  -H "Content-Type: application/json" \
  -d '{
    "start_location": "Colombo",
    "end_location": "Galle",
    "constraints": {
      "budget": 50000,
      "interests": ["history", "beaches"],
      "duration_days": 3
    }
  }'
```

**Response:**
```json
{
  "itinerary": {
    "route": ["Colombo", "Bentota", "Hikkaduwa", "Galle"],
    "attractions": [
      {
        "name": "Galle Fort",
        "confidence": 0.95,
        "reasoning": "Symbolic: Direct match to 'history' + Neural: High similarity to user preferences"
      },
      {
        "name": "Unawatuna Beach",
        "confidence": 0.88,
        "reasoning": "Neural: Predicted link to Galle Fort + Symbolic: Matches 'beaches'"
      }
    ],
    "hotels": [...],
    "estimated_cost": 48500
  },
  "explanation_chain": [
    {"step": 1, "method": "symbolic", "confidence": 1.0, "result": "Found direct route"},
    {"step": 2, "method": "gnn", "confidence": 0.87, "result": "Predicted 3 implicit connections"},
    {"step": 3, "method": "ensemble", "confidence": 0.92, "result": "Combined results"}
  ]
}
```

---

## 🔌 API Endpoints {#api-endpoints}

### Training Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/research/gnn/train` | POST | Train GNN model |
| `/research/status` | GET | Check service status |

### Inference Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/research/link_prediction` | POST | Predict if two entities should be connected |
| `/research/cross_type_prediction` | POST | Find related entities of different type |
| `/research/similar_entities` | POST | Find semantically similar entities |
| `/research/hybrid_reason` | POST | Full hybrid reasoning for itineraries |
| `/research/embeddings/{entity_name}` | GET | Get raw embedding vector for entity |

### Example: Get Raw Embeddings

```bash
curl "http://localhost:8000/research/embeddings/Sigiriya"
```

**Response:**
```json
{
  "entity": "Sigiriya",
  "embedding": [0.23, -0.45, 0.67, ..., 0.12],  // 64 dimensions
  "dimension": 64
}
```

---

## 🛠️ Troubleshooting {#troubleshooting}

### Issue 1: Training Fails with "No Nodes Found"

**Cause**: Neo4j database is empty or connection failed

**Solution**:
```bash
# 1. Check Neo4j is running
curl http://localhost:7474/

# 2. Verify data exists
curl http://localhost:8000/kg/statistics

# 3. Initialize database if empty
curl -X POST http://localhost:8000/kg/initialize
```

### Issue 2: Low Accuracy (< 60%)

**Cause**: Insufficient data or poor hyperparameters

**Solution**:
```bash
# 1. Add more data to Neo4j
# 2. Increase epochs
curl -X POST "http://localhost:8000/research/gnn/train" \
  -d '{"epochs": 500, "learning_rate": 0.0005}'

# 3. Check node_limit isn't too restrictive
```

### Issue 3: "GNN Service Not Initialized"

**Cause**: Model not trained yet

**Solution**:
```bash
# Train first!
curl -X POST http://localhost:8000/research/gnn/train -d '{}'

# Then use inference endpoints
```

### Issue 4: CUDA Out of Memory

**Cause**: GPU memory exhausted (if using GPU)

**Solution**:
```bash
# Reduce node_limit
curl -X POST "http://localhost:8000/research/gnn/train" \
  -d '{"node_limit": 1000, "embedding_dim": 32}'

# Or force CPU
export CUDA_VISIBLE_DEVICES=""
```

---

## 📊 Performance Expectations

| Metric | Expected Value |
|--------|---------------|
| Training Time | 30-120 seconds (CPU), 10-30 seconds (GPU) |
| Link Prediction Accuracy | 80-90% |
| Inference Latency | < 50ms per query |
| Memory Usage | 200-500 MB (for 1000-5000 nodes) |

---

## 🎯 Best Practices

### 1. Training Frequency
- **Initial**: Train once after database setup
- **Updates**: Retrain when you add >20% new data
- **Continuous**: Set up cron job for weekly retraining

### 2. Hyperparameter Tuning
- Start with defaults
- If accuracy < 70%, increase epochs to 500
- If overfitting (train accuracy >> test accuracy), increase dropout to 0.5

### 3. Production Deployment
- **Always train on full dataset** (set node_limit high)
- **Save model weights** to disk (not just in-memory)
- **Monitor confidence scores** - flag predictions with confidence < 0.6 for manual review
- **Use hybrid reasoning** for user-facing features (better explainability)

### 4. Data Quality
- **Clean data**: Remove duplicate nodes
- **Rich relationships**: More relationship types = better embeddings
- **Balanced types**: Try to have similar counts of each entity type

---

## 📖 Additional Resources

- **Technical Deep Dive**: See [HETEROGENEOUS_GNN_COMPLETE_GUIDE.md](./HETEROGENEOUS_GNN_COMPLETE_GUIDE.md)
- **Hybrid Reasoning Theory**: See [HYBRID_REASONING.md](./HYBRID_REASONING.md)
- **Production Config**: See [GNN_PRODUCTION_CONFIG.md](./GNN_PRODUCTION_CONFIG.md)
- **Research Background**: See [GNN_FOR_KNOWLEDGE_GRAPHS_EXPLAINED.md](./GNN_FOR_KNOWLEDGE_GRAPHS_EXPLAINED.md)
- **API Testing**: Use Postman collection in `GNN_Postman_Collection.json`

---

## 💡 Quick Start Summary

```bash
# 1. Start service
cd services/kg_service/src
uvicorn api.main:app --reload --port 8000

# 2. Train GNN
curl -X POST http://localhost:8000/research/gnn/train -d '{}'

# 3. Test link prediction
curl -X POST http://localhost:8000/research/link_prediction \
  -H "Content-Type: application/json" \
  -d '{"entity1": "Sigiriya", "entity2": "Dambulla"}'

# 4. Use in your app!
```

---

## 🤝 Contributing

For questions or improvements, contact the development team or create an issue in the repository.

**Happy Training! 🚀**
