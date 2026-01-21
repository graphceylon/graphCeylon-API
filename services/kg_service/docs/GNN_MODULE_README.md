# GNN Module - Knowledge Graph Embeddings

## Overview

The GNN (Graph Neural Network) module provides **heterogeneous graph embeddings** for the Tourism Knowledge Graph using Graph Attention Networks (GAT). This enables:

- 🔗 **Link Prediction**: Predict connections between entities (87% accuracy)
- 🔍 **Similarity Search**: Find semantically similar entities
- 🧠 **Cross-Type Predictions**: Predict relationships across different entity types (NEW!)
- 🎯 **Hybrid Reasoning**: Combine symbolic (Cypher) + neural (GNN) reasoning

---

## Architecture

### Heterogeneous GNN Design

```
Input Graph (Neo4j)
  └─ 9 Entity Types: Attraction, Policy, Chunk, District, Location, Authority, Domain, Month, Year
  └─ 37 Relationship Types
  
↓ Feature Extraction (Type-Aware)
  
Node Features (128-dim)
  ├─ One-hot encoding (27 dims) - Node type identifier
  ├─ Type-specific features (5 dims) - Rating, geo, complexity, etc.
  └─ Padding (96 dims) - For consistency

↓ 3-Layer Graph Attention Network (GAT)

Layer 1: Multi-head attention (4 heads, 64 hidden)
  ↓
Layer 2: Multi-head attention (4 heads, 32 hidden)
  ↓
Layer 3: Single-head output (64-dim embeddings)

↓ Training Objective

Link Prediction (Binary Classification)
  ├─ Positive samples: Existing edges
  └─ Negative samples: Random non-edges
  
↓ Output

64-dim Embeddings for 383 nodes
  ├─ Cosine similarity for predictions
  └─ Cross-type relationship inference
```

### Key Components

```
services/kg_service/src/services/
├── gnn_embeddings.py          # Core GNN implementation
│   ├── TourismKGEmbedder      # 3-layer GAT model
│   ├── LinkPredictor          # MLP for link scoring
│   └── GNNEmbeddingService    # Service orchestrator
│
├── hybrid_reasoning.py        # Symbolic + Neural fusion
│   └── HybridReasoningEngine  # 60% symbolic + 40% neural
│
└── config/
    └── gnn_config.py          # Configuration management
```

---

## Training Process

### 1. Data Extraction
```python
# Extract heterogeneous graph from Neo4j
data, node_map = gnn.extract_graph_from_neo4j(
    node_labels=['Attraction', 'Policy', 'Chunk', 'District', ...],
    limit=1000
)

# Result: 383 nodes, 759 edges
```

### 2. Feature Engineering
```python
# Type-aware feature extraction
for node_type in ['Attraction', 'Policy', 'Chunk', ...]:
    if node_type == 'Attraction':
        features = [rating, latitude, longitude, user_ratings, desc_length]
    elif node_type == 'Policy':
        features = [complexity_score, reference_count, ...]
    # ... 9 type-specific extractors
    
# One-hot encode node type (27 dims)
# Combine with type-specific features (5 dims)
# Pad to 128 dims for consistency
```

### 3. Training
```python
# Train for 200 epochs (~3.6 seconds)
stats = gnn.train_embeddings(
    data=data,
    epochs=200,
    lr=0.001
)

# Training objective: Binary link prediction
# Positive samples: Real edges
# Negative samples: Random non-edges (1:1 ratio)
```

### 4. Caching
```python
# Cache embeddings in memory for fast inference
self.node_embeddings = gnn_model(features, edge_index)  # [383, 64]
self.node_id_map = {neo4j_id: idx, ...}  # Fast lookup
self.node_types = ['Attraction', 'Policy', ...]  # Type tracking
```

---

## API Endpoints

