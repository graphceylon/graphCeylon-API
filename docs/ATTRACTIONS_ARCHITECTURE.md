# Attractions API Architecture

## System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Request                               │
│  POST /attractions/orchestrator/call/attractions                     │
│  {                                                                    │
│    "city": "Kandy",                                                  │
│    "country": "Sri Lanka",                                           │
│    "poi_category": "temple",                                         │
│    "days": 2                                                         │
│  }                                                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Router Layer                              │
│  attractions.py                                                      │
│  - Validates request (AttractionSearchRequest)                       │
│  - Gets DatabaseManager instance                                     │
│  - Calls OrchestratorAttractionService                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              OrchestratorAttractionService                           │
│  orchestrator_attraction_service.py                                  │
│                                                                       │
│  1. search_attractions(request)                                      │
│     ├─ _normalize_city_name("Kandy") → "Kandy"                      │
│     ├─ _get_attractions_by_city(city, filters)  ────────┐          │
│     │                                                     │          │
│     │  2. Build Neo4j Query                              │          │
│     │     WHERE toLower(a.city) = toLower("Kandy")       │          │
│     │     AND placeTypes CONTAINS "temple"               │          │
│     │     ORDER BY rating DESC                           │          │
│     │     LIMIT 10                                       │          │
│     │                                                     ▼          │
│     │                               ┌──────────────────────────────┐│
│     │                               │      Neo4j Database          ││
│     │                               │                              ││
│     │                               │  ┌────────────────┐         ││
│     │                               │  │  Attraction    │         ││
│     │                               │  │  Nodes         │         ││
│     │                               │  │  - title       │         ││
│     │                               │  │  - city        │         ││
│     │                               │  │  - rating      │         ││
│     │                               │  │  - placeTypes  │         ││
│     │                               │  └────────┬───────┘         ││
│     │                               │           │                 ││
│     │                               │           │ [:LOCATED_IN]   ││
│     │                               │           ▼                 ││
│     │                               │  ┌────────────────┐         ││
│     │                               │  │  District      │         ││
│     │                               │  │  Nodes         │         ││
│     │                               │  └────────────────┘         ││
│     │                               └──────────┬───────────────────┘│
│     │                                          │                    │
│     │  3. Process Results  ◄───────────────────┘                   │
│     │                                                               │
│     ├─ _map_to_item(data) for each result                          │
│     │   ├─ _extract_category(placeTypes) → "temple"                │
│     │   ├─ _build_location_string() → "Sri Dalada Veediya, Kandy"  │
│     │   ├─ _estimate_entry_fee(priceLevel) → "1500"               │
│     │   └─ Create AttractionItem                                   │
│     │                                                               │
│     └─ _generate_summary(items, "Kandy", 2)                        │
│        → "Found 5 attractions in Kandy including 3 temples..."     │
│                                                                      │
│  Returns AttractionSearchResponse                                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Response to Client                              │
│  {                                                                    │
│    "ok": true,                                                       │
│    "city": "Kandy",                                                  │
│    "country": "Sri Lanka",                                           │
│    "items": [                                                        │
│      {                                                               │
│        "name": "Temple of the Sacred Tooth Relic",                   │
│        "category": "temple",                                         │
│        "description": "Buddhist temple housing...",                  │
│        "location": "Sri Dalada Veediya, Kandy",                      │
│        "open_hours": "Hours vary, please check website",             │
│        "entry_fee_lkr": "1500",                                      │
│        "source": "kg_service",                                       │
│        "rating": 4.6                                                 │
│      }                                                               │
│    ],                                                                │
│    "summary": "Found 5 attractions in Kandy including 3 temples..." │
│  }                                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Request Processing
```
Client Request
    → FastAPI Router validates schema
    → Passes to OrchestratorAttractionService
    → Service normalizes city name
```

### 2. Database Query
```
Service builds Cypher query with filters
    → Executes against Neo4j
    → Retrieves Attraction nodes matching city
    → Joins with District nodes for location
    → Sorts by rating DESC
```

