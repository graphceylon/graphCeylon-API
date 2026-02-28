# Attractions API Documentation

## Overview

The Attractions API provides access to tourist attractions in Sri Lanka through the Knowledge Graph service. The orchestrator endpoint is designed to integrate with the main orchestrator service for natural language queries.

## Endpoint

### POST /attractions/orchestrator/call/attractions

Search for tourist attractions based on city and optional filters.

**URL:** `http://localhost:8003/attractions/orchestrator/call/attractions`

**Method:** `POST`

**Content-Type:** `application/json`

---

## Request Schema

### AttractionSearchRequest

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `city` | string | Yes | City name | "Kandy" |
| `country` | string | Yes | Country name | "Sri Lanka" |
| `poi_name` | string | No | Specific POI to search for | "Temple of the Sacred Tooth Relic" |
| `poi_category` | string | No | Category filter (temple, museum, park, etc.) | "temple" |
| `days` | integer | No | Trip duration for planning context | 2 |
| `tags` | array[string] | No | Tags for filtering | ["cultural", "historical"] |
| `user_id` | string | No | User ID for personalization | "user123" |
| `session_id` | string | No | Session ID for tracking | "session456" |
| `query` | string | No | Natural language query | "What are the main tourist attractions in Kandy?" |

### Example Request

```json
{
  "city": "Kandy",
  "country": "Sri Lanka",
  "poi_category": "temple",
  "days": 2,
  "query": "What are the main tourist attractions in Kandy?"
}
```

---

## Response Schema

### AttractionSearchResponse

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Whether search was successful |
| `city` | string | City searched |
| `country` | string | Country searched |
| `items` | array[AttractionItem] | List of attractions |
| `summary` | string | Natural language summary |
| `error` | string | Error type (only if ok=false) |
| `details` | string | Error details (only if ok=false) |

### AttractionItem

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Attraction name |
| `category` | string | Attraction category/type |
| `description` | string | Brief description |
| `location` | string | Location/address |
| `open_hours` | string | Opening hours |
| `entry_fee_lkr` | string | Entry fee in LKR |
| `source` | string | Data source (always "kg_service") |
| `rating` | float | Google rating (0-5) |
| `coordinates` | string | Lat, Lon coordinates |
| `website` | string | Official website |
| `phone` | string | Phone number |

### Example Response (Success)

```json
{
  "ok": true,
  "city": "Kandy",
  "country": "Sri Lanka",
  "items": [
    {
      "name": "Temple of the Sacred Tooth Relic",
      "category": "temple",
      "description": "Buddhist temple housing the relic of the tooth of Buddha",
      "location": "Sri Dalada Veediya, Kandy",
      "open_hours": "Hours vary, please check website",
      "entry_fee_lkr": "1500",
      "source": "kg_service",
      "rating": 4.6,
      "coordinates": "7.2934, 80.6405",
      "website": "http://sridaladamaligawa.lk",
      "phone": "+94 81 223 4226"
    },
    {
      "name": "Royal Botanical Gardens",
      "category": "garden",
      "description": "Large botanical garden in Peradeniya, near Kandy",
      "location": "Peradeniya, Kandy",
      "open_hours": "Hours vary, please check website",
      "entry_fee_lkr": "1000-2000",
      "source": "kg_service",
      "rating": 4.5,
      "coordinates": "7.2715, 80.5963"
    }
  ],
  "summary": "Found 5 attractions in Kandy including 3 temples, 1 garden, 1 museum. Great selection for a 2-day exploration."
}
```

### Example Response (Error)

```json
{
  "ok": false,
  "city": "NonExistentCity",
  "country": "Sri Lanka",
  "items": [],
  "summary": "",
  "error": "No attractions found",
  "details": "No attractions available in NonExistentCity"
}
```

---

## Search Features

### City-Based Search
The API searches attractions by city name. City names are normalized automatically:
- Case-insensitive matching
- Common aliases supported (e.g., "colombo" → "Colombo")

### Supported Cities
Major tourist cities in Sri Lanka:
- Colombo
- Kandy
- Galle
- Jaffna
- Negombo
- Trincomalee
- Anuradhapura
- Polonnaruwa
- Nuwara Eliya
- Ella
- Sigiriya
- Dambulla
- Matara
- Bentota
- Hikkaduwa
- Mirissa
- Arugam Bay

### Category Filtering
Filter by attraction type using `poi_category`:
- `temple` - Religious temples
- `church` - Churches
- `mosque` - Mosques
- `museum` - Museums
- `park` - Parks and gardens
- `garden` - Botanical gardens
- `zoo` - Zoos
- `beach` - Beaches
- `historical` - Historical sites
- `monument` - Monuments
- `palace` - Palaces
- `fort` - Forts
- `waterfall` - Waterfalls
- `lake` - Lakes
- `mountain` - Mountains
- `viewpoint` - Viewpoints
- `market` - Markets

