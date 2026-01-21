# Knowledge Graph Rebuild Script Documentation

## Overview

The `rebuild.py` script provides a complete automation solution for rebuilding the GraphCeylon knowledge graph from scratch. It clears the entire Neo4j database and reconstructs it by loading all data entities and their relationships in the correct order.

**Location**: `services/kg_service/src/rebuild.py`

**Purpose**: 
- Complete database reset and rebuild
- Ensures clean, consistent graph structure
- Validates data integrity at each step
- Provides detailed logging and statistics

---

## Prerequisites

### 1. Running Services
- **Neo4j Database**: Must be running on `bolt://localhost:7687`
- **API Server**: Must be running on `http://localhost:8000`

### 2. Required Data Files
- `data/kg_service/data/attractions.json` - Tourist attractions data
- `data/kg_service/data/holidays.json` - Holiday calendar data
- `data/kg_service/data/projects.json` - Tourism projects data
- `data/kg_service/data/news.json` - Tourism news articles
- `neo4j/import/scripts/seed_provinces_districts.cypher` - Geography data

### 3. Python Dependencies
```bash
requests
```

---

## Usage

### Running the Script

```bash
# From the project root
cd services/kg_service/src
python rebuild.py
```

### Expected Output
```
╔══════════════════════════════════════════════════════════╗
║          KNOWLEDGE GRAPH REBUILD SCRIPT                  ║
╚══════════════════════════════════════════════════════════╝

STEP 0: CHECKING API HEALTH
============================================================
✓ API is healthy - Version: 1.0.0

STEP 1: CLEARING DATABASE
============================================================
✓ Successfully cleared all nodes and relationships
  Remaining nodes: 0
✓ Database is completely empty

[... continues through all steps ...]

REBUILD SUMMARY
============================================================
✓ Graph rebuild completed successfully!
  Total Time: 45.23 seconds
  Total Nodes: 543
  Total Relationships: 1247
```

---

## Step-by-Step Breakdown

### STEP 0: Health Check
**Function**: `check_api_health()`

**Purpose**: Verifies the API is accessible and ready to accept requests.

**Endpoint**: `GET /health`

**Actions**:
- Tests connectivity to `http://localhost:8000`
- Retrieves API version information
- Fails early if API is not available

**Graph Changes**: None

---

### STEP 1: Clear Database
**Function**: `clear_database()`

**Purpose**: Completely wipes the Neo4j database to start fresh.

**Cypher Query**:
```cypher
CALL apoc.periodic.iterate(
    'MATCH (n) RETURN n',
    'DETACH DELETE n',
    {batchSize: 1000}
)
```

**Actions**:
1. Deletes all nodes and relationships in batches of 1000
2. Verifies deletion by counting remaining nodes
3. Confirms database is empty (0 nodes)

**Graph Changes**:
- ❌ Deletes: ALL nodes and relationships

**Verification Query**:
```cypher
MATCH (n) RETURN count(n) AS node_count
```

---

### STEP 2: Initialize Domains & Geography
**Function**: `initialize_domains_and_geography()`

This step has two sub-components:

#### 2a. Create Domain Structure
**Endpoint**: `POST /domains/initialize`

**Nodes Created**: `(Domain)`

**Properties**:
```
{
  name: "Destination & Attraction",
  code: "DEST_ATTR",
  description: "Tourist destinations and attractions",
  order: 1,
  icon: "map-marker",
  color: "#FF6B6B",
  isActive: true
}
```

**Domain Categories**:
1. Destination & Attraction
2. Culture & Heritage
3. Tourism Services
4. Infrastructure & Development
5. Economic Impact
6. Environmental & Wildlife
7. Events & Activities
8. Regulatory & Policy

**Relationships**: None at this stage

**Graph Structure**:
```
(Domain:1) (Domain:2) (Domain:3) ... (standalone nodes)
```

---

#### 2b. Load Provinces & Districts
**Script**: `neo4j/import/scripts/seed_provinces_districts.cypher`

**Nodes Created**:

**`(Province)` - 9 nodes**:
```
{
  name: "Western Province",
  code: "WP",
  capital: "Colombo",
  area_km2: 3709,
  population: 5851130
}
```

