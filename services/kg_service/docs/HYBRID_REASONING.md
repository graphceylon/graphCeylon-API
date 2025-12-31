# 🧠 Hybrid Reasoning System with GNN Embeddings

## Overview

This implementation provides a **state-of-the-art hybrid reasoning system** for the Sri Lankan Tourism Knowledge Graph, combining:

1. **Symbolic Reasoning** - Deterministic Cypher queries for rule-based inference
2. **Neural Reasoning** - Graph Neural Networks (GNN) for pattern learning and predictions
3. **Temporal Reasoning** - Time-aware entity validity and seasonal availability
4. **Provenance Tracking** - Full data lineage with confidence scores
5. **Explainability** - Evidence trails and reasoning chains

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Agent Interface Layer (AIL)                │
│  ┌──────────┬──────────┬──────────┬──────────┬───────────┐ │
│  │  Query   │  Reason  │  Write   │Subscribe │  Explain  │ │
│  └──────────┴──────────┴──────────┴──────────┴───────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Hybrid Reasoning Engine                         │
│  ┌──────────────────────┬────────────────────────────────┐ │
│  │ Symbolic Reasoning   │  Neural Reasoning (GNN)        │ │
│  │ - Cypher queries     │  - Graph Attention Networks    │ │
│  │ - Multi-hop paths    │  - Link prediction             │ │
│  │ - Constraint checks  │  - Entity similarity           │ │
│  │ - Temporal validity  │  - Knowledge completion        │ │
│  └──────────────────────┴────────────────────────────────┘ │
│                Confidence Scoring & Explanation              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Neo4j Knowledge Graph                     │
│        Entities + Relationships + Temporal + Provenance      │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 New Components

### 1. **Temporal & Provenance Models** (`models/temporal.py`)

Enhanced data models for tracking:
- **Temporal validity**: `valid_from`, `valid_to`, seasonal availability
- **Provenance**: source, confidence, verification status, license

```python
from models.temporal import TemporalMetadata, ProvenanceMetadata

temporal = TemporalMetadata(
    valid_from=datetime(2026, 1, 1),
    valid_to=None,  # Still valid
    seasonal_availability=["Nov-Mar", "closed-during-monsoon"]
)

provenance = ProvenanceMetadata(
    source="SLTDA Official Database",
    source_url="https://sltda.gov.lk/...",
    confidence=0.95,
    verified=True
)
```

### 2. **GNN Embeddings** (`services/gnn_embeddings.py`)

Graph Neural Network implementation using PyTorch Geometric:

- **Architecture**: 3-layer Graph Attention Network (GAT)
- **Training**: Link prediction as objective
- **Features**:
  - Entity embeddings from graph structure
  - Link prediction for missing relationships
  - Similarity search

```python
from services.gnn_embeddings import GNNEmbeddingService

gnn_service = GNNEmbeddingService(driver, embedding_dim=32)

# Extract graph from Neo4j
data, node_map = gnn_service.extract_graph_from_neo4j(
    node_labels=["Attraction", "District", "Province"],
    limit=10000
)

# Train embeddings
stats = gnn_service.train_embeddings(data, epochs=100)

# Predict missing link
prediction = gnn_service.predict_link(entity1_id, entity2_id)
# {'exists': True, 'confidence': 0.87}

# Find similar entities
similar = gnn_service.find_similar_entities(entity_id, top_k=5)
```

### 3. **Hybrid Reasoning Engine** (`services/hybrid_reasoning.py`)

Combines symbolic and neural reasoning with explainability:

```python
from services.hybrid_reasoning import HybridReasoningEngine

reasoner = HybridReasoningEngine(
    driver,
    gnn_service,
    symbolic_weight=0.6,
    neural_weight=0.4
)

# Multi-domain itinerary planning
result = reasoner.reason_itinerary(
    start_location="Colombo",
    end_location="Sigiriya",
    constraints={
        "budget": 50000,
        "interests": ["history", "nature"],
        "min_rating": 4.0
    },
    query_date=datetime(2026, 2, 15)
)

# Returns:
{
    "itinerary": [...],
    "overall_confidence": 0.85,
    "explanation": {
        "chain": [
            {"step": 1, "method": "symbolic_path_finding", "confidence": 1.0},
            {"step": 2, "method": "neural_similarity", "confidence": 0.82},
            {"step": 3, "method": "temporal_validation", "confidence": 1.0}
        ]
    }
}
```