### 3. Response Mapping
```
Raw Neo4j data
    → Extract category from placeTypes
    → Build location string
    → Estimate entry fee from priceLevel
    → Create AttractionItem objects
    → Generate summary with category counts
```

### 4. Response Delivery
```
AttractionSearchResponse
    → Serialized to JSON
    → Returned to client with 200 OK
    → Client receives formatted attractions list
```

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           KG Service                                 │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    API Layer                                 │   │
│  │                                                              │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  attractions.py (Router)                             │  │   │
│  │  │  - GET /attractions                                  │  │   │
│  │  │  - GET /attractions/districts                        │  │   │
│  │  │  - GET /attractions/district/{name}                  │  │   │
│  │  │  - POST /attractions/query                           │  │   │
│  │  │  - POST /orchestrator/call/attractions ← NEW         │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  └───────────────────────────┬─────────────────────────────────┘   │
│                              │                                       │
│  ┌───────────────────────────▼─────────────────────────────────┐   │
│  │                   Service Layer                             │   │
│  │                                                              │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  OrchestratorAttractionService                       │  │   │
│  │  │  - search_attractions()                              │  │   │
│  │  │  - _normalize_city_name()                            │  │   │
│  │  │  - _get_attractions_by_city()                        │  │   │
│  │  │  - _map_to_item()                                    │  │   │
│  │  │  - _extract_category()                               │  │   │
│  │  │  - _estimate_entry_fee()                             │  │   │
│  │  │  - _generate_summary()                               │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  └───────────────────────────┬─────────────────────────────────┘   │
│                              │                                       │
│  ┌───────────────────────────▼─────────────────────────────────┐   │
│  │                   Model Layer                               │   │
│  │                                                              │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  attraction_orchestrator.py                          │  │   │
│  │  │  - AttractionSearchRequest                           │  │   │
│  │  │  - AttractionItem                                    │  │   │
│  │  │  - AttractionSearchResponse                          │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  └───────────────────────────┬─────────────────────────────────┘   │
│                              │                                       │
│  ┌───────────────────────────▼─────────────────────────────────┐   │
│  │                 Database Layer                              │   │
│  │                                                              │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  DatabaseManager                                     │  │   │
│  │  │  - Neo4j Driver                                      │  │   │
│  │  │  - execute_query()                                   │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Neo4j Database                               │
│                                                                       │
│  Nodes:                                                              │
│  - Attraction (title, city, rating, placeTypes, priceLevel, ...)    │
│  - District (name)                                                   │
│  - Province (name)                                                   │
│                                                                       │
│  Relationships:                                                      │
│  - (Attraction)-[:LOCATED_IN]->(District)                           │
│  - (District)-[:IN_PROVINCE]->(Province)                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Integration with Orchestrator Service

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Main Orchestrator Service                         │
│  (Processes natural language queries)                                │
│                                                                       │
│  User: "Plan a 2-day trip to Kandy with temples and hotels"         │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  1. Intent Classification                                     │  │
│  │     - Detect: trip planning                                   │  │
│  │     - Entities: city=Kandy, duration=2 days, type=temples     │  │
│  └────────────────────────────┬──────────────────────────────────┘  │
│                               │                                      │
│  ┌────────────────────────────▼──────────────────────────────────┐  │
│  │  2. Service Orchestration                                     │  │
│  │                                                                │  │
│  │     ┌─────────────────────────────────────────────────────┐  │  │
│  │     │ Call Attractions API                                │  │  │
│  │     │ POST /attractions/orchestrator/call/attractions     │  │  │
│  │     │ → Get temples in Kandy                              │  │  │
│  │     └─────────────────────┬───────────────────────────────┘  │  │
│  │                           │                                   │  │
│  │     ┌─────────────────────▼───────────────────────────────┐  │  │
│  │     │ Call Hotels API                                     │  │  │
│  │     │ POST /hotels/orchestrator/call/hotels               │  │  │
│  │     │ → Get hotels near Kandy attractions                 │  │  │
│  │     └─────────────────────┬───────────────────────────────┘  │  │
│  │                           │                                   │  │
│  │     ┌─────────────────────▼───────────────────────────────┐  │  │
│  │     │ Call Transport API                                  │  │  │
│  │     │ POST /train-schedules/orchestrator/call/transport   │  │  │
│  │     │ → Get trains to Kandy                               │  │  │
│  │     └─────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────┬──────────────────────────────────┘  │
│                               │                                      │
│  ┌────────────────────────────▼──────────────────────────────────┐  │
│  │  3. Response Aggregation                                      │  │
│  │     - Combine all results                                     │  │
│  │     - Generate comprehensive itinerary                        │  │
│  │     - Format as natural language response                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## File Structure