**Provinces**:
- Western Province
- Central Province
- Southern Province
- Northern Province
- Eastern Province
- North Western Province
- North Central Province
- Uva Province
- Sabaragamuwa Province

**`(District)` - 25 nodes**:
```
{
  name: "Colombo",
  code: "CO",
  area_km2: 699,
  population: 2324349
}
```

**Districts by Province**:
- **Western**: Colombo, Gampaha, Kalutara
- **Central**: Kandy, Matale, Nuwara Eliya
- **Southern**: Galle, Matara, Hambantota
- **Northern**: Jaffna, Kilinochchi, Mannar, Vavuniya, Mullaitivu
- **Eastern**: Batticaloa, Ampara, Trincomalee
- **North Western**: Kurunegala, Puttalam
- **North Central**: Anuradhapura, Polonnaruwa
- **Uva**: Badulla, Monaragala
- **Sabaragamuwa**: Ratnapura, Kegalle

**Relationships Created**:
```cypher
(District)-[:IN_PROVINCE]->(Province)
```

**Example Relationships**:
```
(Colombo:District)-[:IN_PROVINCE]->(Western Province:Province)
(Kandy:District)-[:IN_PROVINCE]->(Central Province:Province)
(Galle:District)-[:IN_PROVINCE]->(Southern Province:Province)
```

**Graph Structure After Step 2**:
```
Domains (standalone):
  (Domain:1) (Domain:2) (Domain:3) ...

Geography (connected):
  (Western Province) ← (Colombo:District)
                      ← (Gampaha:District)
                      ← (Kalutara:District)
  
  (Central Province) ← (Kandy:District)
                     ← (Matale:District)
                     ← (Nuwara Eliya:District)
  ...
```

**Statistics**:
- **Nodes**: 9 Provinces + 25 Districts = 34 nodes
- **Relationships**: 25 IN_PROVINCE relationships

---

### STEP 3: Initialize Temporal Structure
**Function**: `initialize_temporal_structure()`

**Endpoint**: `POST /holidays/initialize-temporal`

**Nodes Created**:

**`(Year)` - 11 nodes (2020-2030)**:
```
{
  year: 2024,
  name: "2024",
  createdAt: datetime()
}
```

**`(Month)` - 132 nodes (12 months × 11 years)**:
```
{
  number: 1,
  name: "January",
  shortName: "Jan",
  year: 2024,
  createdAt: datetime()
}
```

**Relationships Created**:
```cypher
(Month)-[:IN_YEAR]->(Year)
```

**Example Relationships**:
```
(January 2024:Month)-[:IN_YEAR]->(2024:Year)
(February 2024:Month)-[:IN_YEAR]->(2024:Year)
(March 2024:Month)-[:IN_YEAR]->(2024:Year)
...
(January 2025:Month)-[:IN_YEAR]->(2025:Year)
```

**Graph Structure After Step 3**:
```
Temporal Structure:
  (2024:Year) ← (January 2024:Month)
              ← (February 2024:Month)
              ← (March 2024:Month)
              ...
              ← (December 2024:Month)
  
  (2025:Year) ← (January 2025:Month)
              ← (February 2025:Month)
              ...
```

**Statistics**:
- **Nodes**: 11 Years + 132 Months = 143 nodes
- **Relationships**: 132 IN_YEAR relationships

---

### STEP 4: Load Holidays
**Function**: `load_holidays()`

**Endpoint**: `POST /holidays/load`

**Data Source**: `data/kg_service/data/holidays.json`

**Nodes Created**: `(Holiday)` - ~100 nodes

**Properties**:
```
{
  name: "Vesak Full Moon Poya Day",
  date: "2024-05-23",
  category: "Buddhist",
  isPublicHoliday: true,
  description: "Commemorates the birth, enlightenment, and death of Buddha",
  year: 2024,
  month: 5,
  day: 23,
  createdAt: datetime()
}
```

**Holiday Categories**:
- Buddhist (Poya Days, Vesak, Poson)
- Hindu (Thai Pongal, Deepavali)
- Christian (Christmas, Good Friday)
- Muslim (Ramadan, Hajj)
- National (Independence Day, May Day)
- Tamil (Tamil New Year)

