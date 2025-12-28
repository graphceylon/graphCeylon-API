# Knowledge Graph Service - Complete Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [API Endpoints](#api-endpoints)
5. [Services Layer](#services-layer)
6. [Database Layer](#database-layer)
7. [Models & Schemas](#models--schemas)
8. [Data Flow](#data-flow)
9. [Configuration](#configuration)
10. [Usage Examples](#usage-examples)

---

## Overview

The Knowledge Graph (KG) Service is a **FastAPI-based microservice** that manages a comprehensive knowledge graph for **Sri Lankan Tourism** using **Neo4j** as the graph database. It provides semantic search, reasoning capabilities, vector embeddings, and GraphRAG (Retrieval-Augmented Generation) features.

### Key Features
- **12-Domain Tourism Architecture**: Organized knowledge graph with structured domains
- **Geographic Hierarchy**: Country → Province → District → Attractions
- **Temporal Structure**: Year → Month → Holidays
- **Vector Search**: Semantic similarity using embeddings
- **GraphRAG**: Entity extraction and RAG-based querying
- **Reasoning Engine**: Symbolic and constraint-based reasoning
- **Real-time CRUD Operations**: Create, read, update, delete tourism entities
- **Multi-LLM Support**: OpenAI and Groq integration

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Application                    │
│                     (main.py)                            │
└──────────────┬──────────────────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────┐         ┌──────▼──────┐
│  API   │         │   Services   │
│ Router │         │    Layer     │
│ Layer  │         └──────┬───────┘
└───┬────┘                │
    │              ┌──────┴─────────────────┐
    │              │                         │
    │        ┌─────▼──────┐         ┌───────▼────────┐
    │        │  Reasoning │         │   Embeddings   │
    │        │ Orchestrator│        │    Service     │
    │        └─────┬──────┘         └───────┬────────┘
    │              │                         │
    │        ┌─────▼─────┐          ┌───────▼────────┐
    │        │  GraphRAG │          │  LLM Factory   │
    │        │  Service  │          │   (OpenAI/     │
    │        └─────┬─────┘          │    Groq)       │
    │              │                └────────────────┘
┌───▼──────────────▼────────────────────────────────┐
│              Database Layer                        │
│           (DatabaseManager)                        │
└───────────────────┬────────────────────────────────┘
                    │
        ┌───────────┴───────────────────┐
        │                               │
┌───────▼──────┐            ┌───────────▼──────────┐
│ Repositories │            │    Neo4j Driver      │
│   (Domain    │            │   (bolt://...)       │
│  Specific)   │            └──────────────────────┘
└──────────────┘
```

### Layer Responsibilities

1. **API Layer**: HTTP endpoints, request/response handling, validation
2. **Services Layer**: Business logic, reasoning, embeddings, GraphRAG
3. **Database Layer**: Data access, repository pattern, Cypher execution
4. **Neo4j**: Graph database storage and querying

---

## Core Components

### 1. Main Application ([main.py](../src/main.py))

**Purpose**: FastAPI application initialization and lifecycle management

**Key Features**:
- Lifespan management (startup/shutdown)
- CORS configuration
- Dependency injection
- Router registration
- Global exception handling

**Startup Flow**:
```
1. Create Neo4j driver
2. Initialize DatabaseManager
3. Initialize ReasoningOrchestrator
4. Test database connection
5. Register all routers
6. Start Uvicorn server
```

**Registered Routers**:
- `/attractions` - Attraction management
- `/domains` - Domain architecture
- `/holidays` - Holiday & temporal data
- `/projects` - Tourism projects
- `/news` - Tourism news
- `/semantic` - Semantic web operations
- `/agent` - Agent interface
- `/graphrag` - GraphRAG operations
- `/kg/*` - Core KG operations

---

## API Endpoints

### Core Knowledge Graph Endpoints

#### `GET /health`
**Purpose**: Health check endpoint

**Response**:
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

#### `POST /kg/initialize`
**Purpose**: Initialize database with ontology, shapes, and seed data

**Response**:
```json
{
  "message": "Database initialized successfully",
  "results": {...}
}
```

---

#### `GET /kg/statistics`
**Purpose**: Get comprehensive database statistics

**Response**:
```json
{
  "statistics": {
    "node_count": 1500,
    "relationship_count": 3200,
    "node_labels": {
      "Attraction": 450,
      "District": 25,
      "Province": 9,
      "Holiday": 150
    },
    "relationship_types": {
      "LOCATED_IN": 450,
      "HAS_DISTRICT": 25
    }
  }
}
```

---

#### `POST /kg/query`
**Purpose**: Execute Cypher queries or structured queries

**Request Body**:
```json
{
  "query": "MATCH (p:Province) RETURN p.name LIMIT 10",
  "province": "Western",  // Optional
  "district": "Colombo"   // Optional
}
```

**Response**:
```json
{
  "data": [...],
  "execution_time": 45.2,
  "provenance": {
    "query_type": "raw_cypher",
    "timestamp": "2025-12-19T19:00:00"
  }
}
```

---

#### `POST /kg/reason`
**Purpose**: Perform symbolic or constraint-based reasoning

**Request Body**:
```json
{
  "start_province": "Western",
  "target_district": "Colombo",
  "constraints": {
    "min_districts": 5
  }
}
```

**Response**:
```json
{
  "feasible": true,
  "explanations": [{
    "rule": "multi-hop-shortestPath",
    "path_nodes": [...],
    "path_rels": ["HAS_DISTRICT"],
    "evidence_count": 2
  }],
  "result": {...},
  "provenance": {
    "method": "symbolic",
    "timestamp": "2025-12-19T19:00:00"
  }
}
```

---

### Attractions API ([attractions.py](../src/api/attractions.py))

#### `GET /attractions`
**Purpose**: Get all attractions with pagination

**Parameters**:
- `limit` (int): Maximum number of results (default: 20)

**Response**:
```json
{
  "attractions": [
    {
      "title": "Sigiriya Rock Fortress",
      "description": "Ancient rock fortress...",
      "rating": 4.8,
      "district": "Matale",
      "latitude": 7.9570,
      "longitude": 80.7597
    }
  ],
  "count": 450,
  "query_info": {"limit": 20}
}
```

---

#### `GET /attractions/districts`
**Purpose**: Get all districts that have attractions

**Response**:
```json
{
  "districts": [
    {"district": "Colombo", "attraction_count": 45},
    {"district": "Kandy", "attraction_count": 38}
  ],
  "count": 25
}
```

---

#### `POST /attractions/initialize`
**Purpose**: Initialize attractions schema and load data from JSON

**Process**:
1. Cleanup existing relationships
2. Load attraction schema (constraints/indexes)
3. Load attractions from JSON file
4. Link to districts and provinces
5. Link to "Destination & Attraction" domain

**Response**:
```json
{
  "success": true,
  "cleanup": {...},
  "schema": {...},
  "data": {
    "attractions_loaded": 450,
    "relationships_created": 900
  },
  "message": "Attractions initialized successfully"
}
```

---

#### `POST /attractions/vector-index/create`
**Purpose**: Create vector index for semantic search

**Technical Details**:
- Index name: `attraction_embeddings`
- Vector dimensions: 384 (all-MiniLM-L6-v2)
- Similarity function: cosine

---

#### `POST /attractions/embeddings/update`
**Purpose**: Generate and update embeddings for attractions

**Process**:
1. Find attractions without embeddings
2. Generate embeddings using SentenceTransformer
3. Update Neo4j nodes with embedding vectors

---

#### `POST /attractions`
**Purpose**: Create a new attraction

**Request Body**:
```json
{
  "title": "New Beach Resort",
  "description": "Beautiful coastal resort...",
  "district": "Galle",
  "latitude": 6.0535,
  "longitude": 80.2210,
  "rating": 4.5,
  "image_url": "https://...",
  "google_place_id": "ChIJ..."
}
```

---

### Domains API ([domains.py](../src/api/domains.py))

#### `POST /domains/initialize`
**Purpose**: Initialize 12-domain architecture

**Created Domains**:
1. **Destination & Attraction** - Tourist sites, landmarks
2. **Accommodation** - Hotels, resorts, guesthouses
3. **Transportation** - Airlines, buses, trains
4. **Events & Activities** - Festivals, tours, sports
5. **Culinary** - Restaurants, food experiences
6. **Culture & Heritage** - Museums, temples, traditions
7. **Nature & Wildlife** - National parks, sanctuaries
8. **Economic & Policy** - Tourism statistics, policies
9. **Marketing & Promotion** - Campaigns, branding
10. **Temporal** - Seasons, holidays, events calendar
11. **Safety & Healthcare** - Hospitals, safety info
12. **Technology & Infrastructure** - Smart tourism tech

**Response**:
```json
{
  "success": true,
  "message": "Domain-driven architecture initialized",
  "summary": {
    "country": "Sri Lanka",
    "total_domains": 12,
    "domains": [
      {
        "name": "Destination & Attraction",
        "code": "DA",
        "status": "active",
        "order": 1
      }
    ]
  }
}
```

---

#### `GET /domains/overview`
**Purpose**: Get overview of all domains with entity counts

**Response**:
```json
{
  "domains": [
    {
      "name": "Destination & Attraction",
      "code": "DA",
      "entity_count": 450,
      "description": "Tourist destinations...",
      "examples": ["Sigiriya", "Temple of Tooth"]
    }
  ]
}
```

---

#### `GET /domains/{domain_name}/entities`
**Purpose**: Get all entities in a specific domain

**Parameters**:
- `domain_name` (str): Domain name
- `limit` (int): Max results (default: 100)

---

#### `GET /domains/structure`
**Purpose**: Get complete hierarchical structure

**Response**:
```json
{
  "country": "Sri Lanka",
  "domain_count": 12,
  "province_count": 9,
  "district_count": 25,
  "attraction_count": 450,
  "hierarchy": {
    "domains": [...],
    "provinces": [...],
    "districts": [...]
  }
}
```

---

#### `POST /domains/cleanup-duplicates`
**Purpose**: Remove duplicate relationships

---

### Holidays API ([holidays.py](../src/api/holidays.py))

#### `POST /holidays/initialize-temporal`
**Purpose**: Initialize temporal structure (Year → Month)

**Creates**:
- Year nodes (2024, 2025, 2026, ...)
- Month nodes for each year (January-December)
- Relationships to Temporal domain
- Indexes for performance

**Response**:
```json
{
  "years_created": 3,
  "months_created": 36,
  "relationships_created": 39
}
```

---

#### `POST /holidays/load`
**Purpose**: Load holidays from JSON and link to temporal structure

**Process**:
1. Read holidays.json
2. Create Holiday nodes
3. Link to Year nodes
4. Link to Month nodes
5. Create category relationships
6. Link to Temporal domain

**Response**:
```json
{
  "holidays_loaded": 150,
  "categories": ["Religious", "Cultural", "National", "General"],
  "years_covered": [2024, 2025, 2026]
}
```

---

#### `POST /holidays/query`
**Purpose**: Query holidays with filters

**Request Body**:
```json
{
  "year": 2025,
  "month": 12,
  "category": "Religious",
  "holiday_type": "Poya Day",
  "is_public_holiday": true,
  "name": "Vesak",
  "limit": 50
}
```

**Response**:
```json
{
  "holidays": [
    {
      "name": "Vesak Full Moon Poya Day",
      "date": "2025-05-12",
      "category": "Religious",
      "holiday_type": "Poya Day",
      "is_public_holiday": true,
      "description": "..."
    }
  ],
  "count": 1,
  "query_info": {
    "filters_applied": {"category": "Religious"},
    "limit": 50
  }
}
```

---

#### `GET /holidays/year/{year}`
**Purpose**: Get all holidays for a specific year

---

#### `GET /holidays/year/{year}/month/{month}`
**Purpose**: Get holidays for specific year and month

---

#### `GET /holidays/category/{category}`
**Purpose**: Get holidays by category

**Categories**:
- Religious
- Cultural
- National
- General

---

#### `GET /holidays/statistics/overview`
**Purpose**: Get comprehensive holiday statistics

**Response**:
```json
{
  "total_holidays": 150,
  "by_category": [
    {"category": "Religious", "count": 60},
    {"category": "Cultural", "count": 40},
    {"category": "National", "count": 30},
    {"category": "General", "count": 20}
  ],
  "by_year": [
    {"year": 2025, "count": 50}
  ],
  "public_holidays": 25
}
```

---

### Projects API ([projects.py](../src/api/projects.py))

#### `GET /projects`
**Purpose**: Get all tourism projects

---

#### `POST /projects/query`
**Purpose**: Query projects with filters

**Request Body**:
```json
{
  "title": "Resort",
  "province": "Southern",
  "district": "Galle",
  "project_type": "Hotel Development",
  "limit": 20
}
```

---

#### `GET /projects/types`
**Purpose**: Get all project types with counts

---

#### `GET /projects/provinces`
**Purpose**: Get provinces with project counts

---

#### `GET /projects/districts`
**Purpose**: Get districts with project counts

---

#### `POST /projects/initialize`
**Purpose**: Initialize projects schema and load from JSON

---

#### `POST /projects`
**Purpose**: Create new tourism project

---

#### `GET /projects/{project_id}`
**Purpose**: Get specific project by ID

---

#### `GET /projects/statistics/overview`
**Purpose**: Get project statistics

**Response**:
```json
{
  "total_projects": 120,
  "by_type": [
    {"type": "Hotel Development", "count": 45},
    {"type": "Infrastructure", "count": 30}
  ],
  "by_province": [
    {"province": "Western", "count": 35},
    {"province": "Southern", "count": 25}
  ]
}
```

---

### News API ([news.py](../src/api/news.py))

#### `GET /news`
**Purpose**: Get all news articles

---

#### `POST /news/query`
**Purpose**: Query news with filters

**Request Body**:
```json
{
  "title": "tourism",
  "category": "Industry Updates",
  "date_from": "2024-01-01",
  "date_to": "2024-12-31",
  "year": 2024,
  "month": 12,
  "limit": 20
}
```

---

#### `GET /news/categories`
**Purpose**: Get all news categories with counts

---

#### `GET /news/year/{year}`
**Purpose**: Get news for specific year

---

#### `GET /news/month/{year}/{month}`
**Purpose**: Get news for specific month

---

#### `GET /news/recent`
**Purpose**: Get recent news sorted by date

---

#### `POST /news/initialize`
**Purpose**: Initialize news schema and load from JSON

---

#### `POST /news`
**Purpose**: Create new news article

---

#### `GET /news/statistics/overview`
**Purpose**: Get news statistics

**Response**:
```json
{
  "total_articles": 200,
  "by_category": [
    {"category": "Industry Updates", "count": 80},
    {"category": "Destination News", "count": 60}
  ],
  "by_year": [
    {"year": 2024, "count": 100},
    {"year": 2023, "count": 100}
  ]
}
```

---

### Agent API ([agent.py](../src/api/agent.py))

#### `POST /agent/search`
**Purpose**: Semantic search for agents using vector reasoning

**Request Body**:
```json
{
  "query": "ancient temples in central Sri Lanka",
  "limit": 5,
  "filters": {"rating": 4.5}
}
```

**Response**:
```json
{
  "result": [
    {
      "title": "Temple of the Tooth",
      "description": "...",
      "score": 0.92
    }
  ],
  "explanation": {
    "method": "cosine-similarity-vector-search",
    "query": "ancient temples...",
    "results_found": 5
  }
}
```

---

#### `POST /agent/plan`
**Purpose**: Path planning and validation for agents

**Request Body**:
```json
{
  "intent": "travel_route",
  "waypoints": ["Colombo", "Kandy"],
  "constraints": {"max_distance": 100}
}
```

---

#### `GET /agent/explain/{entity_id}`
**Purpose**: Get provenance and context for an entity

**Response**:
```json
{
  "entity": {
    "name": "Sigiriya",
    "title": "Sigiriya Rock Fortress"
  },
  "context": [
    {"rel": "LOCATED_IN", "node": "Matale", "label": "District"}
  ],
  "provenance": "Sri Lanka Tourism Knowledge Graph v2.0"
}
```

---

### GraphRAG API ([graphrag.py](../src/api/graphrag.py))

#### `POST /graphrag/ingest`
**Purpose**: Ingest data with entity extraction

**Request Body**:
```json
{
  "data_dir": "data/immigration",
  "domain_name": "Economic & Policy"
}
```

**Process**:
1. Read JSON files from directory
2. Split text into chunks
3. Extract entities using LLM
4. Generate embeddings
5. Store in Neo4j
6. Link to domain

**Response**:
```json
{
  "success": true,
  "statistics": {
    "files_processed": 10,
    "chunks_created": 250,
    "entities_extracted": 450,
    "relationships_created": 680
  },
  "message": "Successfully ingested 10 files"
}
```

---

#### `POST /graphrag/query`
**Purpose**: RAG-based querying with LLM

**Request Body**:
```json
{
  "question": "What are the visa requirements for tourists?",
  "top_k": 5,
  "domain_name": "Economic & Policy"
}
```

**Process**:
1. Generate query embedding
2. Vector similarity search for relevant chunks
3. Retrieve connected entities
4. Generate answer using LLM

**Response**:
```json
{
  "answer": "Tourist visas for Sri Lanka...",
  "context": [
    {
      "chunk_text": "Visa requirements...",
      "score": 0.89
    }
  ],
  "metadata": {
    "model": "gpt-4o-mini",
    "chunks_used": 3,
    "entities_found": 5
  }
}
```

---

#### `POST /graphrag/ensure-index`
**Purpose**: Ensure vector index exists for GraphRAG

---

#### `GET /graphrag/statistics`
**Purpose**: Get GraphRAG statistics

**Response**:
```json
{
  "chunk_count": 250,
  "entity_types": [
    {"type": "Policy", "count": 50},
    {"type": "Statistic", "count": 100}
  ],
  "relationship_types": [
    {"type": "RELATES_TO", "count": 200}
  ]
}
```

---

## Services Layer

### 1. Reasoning Orchestrator ([reasoning.py](../src/services/reasoning.py))

**Purpose**: Provides symbolic and predictive reasoning capabilities

#### Methods:

##### `symbolic_reason(start: str, end: str)`
**Purpose**: Find shortest path between entities

**Algorithm**:
```cypher
MATCH path=shortestPath(
  (p:Province {name:$start})-[*..4]-(t:District {name:$end})
)
RETURN nodes(path), relationships(path)
```

**Use Cases**:
- Path finding between provinces and districts
- Relationship validation
- Multi-hop reasoning

---

##### `constraint_reason(constraints: Dict)`
**Purpose**: Filter entities based on constraints

**Supported Constraints**:
- `province`: Filter by province name
- `district_pattern`: Regex pattern for districts
- `min_districts`: Minimum district count
- `max_districts`: Maximum district count

**Example**:
```python
constraints = {
    "province": "Western",
    "min_districts": 5
}
result = orchestrator.constraint_reason(constraints)
```

---

##### `vector_reason_similar(query: str, top_k: int)`
**Purpose**: Semantic similarity search using embeddings

**Process**:
1. Generate embedding for query
2. Execute vector similarity search in Neo4j
3. Return top-k similar entities

**Technical**:
- Uses `db.index.vector.queryNodes`
- Cosine similarity
- Returns entities with similarity scores

---

##### `predictive_reason_similar(name: str, node_label: str, top_k: int)`
**Purpose**: Find similar entities using string similarity (fallback)

**Algorithm**: difflib.SequenceMatcher

---

##### `shacl_validate()`
**Purpose**: Validate graph against SHACL shapes

**Process**:
1. Run n10s SHACL validation
2. Collect violations
3. Return conformance report

---

### 2. Embedding Service ([embeddings.py](../src/services/embeddings.py))

**Purpose**: Generate text embeddings for semantic search

**Model**: SentenceTransformer (all-MiniLM-L6-v2)
**Dimensions**: 384
**Pattern**: Singleton

#### Methods:

##### `generate_embedding(text: str) -> List[float]`
**Purpose**: Generate embedding for single text

**Usage**:
```python
from services.embeddings import embedding_service

embedding = embedding_service.generate_embedding(
    "Beautiful beach resort in Galle"
)
# Returns: [0.123, -0.456, 0.789, ...]  # 384 dimensions
```

---

##### `generate_embeddings(texts: List[str]) -> List[List[float]]`
**Purpose**: Batch generate embeddings for multiple texts

---

### 3. GraphRAG Service ([graphrag/service.py](../src/services/graphrag/service.py))

**Purpose**: Coordinate GraphRAG operations

**Components**:
- VectorIndexer
- EntityExtractor
- ChunkProcessor
- DataIngestionService
- RAGQueryEngine

#### Methods:

##### `ensure_vector_index()`
**Purpose**: Create vector index if not exists

---

##### `ingest_immigration_data(data_dir, domain_name)`
**Purpose**: Ingest and process data files

**Process**:
1. Read files from directory
2. Process with ChunkProcessor
3. Extract entities with EntityExtractor
4. Generate embeddings
5. Store in Neo4j
6. Link to domain

---

##### `query(question, domain_name, top_k)`
**Purpose**: Execute RAG query

**Process**:
1. Generate query embedding
2. Vector search for relevant chunks
3. Retrieve context from graph
4. Generate answer with LLM

---

##### `get_statistics(domain_name)`
**Purpose**: Get ingestion statistics

---

### 4. LLM Factory ([services/llm/factory.py](../src/services/llm/factory.py))

**Purpose**: Abstract LLM provider management

**Supported Providers**:
- OpenAI (GPT-4o-mini, GPT-4, GPT-3.5-turbo)
- Groq (Llama-3.3-70b-versatile, Mixtral, etc.)

**Configuration**:
```python
# In settings
ingestion_llm_provider = "openai"
ingestion_llm_model = "gpt-4o-mini"
query_llm_provider = "groq"
query_llm_model = "llama-3.3-70b-versatile"
```

**Usage**:
```python
from services.llm import LLMFactory, LLMConfig

config = LLMConfig(
    provider="openai",
    model="gpt-4o-mini",
    temperature=0
)

llm = LLMFactory.create_llm(config)
response = llm.generate("What is Sri Lanka?")
```

---

## Database Layer

### DatabaseManager ([database/manager.py](../src/database/manager.py))

**Purpose**: Unified database access layer delegating to repositories

**Pattern**: Facade + Repository Pattern

**Repositories**:
- `AttractionRepository` - Attraction operations
- `HolidayRepository` - Holiday & temporal operations
- `ProjectRepository` - Project operations
- `NewsRepository` - News operations
- `OntologyRepository` - Ontology & domain operations
- `BaseRepository` - Common operations

#### Key Methods:

##### Common Operations
- `execute_cypher(query, params)` - Execute raw Cypher
- `execute_cypher_file(path)` - Execute from file
- `get_statistics()` - Get database stats

##### Initialization
- `initialize_database()` - Full initialization
- `initialize_domain_structure()` - Create 12 domains
- `initialize_temporal_structure()` - Create Year/Month hierarchy

##### Vector Operations
- `create_vector_index()` - Create vector index
- `update_embeddings()` - Generate and store embeddings

##### Attraction Operations
- `load_attractions_schema()` - Load constraints/indexes
- `load_attractions_from_json()` - Bulk load attractions
- `create_attraction(data)` - Create single attraction
- `query_attractions(filters)` - Query with filters
- `get_attractions_by_district(district)` - Get by location
- `cleanup_attractions()` - Remove relationships

##### Holiday Operations
- `load_holidays_from_json()` - Load holidays
- `query_holidays(filters)` - Query with filters
- `get_holidays_by_year(year)` - Get by year
- `get_holidays_by_category(category)` - Get by category
- `get_holiday_statistics()` - Get stats
- `create_holiday(data)` - Create holiday
- `search_holidays(query)` - Text search

##### Project Operations
- `load_projects_from_json()` - Load projects
- `query_projects(filters)` - Query with filters
- `create_project(data)` - Create project
- `get_project_statistics()` - Get stats

##### News Operations
- `load_news_from_json()` - Load news
- `query_news(filters)` - Query with filters
- `create_news_article(data)` - Create article
- `get_news_statistics()` - Get stats

---

### Repository Pattern

Each repository inherits from `BaseRepository` and implements domain-specific logic.

#### BaseRepository ([database/repositories/base.py](../src/database/repositories/base.py))

**Common Methods**:
- `execute_query(cypher, params)` - Execute Cypher
- `execute_cypher_file(path)` - Execute file
- `get_statistics()` - Database statistics
- `create_constraint(label, property)` - Create constraint
- `create_index(label, property)` - Create index

---

#### AttractionRepository ([database/repositories/attraction_repository.py](../src/database/repositories/attraction_repository.py))

**Specialized Methods**:
- `load_schema()` - Create constraints and indexes
- `load_from_json()` - Bulk load with APOC
- `create_attraction(data)` - Create single
- `link_to_district(attraction, district)` - Link relationships
- `query_attractions(filters)` - Complex filtering
- `get_by_district(district)` - By location
- `cleanup_relationships()` - Remove orphans

---

#### HolidayRepository ([database/repositories/holiday_repository.py](../src/database/repositories/holiday_repository.py))

**Specialized Methods**:
- `initialize_temporal_structure()` - Create Year/Month nodes
- `load_from_json()` - Load holidays with temporal links
- `query_holidays(filters)` - Complex temporal queries
- `get_by_year_month(year, month)` - Specific date range
- `get_temporal_structure()` - Hierarchy overview

---

#### ProjectRepository ([database/repositories/project_repository.py](../src/database/repositories/project_repository.py))

**Specialized Methods**:
- `load_schema()` - Project constraints
- `load_from_json()` - Load with location links
- `query(filters)` - Filter by type, location
- `get_statistics()` - Project stats

---

#### NewsRepository ([database/repositories/news_repository.py](../src/database/repositories/news_repository.py))

**Specialized Methods**:
- `load_schema()` - News constraints
- `load_from_json()` - Load with temporal links
- `query(filters)` - Filter by category, date
- `get_statistics()` - News stats

---

#### OntologyRepository ([database/repositories/ontology_repository.py](../src/database/repositories/ontology_repository.py))

**Specialized Methods**:
- `initialize_database()` - Full initialization
- `initialize_domain_structure()` - 12 domains
- `get_domain_overview()` - Domain statistics
- `get_domain_entities(domain)` - Entities in domain
- `get_graph_structure()` - Complete hierarchy
- `cleanup_duplicate_relationships()` - Remove duplicates
- `validate_shacl()` - SHACL validation

---

## Models & Schemas

### Base Models ([models/base.py](../src/models/base.py))

```python
class HealthResponse(BaseModel):
    status: str
    version: str

class ErrorResponse(BaseModel):
    error: str
    detail: str

class StatisticsResponse(BaseModel):
    statistics: Dict[str, Any]
```

---

### Knowledge Graph Models ([models/knowledge_graph.py](../src/models/knowledge_graph.py))

```python
class QueryRequest(BaseModel):
    query: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None

class QueryResponse(BaseModel):
    data: Optional[List[Dict[str, Any]]] = None
    result: Optional[Dict[str, Any]] = None
    execution_time: float
    provenance: Dict[str, Any]

class ReasonRequest(BaseModel):
    start_province: Optional[str] = None
    target_district: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None

class ReasonResponse(BaseModel):
    feasible: bool
    explanations: List[Dict[str, Any]]
    result: Optional[Dict[str, Any]] = None
    predictive: Optional[Dict[str, Any]] = None
    provenance: Dict[str, Any]
```

---

### Attraction Models ([models/attractions.py](../src/models/attractions.py))

```python
class AttractionModel(BaseModel):
    title: str
    description: str
    rating: Optional[float] = None
    district: str
    latitude: float
    longitude: float
    image_url: Optional[str] = None
    google_place_id: Optional[str] = None

class CreateAttractionRequest(AttractionModel):
    pass

class AttractionQueryRequest(BaseModel):
    title: Optional[str] = None
    district: Optional[str] = None
    province: Optional[str] = None
    min_rating: Optional[float] = None
    limit: int = 20

class AttractionResponse(BaseModel):
    attractions: List[Dict[str, Any]]
    count: int
    query_info: Dict[str, Any]
```

---

### Holiday Models ([models/holidays.py](../src/models/holidays.py))

```python
class HolidayModel(BaseModel):
    name: str
    date: str  # YYYY-MM-DD
    category: str  # Religious, Cultural, National, General
    holiday_type: str
    is_public_holiday: bool
    description: Optional[str] = None

class HolidayQueryRequest(BaseModel):
    year: Optional[int] = None
    month: Optional[int] = None
    category: Optional[str] = None
    holiday_type: Optional[str] = None
    is_public_holiday: Optional[bool] = None
    name: Optional[str] = None
    limit: int = 50

class HolidayResponse(BaseModel):
    holidays: List[Dict[str, Any]]
    count: int
    query_info: Dict[str, Any]
```

---

### GraphRAG Models ([models/graphrag.py](../src/models/graphrag.py))

```python
class IngestImmigrationDataRequest(BaseModel):
    data_dir: str
    domain_name: str = "Economic & Policy"

class IngestImmigrationDataResponse(BaseModel):
    success: bool
    statistics: Dict[str, Any]
    message: str

class RAGQueryRequest(BaseModel):
    question: str
    top_k: int = 5
    domain_name: str = "Economic & Policy"

class RAGQueryResponse(BaseModel):
    answer: str
    context: List[Dict[str, Any]]
    metadata: Dict[str, Any]
```

---

## Data Flow

### 1. Request Flow (API Call)

```
HTTP Request
    ↓
FastAPI Router (e.g., attractions.py)
    ↓
Request Validation (Pydantic Models)
    ↓
Dependency Injection (get_db_manager)
    ↓
DatabaseManager
    ↓
Specific Repository (AttractionRepository)
    ↓
Neo4j Driver (Cypher Query)
    ↓
Neo4j Database
    ↓
Response Processing
    ↓
Response Model (Pydantic)
    ↓
JSON Response
```

---

### 2. Vector Search Flow

```
User Query
    ↓
EmbeddingService.generate_embedding()
    ↓
SentenceTransformer Model
    ↓
Query Vector [384 dimensions]
    ↓
Neo4j Vector Index Search
    ↓
db.index.vector.queryNodes()
    ↓
Cosine Similarity Calculation
    ↓
Top-K Results with Scores
    ↓
Response
```

---

### 3. GraphRAG Ingestion Flow

```
JSON Files
    ↓
DataIngestionService
    ↓
ChunkProcessor (split text)
    ↓
Chunks [1000 chars, 100 overlap]
    ↓
EmbeddingService (generate vectors)
    ↓
EntityExtractor (LLM extraction)
    ↓
Entities + Relationships
    ↓
Neo4j Storage
    ├── Chunk nodes with embeddings
    ├── Entity nodes
    ├── Relationship edges
    └── Links to Domain
```

---

### 4. GraphRAG Query Flow

```
User Question
    ↓
RAGQueryEngine
    ↓
Generate Query Embedding
    ↓
Vector Similarity Search
    ↓
Retrieve Top-K Chunks
    ↓
Traverse Graph for Context
    ↓
Extract Connected Entities
    ↓
Build Context Window
    ↓
LLM Generation (with context)
    ↓
Natural Language Answer
```

---

### 5. Initialization Flow (rebuild.py)

```
1. Check API Health (/health)
    ↓
2. Clear Database (DELETE all nodes)
    ↓
3. Initialize Domains (/domains/initialize)
    ├── Create 12 Domain nodes
    └── Create Country node
    ↓
4. Load Geography (from Cypher script)
    ├── Create Province nodes
    └── Create District nodes
    ↓
5. Initialize Temporal (/holidays/initialize-temporal)
    ├── Create Year nodes
    └── Create Month nodes
    ↓
6. Load Holidays (/holidays/load)
    ├── Read holidays.json
    ├── Create Holiday nodes
    └── Link to Year/Month
    ↓
7. Load Attractions (/attractions/initialize)
    ├── Read attractions.json
    ├── Create Attraction nodes
    ├── Link to Districts
    └── Link to Domain
    ↓
8. Create Vector Index
    ↓
9. Generate Embeddings
    ↓
10. Load Projects (/projects/initialize)
    ├── Read projects.json
    ├── Create Project nodes
    └── Link to Locations
    ↓
11. Load News (/news/initialize)
    ├── Read news.json
    ├── Create News nodes
    └── Link to Temporal
    ↓
12. Verify Statistics (/kg/statistics)
```

---

## Configuration

### Environment Variables (.env)

```bash
# Neo4j Configuration
KG_NEO4J_URI=bolt://127.0.0.1:7687
KG_NEO4J_USER=neo4j
KG_NEO4J_PASSWORD=password

# API Configuration
KG_API_HOST=0.0.0.0
KG_API_PORT=8000
KG_DEBUG=false

# AI/ML Configuration
KG_EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
KG_VECTOR_INDEX_NAME=attraction_embeddings
KG_VECTOR_DIMENSIONS=384

# LLM API Keys
KG_OPENAI_API_KEY=sk-...
KG_GROQ_API_KEY=gsk_...

# LLM Provider Configuration
KG_INGESTION_LLM_PROVIDER=openai
KG_INGESTION_LLM_MODEL=gpt-4o-mini
KG_QUERY_LLM_PROVIDER=groq
KG_QUERY_LLM_MODEL=llama-3.3-70b-versatile
KG_LLM_TEMPERATURE=0

# GraphRAG Configuration
KG_GRAPHRAG_CHUNK_SIZE=1000
KG_GRAPHRAG_CHUNK_OVERLAP=100
KG_GRAPHRAG_TOP_K=5
```

---

### Settings Object ([core/config.py](../src/core/config.py))

```python
from core.config import settings

# Access configuration
neo4j_uri = settings.neo4j_uri
api_port = settings.api_port
embedding_model = settings.embedding_model_name
openai_key = settings.openai_api_key
```

---

## Usage Examples

### Example 1: Query Attractions by District

```python
import requests

response = requests.post(
    "http://localhost:8000/attractions/query",
    json={
        "district": "Kandy",
        "min_rating": 4.0,
        "limit": 10
    }
)

attractions = response.json()["attractions"]
print(f"Found {len(attractions)} attractions in Kandy")
```

---

### Example 2: Vector Search for Similar Attractions

```python
response = requests.post(
    "http://localhost:8000/agent/search",
    json={
        "query": "ancient temples with historical significance",
        "limit": 5
    }
)

results = response.json()["result"]
for result in results:
    print(f"{result['title']}: {result['score']}")
```

---

### Example 3: Query Holidays

```python
response = requests.post(
    "http://localhost:8000/holidays/query",
    json={
        "year": 2025,
        "category": "Religious",
        "is_public_holiday": True
    }
)

holidays = response.json()["holidays"]
for holiday in holidays:
    print(f"{holiday['date']}: {holiday['name']}")
```

---

### Example 4: Symbolic Reasoning

```python
response = requests.post(
    "http://localhost:8000/kg/reason",
    json={
        "start_province": "Central",
        "target_district": "Kandy"
    }
)

reasoning = response.json()
if reasoning["feasible"]:
    path = reasoning["explanations"][0]["path_nodes"]
    print(f"Path: {' → '.join([n['name'] for n in path])}")
```

---

### Example 5: GraphRAG Query

```python
response = requests.post(
    "http://localhost:8000/graphrag/query",
    json={
        "question": "What are the visa policies for tourists visiting Sri Lanka?",
        "top_k": 3
    }
)

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Sources: {len(result['context'])} chunks")
```

---

### Example 6: Get Domain Structure

```python
response = requests.get("http://localhost:8000/domains/structure")

structure = response.json()
print(f"Domains: {structure['domain_count']}")
print(f"Provinces: {structure['province_count']}")
print(f"Districts: {structure['district_count']}")
print(f"Attractions: {structure['attraction_count']}")
```

---

## Key Design Patterns

### 1. **Repository Pattern**
- Separates data access logic
- Each entity type has its own repository
- DatabaseManager acts as facade

### 2. **Dependency Injection**
- FastAPI's `Depends()` for dependency management
- Singleton services (EmbeddingService, LLMFactory)
- Driver injection at startup

### 3. **Factory Pattern**
- LLMFactory creates appropriate LLM instances
- Abstracts provider differences (OpenAI vs Groq)

### 4. **Singleton Pattern**
- EmbeddingService (one model instance)
- GraphRAGService (shared across requests)

### 5. **Facade Pattern**
- DatabaseManager provides simplified interface
- Hides complexity of multiple repositories

---

## Performance Considerations

### 1. **Indexes**
- Create indexes on frequently queried properties
- Vector index for semantic search
- Composite indexes for complex queries

### 2. **Batch Processing**
- Use APOC for bulk operations
- Batch embedding generation
- Batch entity extraction

### 3. **Caching**
- Model caching (SentenceTransformer)
- Driver connection pooling
- Query result caching (future)

### 4. **Pagination**
- Limit parameter on all list endpoints
- SKIP/LIMIT in Cypher queries

---

## Error Handling

### 1. **HTTP Exceptions**
```python
raise HTTPException(
    status_code=404,
    detail="Attraction not found"
)
```

### 2. **Global Exception Handler**
```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )
```

### 3. **Repository-Level Error Handling**
```python
try:
    result = self.execute_query(cypher, params)
    return result
except Exception as e:
    logger.error(f"Query failed: {e}")
    raise
```

---

## Testing

### Running the Service

```powershell
# Activate virtual environment
cd C:\Users\DananjayaAbey\Desktop\graphCeylon-API\services\kg_service\src

# Run with uv
uv run main.py

# Or with Python directly
python main.py
```

### Health Check

```powershell
curl http://localhost:8000/health
```

### API Documentation

```
http://localhost:8000/docs
```

---

## Summary

The KG Service is a sophisticated microservice that:

1. **Manages** a comprehensive tourism knowledge graph
2. **Provides** RESTful APIs for CRUD operations
3. **Implements** advanced reasoning capabilities
4. **Supports** vector search and semantic similarity
5. **Integrates** LLMs for GraphRAG functionality
6. **Organizes** data into 12 tourism domains
7. **Links** geographic, temporal, and entity data
8. **Scales** with proper indexing and batching
9. **Abstracts** complexity through clean architecture
10. **Documents** all operations with provenance

The service is production-ready and designed for scalability, maintainability, and extensibility.