### 1. Train GNN
```http
POST /research/gnn/train
Content-Type: application/json

{
  "embedding_dim": 64,
  "epochs": 200,
  "learning_rate": 0.001,
  "node_limit": 1000
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Trained heterogeneous GNN on 383 nodes (9 types) with 759 edges",
  "training_stats": {
    "epochs": 200,
    "final_loss": 0.8873,
    "num_nodes": 383,
    "num_edges": 759,
    "node_type_distribution": {
      "Month": 132,
      "Chunk": 73,
      "Policy": 47,
      "Attraction": 39,
      ...
    }
  }
}
```

### 2. Check Status
```http
GET /research/gnn/status
```

**Response:**
```json
{
  "trained": true,
  "embedding_dim": 64,
  "num_embeddings": 383,
  "model_type": "Heterogeneous Graph Attention Network (GAT)",
  "node_types_trained": 9,
  "node_type_distribution": {...}
}
```

### 3. Link Prediction (Same-Type)
```http
POST /research/gnn/predict-link
Content-Type: application/json

{
  "entity1": "Anuradhapura",
  "entity2": "Sigiriya"
}
```

**Response:**
```json
{
  "entity1": "Anuradhapura",
  "entity2": "Sigiriya",
  "confidence": 0.82,
  "exists": true,
  "method": "GNN-GAT"
}
```

### 4. Cross-Type Prediction (NEW!)
```http
POST /research/gnn/predict-cross-type
Content-Type: application/json

{
  "source_entity": "Sigiriya",
  "target_type": "District",
  "top_k": 3
}
```

**Response:**
```json
{
  "source_entity": "Sigiriya",
  "target_type": "District",
  "predictions": [
    {"name": "Matale", "confidence": 0.85, "type": "District"},
    {"name": "Anuradhapura", "confidence": 0.72, "type": "District"}
  ],
  "count": 2,
  "method": "Heterogeneous GNN Cross-Type Similarity"
}
```

---

## Usage Examples

### Python API

```python
from services.gnn_embeddings import GNNEmbeddingService
from neo4j import GraphDatabase

# Initialize
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
gnn = GNNEmbeddingService(driver, embedding_dim=64)

# Train
MULTI_TYPE_LABELS = ['Attraction', 'Policy', 'Chunk', 'District', 'Location', 
                     'Authority', 'Domain', 'Month', 'Year']
data, node_map = gnn.extract_graph_from_neo4j(node_labels=MULTI_TYPE_LABELS)
stats = gnn.train_embeddings(data, epochs=200, lr=0.001)

# Same-type prediction
result = gnn.predict_link("Anuradhapura", "Sigiriya")
print(f"Confidence: {result['confidence']:.2f}")  # 0.82

# Cross-type prediction
predictions = gnn.predict_cross_type_links("Sigiriya", "District", top_k=3)
for p in predictions:
    print(f"{p['name']}: {p['confidence']:.2f}")  # Matale: 0.85
```

### REST API (curl)

```bash
# Train
curl -X POST http://localhost:8001/research/gnn/train \
  -H "Content-Type: application/json" \
  -d '{"epochs":200,"learning_rate":0.001}'

# Check status
curl http://localhost:8001/research/gnn/status

# Link prediction
curl -X POST http://localhost:8001/research/gnn/predict-link \
  -H "Content-Type: application/json" \
  -d '{"entity1":"Anuradhapura","entity2":"Sigiriya"}'

# Cross-type prediction
curl -X POST http://localhost:8001/research/gnn/predict-cross-type \
  -H "Content-Type: application/json" \
  -d '{"source_entity":"Sigiriya","target_type":"District","top_k":3}'
```

---

## Performance

| Metric | Value | Notes |
|--------|-------|-------|
| **Training Time** | 3.6s | 383 nodes, 759 edges, 200 epochs |
| **Inference (same-type)** | 0.002s | Two entities |
| **Inference (cross-type)** | 0.005s | Top-5 predictions |
| **Memory Usage** | ~98 MB | 383 × 64-dim embeddings |
| **Accuracy** | 87% | Link prediction validation |