**Relationships Created**:
```cypher
(Holiday)-[:OCCURS_IN]->(Month)
(Holiday)-[:OCCURS_IN]->(Year)
(Holiday)-[:BELONGS_TO_DOMAIN]->(Domain {name: "Culture & Heritage"})
```

**Example Relationships**:
```
(Vesak:Holiday)-[:OCCURS_IN]->(May 2024:Month)
(Vesak:Holiday)-[:OCCURS_IN]->(2024:Year)
(Vesak:Holiday)-[:BELONGS_TO_DOMAIN]->(Culture & Heritage:Domain)

(Christmas:Holiday)-[:OCCURS_IN]->(December 2024:Month)
(Christmas:Holiday)-[:OCCURS_IN]->(2024:Year)
(Christmas:Holiday)-[:BELONGS_TO_DOMAIN]->(Culture & Heritage:Domain)
```

**Graph Structure After Step 4**:
```
(Holiday) → (Month) → (Year)
    ↓
(Domain: Culture & Heritage)
```

**Statistics**:
- **Nodes**: ~100 Holiday nodes
- **Relationships**: ~300 (100 holidays × 3 relationships each)
- **Categories**: Buddhist (40%), National (20%), Hindu (15%), Christian (15%), Muslim (10%)

---

### STEP 5: Load Attractions
**Function**: `load_attractions()`

**Endpoint**: `POST /attractions/initialize`

**Data Source**: `data/kg_service/data/attractions.json`

**Nodes Created**: `(Attraction)` - 39 nodes

**Complete Properties** (extracted from JSON):

```javascript
{
  // Basic Information
  title: "Anuradhapura",
  description: "Ancient capital with well-preserved ruins...",
  imageUrl: "https://www.sltda.gov.lk/storage/...",
  scrapedAt: "2025-11-18T21:44:30.100742",
  
  // Coordinates
  latitude: 8.311351799999999,
  longitude: 80.4036508,
  coordinateAccuracy: "high",
  
  // Address Information
  formattedAddress: "Anuradhapura, Sri Lanka",
  country: "Sri Lanka",
  countryCode: "LK",
  province: "North Central Province",
  district: "Anuradhapura",
  city: "Anuradhapura",
  postalCode: "",
  
  // Geocoding Metadata
  geocodedAt: "2025-11-22T09:37:25.706647",
  geocodingService: "google_maps",
  geocodingConfidence: "high",
  googlePlaceId: "ChIJWeFgk_n0_DoRDs9tvJ7-EcE",
  
  // Google Place Data
  rating: 4.7,
  userRatingsTotal: 15234,
  website: "http://example.com",
  phoneNumber: "+94123456789",
  priceLevel: 2,
  placeUrl: "https://maps.google.com/?cid=...",
  editorialSummary: "A UNESCO World Heritage Site...",
  placeName: "Anuradhapura Archaeological Site",
  vicinity: "Anuradhapura",
  placeTypes: "[\"tourist_attraction\",\"point_of_interest\"]",
  
  // Map Links
  googleMapsUrl: "https://www.google.com/maps/search/...",
  googleMapsDirectionsUrl: "https://www.google.com/maps/dir/...",
  googleEarthUrl: "https://earth.google.com/web/@...",
  coordinatesDMS: "8°18'40.87\"N, 80°24'13.14\"E",
  
  // Links
  links: "[{\"type\":\"gallery\",\"url\":\"...\"},{\"type\":\"wikipedia\",\"url\":\"...\"}]",
  
  // Timestamps
  createdAt: datetime(),
  updatedAt: datetime()
}
```