```
graphCeylon-API/
├── services/
│   └── kg_service/
│       └── src/
│           ├── api/
│           │   └── routers/
│           │       └── attractions.py ← Modified (added orchestrator endpoint)
│           ├── models/
│           │   └── domain/
│           │       └── attraction_orchestrator.py ← NEW
│           └── services/
│               └── orchestrator_attraction_service.py ← NEW
│
└── docs/
    ├── ATTRACTIONS_API.md ← NEW (API documentation)
    ├── ATTRACTIONS_IMPLEMENTATION_SUMMARY.md ← NEW (summary)
    ├── ATTRACTIONS_ARCHITECTURE.md ← NEW (this file)
    └── postman/
        └── Attractions_API_Tests.postman_collection.json ← NEW
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI |
| Database | Neo4j (Graph Database) |
| Query Language | Cypher |
| Validation | Pydantic |
| Python Version | 3.11+ |
| Testing | Postman |

## Key Design Decisions

### 1. City-Based Search
**Decision:** Search by city instead of district/province
**Rationale:** 
- Users think in terms of cities, not administrative divisions
- More intuitive for tourists
- Easier natural language processing

### 2. Rating-Based Sorting
**Decision:** Sort by rating DESC, then userRatingsTotal DESC
**Rationale:**
- Show best attractions first
- Prioritize popular, well-reviewed spots
- Better user experience

### 3. Entry Fee Estimation
**Decision:** Estimate from Google price level (0-4)
**Rationale:**
- Actual fees not available in data
- Price level provides rough guidance
- Better than showing nothing

### 4. Category Extraction
**Decision:** Parse from Google placeTypes field
**Rationale:**
- Rich categorization from Google Places
- Multiple categories per attraction
- Standardized taxonomy

### 5. Generic Opening Hours
**Decision:** Show "Hours vary, please check website"
**Rationale:**
- Opening hours not structured in current data
- Avoid showing incorrect information
- Direct users to authoritative source

## Performance Considerations

### Query Optimization
- Indexed properties: `city`, `title`, `rating`
- Limited to 10 results by default
- Uses OPTIONAL MATCH for relationships (faster than MATCH)
- ORDER BY uses indexed fields

### Caching Opportunities (Future)
- Cache popular city results (Kandy, Colombo)
- TTL: 1 hour (attractions rarely change)
- Invalidate on data updates

### Scalability
- Stateless service design
- Horizontal scaling possible
- Neo4j connection pooling
- Async query execution (future enhancement)

## Error Handling Strategy

```
Error Types:
├── Validation Errors (400)
│   └── Missing required fields (city, country)
├── Not Found (200 with ok=false)
│   └── No attractions in specified city
├── Database Errors (200 with ok=false)
│   └── Neo4j connection issues
└── Unexpected Errors (200 with ok=false)
    └── Catch-all for unknown issues
```

All errors return structured response:
```json
{
  "ok": false,
  "error": "Error type",
  "details": "Detailed message"
}
```

## Security Considerations

### Current Implementation
- No authentication (internal service)
- Input validation via Pydantic
- SQL injection protected (parameterized Cypher)

### Future Enhancements
- API key authentication
- Rate limiting per user/session
- Request logging for audit
- CORS configuration