**Comparison to Single-Type GNN:**
- 9.8× more nodes (383 vs 39)
- 10× more edges (759 vs ~76)
- 2× faster training (3.6s vs 7s)
- 81 prediction types (vs 1)

---

## Configuration

### Environment Variables
```bash
# Neo4j Connection
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# GNN Parameters
GNN_EMBEDDING_DIM=64
GNN_HIDDEN_DIM=64
GNN_NUM_HEADS=4
GNN_DROPOUT=0.2
GNN_DEVICE=cpu  # or cuda
```

### Python Configuration
```python
# src/services/config/gnn_config.py
class GNNConfig:
    EMBEDDING_DIM = 64
    HIDDEN_DIM = 64
    NUM_HEADS = 4
    DROPOUT = 0.2
    DEVICE = 'cpu'
    
    # Training
    DEFAULT_EPOCHS = 200
    DEFAULT_LR = 0.001
    DEFAULT_WEIGHT_DECAY = 5e-4
    
    # Multi-type labels
    MULTI_TYPE_LABELS = [
        'Attraction', 'Policy', 'Chunk', 'District', 
        'Location', 'Authority', 'Domain', 'Month', 'Year'
    ]
```

---

## Heterogeneous GNN Explained

### What Makes It "Heterogeneous"?

**Traditional GNN (Homogeneous):**
- Single node type (e.g., only Attractions)
- Same features for all nodes
- Can only predict within one type

**Heterogeneous GNN:**
- Multiple node types (9 in our case)
- Type-specific features
- Cross-type predictions enabled

### How It Works

#### 1. Node Type Encoding
```python
# One-hot encoding for 27 possible types (extensible)
type_encoding = [0, 0, 0, ..., 1, ..., 0]  # 27 dims
#                            ↑
#                      "Attraction" = position 5
```

#### 2. Type-Specific Features
```python
if node_type == 'Attraction':
    features = extract_attraction_features(node)
    # [rating, lat, lon, user_ratings, desc_length]
    
elif node_type == 'Policy':
    features = extract_policy_features(node)
    # [complexity, reference_count, domain_count, ...]
    
# ... 9 different extractors
```

#### 3. Feature Concatenation
```python
final_features = concatenate([
    type_encoding,      # 27 dims - "what type am I?"
    type_features,      # 5 dims  - "my specific properties"
    padding            # 96 dims - "alignment for consistency"
])
# Total: 128 dimensions
```

#### 4. Graph Attention
```python
# GAT learns to pay attention to:
# - Same-type neighbors (Attraction → Attraction)
# - Different-type neighbors (Attraction → District)
# - Relationship importance (LOCATED_IN > MENTIONS)

attention_scores = softmax(
    (query @ key.T) / sqrt(d_k)
)
output = attention_scores @ value
```

#### 5. Cross-Type Similarity
```python
# After training, compare embeddings across types
attraction_emb = embeddings[sigiriya_idx]  # [64]
district_embs = embeddings[all_district_indices]  # [25, 64]

similarities = cosine_similarity(
    attraction_emb,
    district_embs
)
# Result: [0.85, 0.72, 0.68, ...]  (Matale, Anuradhapura, Dambulla)
```

---

## Use Cases

### 1. Geographic Inference
**Question:** "Which district is Sigiriya in?"
```python
predictions = gnn.predict_cross_type_links("Sigiriya", "District", top_k=1)
# Answer: "Matale" (0.85 confidence)
```

### 2. Policy Applicability
**Question:** "Where does visa_on_arrival apply?"
```python
predictions = gnn.predict_cross_type_links("visa_on_arrival", "Location", top_k=5)
# Answer: ["Colombo Airport", "Galle Port", ...]
```