### 4. **Enhanced Agent Interface Layer** (`api/ail_enhanced.py`)

Complete AIL with all 5 endpoints:

#### **POST /ail/query** - Query with temporal filtering
```json
{
  "entity_type": "Attraction",
  "query_date": "2026-02-15T00:00:00Z",
  "filters": {"min_rating": 4.0},
  "limit": 10
}
```

#### **POST /ail/reason** - Hybrid reasoning
```json
{
  "start_location": "Colombo",
  "end_location": "Sigiriya",
  "query_date": "2026-02-15T00:00:00Z",
  "constraints": {
    "budget": 50000,
    "interests": ["history"],
    "min_rating": 4.0
  },
  "reasoning_mode": "hybrid"
}
```

#### **POST /ail/write** - Write with provenance
```json
{
  "entity_type": "Attraction",
  "operation": "create",
  "data": {
    "title": "New Beach",
    "description": "Beautiful beach"
  },
  "provenance": {
    "source": "User Input",
    "confidence": 0.8,
    "verified": false
  },
  "temporal": {
    "valid_from": "2026-01-01T00:00:00Z",
    "seasonal_availability": ["Nov-Apr"]
  }
}
```

#### **POST /ail/validate** - SHACL validation
```json
{
  "entity_type": "Attraction"
}
```

#### **POST /ail/explain** - Get explanations
```json
{
  "entity_id": "123",
  "include_provenance": true,
  "include_temporal": true
}
```

#### **WS /ail/subscribe** - Real-time updates
```javascript
const ws = new WebSocket('ws://localhost:8000/ail/subscribe?entity_types=Attraction,Hotel');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Entity changed:', update);
};
```

#### **POST /ail/predict-link** - Link prediction
```json
{
  "entity1_name": "Sigiriya",
  "entity2_name": "Anuradhapura",
  "relationship_type": "NEAR"
}
```

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
cd services/kg_service
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# .env file
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### 3. Initialize and Train GNN

```python
# In Python shell or notebook
from neo4j import GraphDatabase
from services.gnn_embeddings import GNNEmbeddingService

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
gnn_service = GNNEmbeddingService(driver, embedding_dim=32)

# Extract graph
data, node_map = gnn_service.extract_graph_from_neo4j(limit=10000)

# Train for 100 epochs
stats = gnn_service.train_embeddings(data, epochs=100)
print(stats)
```

### 4. Start the API

```bash
cd services/kg_service/src
python main.py
```

API will be available at `http://localhost:8000`

### 5. Test Endpoints

```bash
# Query with temporal filtering
curl -X POST http://localhost:8000/ail/query \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "Attraction",
    "query_date": "2026-02-15T00:00:00Z",
    "limit": 5
  }'

# Hybrid reasoning
curl -X POST http://localhost:8000/ail/reason \
  -H "Content-Type: application/json" \
  -d '{
    "start_location": "Colombo",
    "end_location": "Sigiriya",
    "constraints": {"interests": ["history"]}
  }'
```

---

## 📊 Research Contributions

### **Novel Aspects:**

1. **First Sri Lanka-specific tourism KG** with hybrid reasoning
2. **Temporal-aware GNN embeddings** for seasonal tourism
3. **Explainable hybrid reasoning** combining symbolic + neural
4. **Comprehensive provenance tracking** with confidence scores
5. **Real-time knowledge graph updates** via WebSocket subscriptions

### **Evaluation Metrics:**

- **Link Prediction Accuracy**: Test on held-out edges
- **Path Finding Quality**: Compare symbolic vs hybrid
- **Temporal Reasoning Accuracy**: Validate date-based queries
- **Explanation Quality**: User study on explanation clarity
- **Confidence Calibration**: Correlation between confidence and correctness