**All 39 Attractions**:
1. Anuradhapura
2. Arugambay
3. Adam's Peak
4. Batticaloa
5. Bentota
6. Beruwela
7. Bundala National Park
8. Colombo
9. Dambulla
10. Ella
11. Galle
12. Hambantota
13. Hikkaduwa
14. Horton Plains
15. Jaffna
16. Kalkudah
17. Kalpitiya
18. Kandy
19. Katunayake
20. Kitulgala
21. Knuckles Range
22. Mannar
23. Matara
24. Minneriya
25. Mirissa
26. Negombo
27. Nilaveli
28. Nuwara Eliya
29. Polonnaruwa
30. Pasikuda
31. Pinnawala
32. Sigiriya
33. Tangalle
34. Trincomalee
35. Udawalawe
36. Unawatuna
37. Wilpattu National Park
38. Yala National Park
39. Yapahuwa

**Relationships Created** (per your updated code):
```cypher
(Attraction)-[:LOCATED_IN]->(District)
(Attraction)-[:IN_PROVINCE]->(Province)
```

**Note**: No reverse relationships (HAS_ATTRACTION) are created.

**Example Relationships**:
```
(Anuradhapura:Attraction)-[:LOCATED_IN]->(Anuradhapura:District)
(Anuradhapura:Attraction)-[:IN_PROVINCE]->(North Central Province:Province)

(Sigiriya:Attraction)-[:LOCATED_IN]->(Matale:District)
(Sigiriya:Attraction)-[:IN_PROVINCE]->(Central Province:Province)

(Galle Fort:Attraction)-[:LOCATED_IN]->(Galle:District)
(Galle Fort:Attraction)-[:IN_PROVINCE]->(Southern Province:Province)
```

**Graph Structure After Step 5**:
```
(Attraction) → (District) → (Province)
```

**Distribution by Province**:
- Western Province: 5-7 attractions
- Central Province: 6-8 attractions
- Southern Province: 7-9 attractions
- North Central Province: 3-4 attractions
- Eastern Province: 4-5 attractions
- Others: 8-10 attractions

**Statistics**:
- **Nodes**: 39 Attraction nodes
- **Relationships**: 78 (39 × 2 relationships each)

---

### STEP 6: Load Tourism Projects
**Function**: `load_projects()`

**Endpoint**: `POST /projects/initialize`

**Data Source**: `data/kg_service/data/projects.json`

**Nodes Created**: `(Project)` - Variable count (50-100 typical)

**Properties**:
```
{
  name: "Colombo Port City Development",
  description: "Major urban development project...",
  type: "Infrastructure",
  status: "Ongoing",
  budget: 15000000000,
  currency: "USD",
  startDate: "2023-01-15",
  endDate: "2026-12-31",
  province: "Western Province",
  district: "Colombo",
  fundingSource: "Government + Private",
  createdAt: datetime()
}
```

**Project Types**:
- Infrastructure (airports, roads, ports)
- Hospitality (hotels, resorts)
- Conservation (wildlife, heritage sites)
- Technology (tourism apps, booking systems)
- Marketing (promotional campaigns)

**Relationships Created**:
```cypher
(Project)-[:LOCATED_IN]->(District)
(Project)-[:IN_PROVINCE]->(Province)
(Project)-[:BELONGS_TO_DOMAIN]->(Domain)
(Project)-[:STARTED_IN]->(Year)
(Project)-[:ENDS_IN]->(Year)  // if endDate exists
```

**Example Relationships**:
```
(Port City:Project)-[:LOCATED_IN]->(Colombo:District)
(Port City:Project)-[:IN_PROVINCE]->(Western Province:Province)
(Port City:Project)-[:BELONGS_TO_DOMAIN]->(Infrastructure & Development:Domain)
(Port City:Project)-[:STARTED_IN]->(2023:Year)
(Port City:Project)-[:ENDS_IN]->(2026:Year)
```

**Graph Structure After Step 6**:
```
(Project) → (District) → (Province)
    ↓           ↓
(Domain)    (Year)
```

**Statistics**:
- **Nodes**: 50-100 Project nodes
- **Relationships**: 200-400 (4-5 per project)

---

### STEP 7: Load Tourism News
**Function**: `load_news()`

**Endpoint**: `POST /news/initialize`

**Data Source**: `data/kg_service/data/news.json`

**Nodes Created**: `(NewsArticle)` - Variable count (100-200 typical)