### Name Search
Search for specific attractions using `poi_name`:
- Partial name matching (case-insensitive)
- Example: "tooth relic" matches "Temple of the Sacred Tooth Relic"

### Trip Planning Context
Provide `days` parameter for trip planning context:
- Summary adjusts based on trip duration
- Example: "Perfect for a day trip" vs "Great selection for a 3-day exploration"

---

## Testing

### Postman Collection
Import the Postman collection from:
```
docs/postman/Attractions_API_Tests.postman_collection.json
```

### Test Cases

#### 1. Basic Search - All Attractions in Kandy
```bash
curl -X POST http://localhost:8003/attractions/orchestrator/call/attractions \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Kandy",
    "country": "Sri Lanka",
    "query": "What are the main tourist attractions in Kandy?"
  }'
```

#### 2. Category Filter - Temples in Kandy
```bash
curl -X POST http://localhost:8003/attractions/orchestrator/call/attractions \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Kandy",
    "country": "Sri Lanka",
    "poi_category": "temple",
    "days": 2
  }'
```

#### 3. Name Search - Specific Attraction
```bash
curl -X POST http://localhost:8003/attractions/orchestrator/call/attractions \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Kandy",
    "country": "Sri Lanka",
    "poi_name": "tooth relic"
  }'
```

#### 4. Multiple Filters
```bash
curl -X POST http://localhost:8003/attractions/orchestrator/call/attractions \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Colombo",
    "country": "Sri Lanka",
    "poi_category": "museum",
    "days": 1,
    "tags": ["cultural", "historical"]
  }'
```

---

## Integration with Orchestrator

The attractions API is designed to be called by the main orchestrator service for:

1. **Natural Language Queries**: Process queries like "What can I visit in Kandy?"
2. **Trip Planning**: Provide attraction recommendations based on duration
3. **Multi-Service Integration**: Combine with hotel and transport services
4. **Personalization**: Use user_id and session_id for tracking

### Example Orchestrator Flow
```
User Query: "Plan a 2-day trip to Kandy with temples and cultural sites"
    ↓
Orchestrator parses intent
    ↓
Calls /attractions/orchestrator/call/attractions with:
    - city: "Kandy"
    - poi_category: "temple"
    - days: 2
    - tags: ["cultural"]
    ↓
Returns attractions with summary
    ↓
Orchestrator combines with hotels and transport
    ↓
Returns complete trip plan
```

---

## Data Structure

### Neo4j Schema

**Nodes:**
- `Attraction` - Tourist attraction with properties:
  - `title` - Attraction name
  - `description` - Description
  - `city` - City location
  - `district` - District
  - `province` - Province
  - `latitude`, `longitude` - Coordinates
  - `rating` - Google rating
  - `priceLevel` - Price level (0-4)
  - `placeTypes` - Google Place types
  - `website` - Official website
  - `phoneNumber` - Contact number
  - `formattedAddress` - Full address

**Relationships:**
- `(Attraction)-[:LOCATED_IN]->(District)`
- `(District)-[:IN_PROVINCE]->(Province)`

### Query Pattern
```cypher
MATCH (a:Attraction)
WHERE toLower(a.city) = toLower($city)
OPTIONAL MATCH (a)-[:LOCATED_IN]->(d:District)
RETURN properties(a), d.name
ORDER BY a.rating DESC, a.userRatingsTotal DESC
LIMIT 10
```

---

## Error Handling

### Common Errors

| Error | Details | Solution |
|-------|---------|----------|
| No attractions found | City has no attractions in database | Check city spelling or try nearby city |
| Search failed | Database connection error | Check Neo4j service status |
| Invalid request | Missing required fields | Ensure city and country are provided |

### Error Response Format
All errors return `ok: false` with:
- `error`: Error type
- `details`: Detailed error message

---

## Rate Limiting

No rate limiting currently implemented. Future versions may include:
- Per-user rate limits
- Session-based throttling

---

## Future Enhancements

1. **Opening Hours Parsing**: Extract actual opening hours from data
2. **Real Entry Fees**: Get actual entry fee information
3. **Distance Calculation**: Add distance from city center
4. **Popularity Ranking**: Sort by user ratings and reviews
5. **Season Recommendations**: Best time to visit each attraction
6. **Accessibility Info**: Wheelchair access and facilities
7. **Photo Gallery**: Multiple images per attraction
8. **User Reviews**: Include review summaries

---

## Support

For issues or questions:
1. Check the Postman collection for working examples
2. Review Neo4j data using existing `/attractions` endpoints
3. Check logs in `services/kg_service/logs/`
4. Verify Neo4j connection and data initialization

## Related Endpoints

- `GET /attractions` - Get all attractions
- `GET /attractions/districts` - List districts with attractions
- `GET /attractions/district/{name}` - Attractions by district
- `GET /attractions/province/{name}` - Attractions by province
- `POST /attractions/query` - Advanced query with filters