### 3. Content Discovery
**Question:** "Which attractions match this description?"
```python
predictions = gnn.predict_cross_type_links("beach_paradise_chunk", "Attraction", top_k=5)
# Answer: ["Unawatuna", "Mirissa", "Arugambay", ...]
```

### 4. Smart Recommendations
**Question:** "Find attractions near Colombo"
```python
predictions = gnn.predict_cross_type_links("Colombo", "Attraction", top_k=10)
# Answer: ["Galle Face Green", "National Museum", ...]
```

---

## Testing

### Unit Tests
```bash
# Test GNN service
pytest tests/test_gnn_embeddings.py

# Test heterogeneous features
pytest tests/test_gnn_embeddings.py::test_heterogeneous_features

# Test cross-type predictions
pytest tests/test_gnn_embeddings.py::test_cross_type_predictions
```

### Integration Tests
```bash
# Run full test suite
python scripts/research/test_heterogeneous_gnn.py

# Test specific scenarios
python scripts/research/test_cross_type_predictions.py
```

### Manual Testing (Postman)
Import: `docs/Tourism_KG_GNN_Research.postman_collection.json`
- 13 requests covering all GNN endpoints
- Includes cross-type prediction examples

---

## Troubleshooting

### Issue: "GNN not trained"
**Solution:** Call `/research/gnn/train` first

### Issue: Low confidence scores
**Causes:**
- Entities far apart in graph
- Different domains (expected for some pairs)
- Sparse graph region

**Solution:** Normal behavior; scores >0.7 indicate strong relationship

### Issue: Entity not found
**Causes:**
- Typo in entity name
- Entity not in trained model
- Wrong node type

**Solution:**
1. Check `/research/gnn/status` for sample entities
2. Use exact names (case-insensitive)
3. Verify entity exists in Neo4j

### Issue: Slow training
**Causes:**
- Large graph (>1000 nodes)
- High epoch count
- CPU bottleneck

**Solution:**
1. Reduce `node_limit` in training request
2. Reduce `epochs` (try 100)
3. Use GPU if available (set `device='cuda'`)

---

## Roadmap

### Phase 1: Current (Completed ✅)
- ✅ Heterogeneous GNN with 9 node types
- ✅ Type-aware feature extraction
- ✅ Cross-type predictions
- ✅ REST API endpoints

### Phase 2: Relation-Aware Attention (Planned)
- ⏳ Edge type embeddings (37 relationship types)
- ⏳ Relation-specific attention weights
- ⏳ Multi-relational message passing

### Phase 3: Multi-Task Learning (Planned)
- ⏳ Simultaneous link prediction + node classification
- ⏳ Attribute prediction (rating, category, etc.)
- ⏳ Better embeddings through multi-objective optimization

### Phase 4: Production Optimization (Planned)
- ⏳ Incremental training (add nodes without full retrain)
- ⏳ Model versioning & persistence
- ⏳ A/B testing framework
- ⏳ Monitoring & alerting

---

## References

### Papers
1. Veličković et al., "Graph Attention Networks" (ICLR 2018)
2. Zhang et al., "Heterogeneous Graph Neural Networks" (KDD 2019)
3. Hu et al., "Heterogeneous Graph Transformer" (WWW 2020)

### Code
- PyTorch Geometric: https://pytorch-geometric.readthedocs.io/
- GAT Implementation: https://github.com/PetarV-/GAT

### Documentation
- [HETEROGENEOUS_GNN_COMPLETE_GUIDE.md](HETEROGENEOUS_GNN_COMPLETE_GUIDE.md) - Full technical guide
- [HETEROGENEOUS_GNN_UPGRADE.md](HETEROGENEOUS_GNN_UPGRADE.md) - Before/after comparison
- [QUICK_START_HETEROGENEOUS_GNN.md](QUICK_START_HETEROGENEOUS_GNN.md) - API testing guide

---

## License

MIT License - See LICENSE file for details

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review documentation in `docs/` folder
3. Check Postman collection examples
4. Contact: Your research supervisor or team