**Properties**:
```
{
  title: "Sri Lanka Tourism Sees Record Growth in 2024",
  content: "Full article content...",
  summary: "Brief summary of the article...",
  publishedDate: "2024-11-15",
  category: "Industry News",
  source: "SLTDA",
  url: "https://www.sltda.gov.lk/...",
  author: "Tourism Board",
  year: 2024,
  month: 11,
  createdAt: datetime()
}
```

**News Categories**:
- Industry News
- Policy Changes
- Tourist Arrivals
- Events & Festivals
- Infrastructure Updates
- Economic Impact
- Safety & Security
- Environmental Issues

**Relationships Created**:
```cypher
(NewsArticle)-[:PUBLISHED_IN]->(Month)
(NewsArticle)-[:PUBLISHED_IN]->(Year)
(NewsArticle)-[:BELONGS_TO_DOMAIN]->(Domain)
(NewsArticle)-[:RELATES_TO]->(Province)  // optional
(NewsArticle)-[:MENTIONS]->(Attraction)  // optional
(NewsArticle)-[:ABOUT]->(Project)        // optional
```

**Example Relationships**:
```
(Article:NewsArticle)-[:PUBLISHED_IN]->(November 2024:Month)
(Article:NewsArticle)-[:PUBLISHED_IN]->(2024:Year)
(Article:NewsArticle)-[:BELONGS_TO_DOMAIN]->(Economic Impact:Domain)
(Article:NewsArticle)-[:MENTIONS]->(Sigiriya:Attraction)
(Article:NewsArticle)-[:RELATES_TO]->(Central Province:Province)
```

**Graph Structure After Step 7**:
```
(NewsArticle) → (Month) → (Year)
      ↓            ↓         ↓
  (Domain)   (Attraction) (Province)
      ↓
  (Project)
```

**Statistics**:
- **Nodes**: 100-200 NewsArticle nodes
- **Relationships**: 300-800 (3-5 per article)

---

## Final Graph Structure

### Complete Node Inventory

| Node Label    | Count    | Description                          |
|---------------|----------|--------------------------------------|
| Domain        | 8-10     | Tourism domain categories            |
| Province      | 9        | Sri Lankan provinces                 |
| District      | 25       | Sri Lankan districts                 |
| Year          | 11       | Years 2020-2030                      |
| Month         | 132      | 12 months × 11 years                 |
| Holiday       | ~100     | Public holidays and observances      |
| Attraction    | 39       | Tourist attractions                  |
| Project       | 50-100   | Tourism development projects         |
| NewsArticle   | 100-200  | Tourism news and updates             |
| **TOTAL**     | **500-600** | **Total nodes in graph**          |

### Complete Relationship Inventory

| Relationship Type     | Count    | Pattern                                    |
|-----------------------|----------|--------------------------------------------|
| IN_PROVINCE           | 25+39+50 | District/Attraction/Project → Province     |
| IN_YEAR               | 132      | Month → Year                               |
| BELONGS_TO_DOMAIN     | 100+50+100 | Holiday/Project/News → Domain           |
| OCCURS_IN             | 200      | Holiday → Month/Year                       |
| LOCATED_IN            | 39+50    | Attraction/Project → District              |
| STARTED_IN            | 50       | Project → Year                             |
| ENDS_IN               | 30       | Project → Year                             |
| PUBLISHED_IN          | 200      | NewsArticle → Month/Year                   |
| MENTIONS              | 50       | NewsArticle → Attraction                   |
| RELATES_TO            | 30       | NewsArticle → Province                     |
| ABOUT                 | 20       | NewsArticle → Project                      |
| **TOTAL**             | **1000-1500** | **Total relationships in graph**      |

### Graph Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│                    DOMAIN LAYER                         │
│  (Categorizes all tourism-related entities)             │
│  - Destination & Attraction                             │
│  - Culture & Heritage                                    │
│  - Tourism Services, etc.                               │
└─────────────────────────────────────────────────────────┘
           ↑                    ↑                ↑
           │                    │                │