---

## 📖 Usage Examples

### Example 1: Find Itinerary with Temporal Constraints

```python
result = reasoner.reason_itinerary(
    start_location="Colombo",
    end_location="Ella",
    constraints={
        "budget": 75000,
        "interests": ["nature", "hiking"],
        "min_rating": 4.5,
        "max_time_hours": 48
    },
    query_date=datetime(2026, 3, 15)
)

print(f"Confidence: {result['overall_confidence']:.2f}")
print(f"Found {len(result['itinerary'])} attractions")

for step in result['explanation']['chain']:
    print(f"Step {step['step']}: {step['method']} (conf: {step['confidence']:.2f})")
```

### Example 2: Predict Missing Relationships

```python
# Is there a NEAR relationship between Sigiriya and Dambulla?
prediction = reasoner.predict_missing_relationship(
    entity1_name="Sigiriya",
    entity2_name="Dambulla Cave Temple",
    relationship_type="NEAR"
)

print(f"Relationship exists: {prediction['exists']}")
print(f"Confidence: {prediction['confidence']:.2f}")
print(f"Method: {prediction['explanation']['method']}")
```

### Example 3: Write Entity with Full Provenance

```python
from models.temporal import TemporalMetadata, ProvenanceMetadata
from datetime import datetime

# Create new attraction with metadata
await write_entity(WriteRequest(
    entity_type="Attraction",
    operation="create",
    data={
        "title": "Hidden Waterfall",
        "description": "Secluded waterfall in Sinharaja",
        "rating": 4.8
    },
    provenance=ProvenanceMetadata(
        source="Field Survey 2025",
        source_url="https://example.com/survey",
        confidence=0.92,
        verified=True,
        verified_by="researcher_001",
        license="CC-BY-SA-4.0"
    ),
    temporal=TemporalMetadata(
        valid_from=datetime(2025, 1, 1),
        seasonal_availability=["Nov-Apr"],
        closure_dates=["2026-03-15"]
    )
))
```

---

## 🎯 Next Steps

### Immediate (Week 1-2):
- ✅ Test GNN training on full KG
- ✅ Evaluate link prediction accuracy
- ✅ Benchmark hybrid reasoning performance

### Short-term (Week 3-4):
- 🔄 Add more entity types to GNN training
- 🔄 Implement temporal GNN embeddings
- 🔄 Add constraint optimization with multi-objective

### Medium-term (Month 2):
- 📋 Integrate with Flutter mobile app
- 📋 User study for explainability evaluation
- 📋 Performance optimization (caching, indexing)

### Long-term (Month 3+):
- 📋 RL-based multi-hop reasoning agent
- 📋 Knowledge graph completion pipeline
- 📋 Real-time CDC from Neo4j

---

## 📚 References

### Key Papers:
1. **GAT**: Veličković et al. "Graph Attention Networks" (ICLR 2018)
2. **PyTorch Geometric**: Fey & Lenssen (2019)
3. **Knowledge Graph Embeddings**: Wang et al. "Knowledge Graph Embedding: A Survey" (2017)
4. **Temporal KGs**: Dasgupta et al. "HyTE: Hyperplane-based Temporally aware KG Embedding" (2018)

---

## 🐛 Troubleshooting

### Issue: GNN training OOM
**Solution**: Reduce batch size or use mini-batch training
```python
data, node_map = gnn_service.extract_graph_from_neo4j(limit=5000)
```

### Issue: Neo4j connection timeout
**Solution**: Increase connection pool size
```python
driver = GraphDatabase.driver(uri, auth=auth, max_connection_pool_size=50)
```

### Issue: Slow reasoning queries
**Solution**: Create Neo4j indexes
```cypher
CREATE INDEX attraction_name FOR (n:Attraction) ON (n.name);
CREATE INDEX district_name FOR (n:District) ON (n.name);
```

---

## 📞 Contact

For questions or issues, please create an issue in the repository or contact the research team.

**Research Team**: SLIIT Final Year Data Science Project 2025
**Project**: Multilingual Multimodal Tourism Agent for Sri Lanka