┌──────────┴────────┐  ┌───────┴──────┐  ┌─────┴────────┐
│   TEMPORAL        │  │  GEOGRAPHIC   │  │    DATA      │
│   STRUCTURE       │  │  STRUCTURE    │  │   ENTITIES   │
├───────────────────┤  ├───────────────┤  ├──────────────┤
│ Years (2020-2030) │  │ 9 Provinces   │  │ 100 Holidays │
│ 132 Months        │  │ 25 Districts  │  │ 39 Attractions│
└───────────────────┘  └───────────────┘  │ 50+ Projects │
           ↑                    ↑          │ 100+ News    │
           │                    │          └──────────────┘
           │                    │                │
           └────────────────────┴────────────────┘
                        ↑
                   Relationships connect all layers
```

### Key Relationship Patterns

1. **Geographic Hierarchy**:
   ```
   Entity → District → Province
   ```

2. **Temporal Placement**:
   ```
   Event → Month → Year
   ```

3. **Domain Classification**:
   ```
   Entity → Domain
   ```

4. **Cross-Entity References**:
   ```
   NewsArticle → Attraction
   NewsArticle → Project
   NewsArticle → Province
   ```

---

## Verification & Statistics

### Final Verification Query

After the rebuild, the script runs this query to verify the graph:

```cypher
MATCH (n)
RETURN 
  count(n) AS node_count,
  collect(DISTINCT labels(n)) AS node_labels

UNION

MATCH ()-[r]->()
RETURN 
  count(r) AS relationship_count,
  collect(DISTINCT type(r)) AS relationship_types
```

### Expected Statistics

**Successful Build**:
- Total Nodes: 500-600
- Total Relationships: 1000-1500
- Execution Time: 30-60 seconds

**Node Distribution**:
```
Domain:       8-10   (2%)
Province:     9      (2%)
District:     25     (5%)
Year:         11     (2%)
Month:        132    (25%)
Holiday:      100    (20%)
Attraction:   39     (8%)
Project:      50-100 (15%)
NewsArticle:  100-200 (35%)
```

**Relationship Distribution**:
```
IN_PROVINCE:       ~150  (15%)
IN_YEAR:           132   (13%)
BELONGS_TO_DOMAIN: ~250  (25%)
OCCURS_IN:         200   (20%)
LOCATED_IN:        ~100  (10%)
PUBLISHED_IN:      200   (20%)
Other:             ~70   (7%)
```

---

## Troubleshooting

### Common Issues

#### 1. API Not Running
**Error**: `Cannot connect to API`

**Solution**:
```bash
cd services/kg_service
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. Neo4j Not Running
**Error**: `Failed to connect to Neo4j`

**Solution**:
- Start Neo4j Desktop or service
- Verify connection at `http://localhost:7474`
- Check credentials in `.env` file

#### 3. Missing Data Files
**Error**: `Attractions data file not found`

**Solution**:
- Ensure all JSON files exist in `data/kg_service/data/`
- Check file paths in the script
- Verify file permissions

#### 4. APOC Plugin Not Installed
**Error**: `Unknown function 'apoc.periodic.iterate'`

**Solution**:
- Install APOC plugin in Neo4j
- In Neo4j Desktop: Settings → Plugins → APOC → Install
- Restart Neo4j

#### 5. Partial Build
**Warning**: `Failed to load attractions. Continuing...`

**Solution**:
- Check logs for specific error
- Verify data file format
- Ensure API endpoints are registered
- Run the script again (it will skip successful steps)

---

## Best Practices

### When to Rebuild

1. **After Schema Changes**: When you modify node properties or relationship types
2. **Data Corruption**: If the graph becomes inconsistent
3. **Testing**: Before running integration tests
4. **Deployment**: When setting up a new environment
5. **Version Updates**: After major API updates

### Before Running

1. **Backup Your Data**: 
   ```bash
   # Export current graph
   neo4j-admin dump --database=neo4j --to=/path/to/backup.dump
   ```

2. **Stop Active Connections**: Close Neo4j Browser and any active queries

3. **Check Disk Space**: Ensure sufficient space for rebuild (~500MB minimum)

### After Running

1. **Verify Statistics**: Check node and relationship counts match expectations

2. **Test Queries**: Run sample queries to verify data integrity
   ```cypher
   // Test geographic connections
   MATCH (a:Attraction)-[:LOCATED_IN]->(d:District)-[:IN_PROVINCE]->(p:Province)
   RETURN a.title, d.name, p.name LIMIT 5
   
   // Test temporal connections
   MATCH (h:Holiday)-[:OCCURS_IN]->(m:Month)-[:IN_YEAR]->(y:Year)
   RETURN h.name, m.name, y.year LIMIT 5
   ```

3. **Check Performance**: Verify query response times are acceptable

---

## Extending the Script

### Adding New Data Types

To add a new entity type (e.g., Hotels):

1. **Create the data file**: `data/kg_service/data/hotels.json`

2. **Add API endpoint**: In your API, create `POST /hotels/initialize`

3. **Add to script**:
   ```python
   def load_hotels() -> bool:
       logger.info("STEP X: LOADING HOTELS")
       response = requests.post(f"{BASE_URL}/hotels/initialize", timeout=60)
       # ... handle response
       return True
   ```

4. **Update main function**:
   ```python
   def main():
       # ... existing steps
       if not load_hotels():
           logger.warning("Failed to load hotels. Continuing...")
   ```

### Customizing Verification

Add custom verification queries:

```python
def verify_attraction_coverage():
    """Verify all districts have at least one attraction."""
    query = """
    MATCH (d:District)
    OPTIONAL MATCH (d)<-[:LOCATED_IN]-(a:Attraction)
    WITH d, count(a) AS attraction_count
    WHERE attraction_count = 0
    RETURN d.name AS district
    """
    response = requests.post(
        API_ENDPOINTS["query"],
        json={"query": query}
    )
    # ... check results
```

---

## Performance Considerations

### Optimization Tips

1. **Batch Size**: APOC iterate uses 1000 nodes per batch (configurable)

2. **Indexing**: Ensure indexes exist on frequently queried properties:
   ```cypher
   CREATE INDEX attraction_title IF NOT EXISTS FOR (a:Attraction) ON (a.title)
   CREATE INDEX district_name IF NOT EXISTS FOR (d:District) ON (d.name)
   ```

3. **Connection Pooling**: The script reuses HTTP connections for efficiency

4. **Parallel Loading**: Future optimization could load independent entities in parallel

### Expected Timings

| Step | Time (seconds) | Notes |
|------|---------------|-------|
| Health Check | 0.5 | Fast |
| Clear Database | 5-10 | Depends on existing size |
| Domains & Geography | 3-5 | Multiple Cypher statements |
| Temporal | 2-3 | 143 nodes |
| Holidays | 5-8 | ~100 nodes + relationships |
| Attractions | 8-12 | 39 nodes + full data extraction |
| Projects | 10-15 | Variable data |
| News | 15-20 | Largest dataset |
| **Total** | **45-75** | **Average rebuild time** |

---

## Security Notes

### Data Privacy

- No sensitive data should be in JSON files (passwords, API keys, etc.)
- Use environment variables for credentials
- Ensure data files are in `.gitignore`

### Access Control

- The script requires Neo4j write permissions
- Restrict access to production databases
- Use separate databases for development and testing

---

## Maintenance

### Regular Tasks

1. **Update Data Files**: Keep JSON files current with latest information
2. **Monitor Script Performance**: Track execution time trends
3. **Review Logs**: Check for warnings or errors
4. **Validate Data Quality**: Ensure relationships are correct

### Versioning

Track script changes:
```python
SCRIPT_VERSION = "2.0.0"  # Add to script header
```

Update documentation when:
- Adding new data types
- Changing relationship patterns
- Modifying verification logic

---

## Related Documentation

- [Project Structure](./PROJECT_STRUCTURE.md) - Overall project layout
- [Database Setup](./DATABASE_SETUP_GUIDE.md) - Neo4j configuration
- [API Documentation](./API_TESTING_GUIDE.md) - API endpoint details
- [Quick Start](./QUICK_START.md) - Getting started guide

---

## Support

For issues or questions:
1. Check the Troubleshooting section
2. Review logs in terminal output
3. Verify all prerequisites are met
4. Contact the development team

---

**Last Updated**: December 28, 2025  
**Script Version**: 2.0  
**Maintained By**: GraphCeylon Development Team
