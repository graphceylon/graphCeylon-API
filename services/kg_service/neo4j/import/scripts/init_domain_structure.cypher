// Domain-Driven Architecture Initialization Script
// Phase 1: Create root structure and 12 domains for Sri Lankan Tourism Knowledge Graph

// ============================================================================
// STEP 1: Create Root Country Node
// ============================================================================

MERGE (sl:Country { name: "Sri Lanka" })
  ON CREATE SET
sl.isoCode = "LK",
sl.isoCode3 = "LKA",
sl.capital = "Colombo",
sl.continent = "Asia",
sl.region = "South Asia",
sl.population = 22156000,
sl.area_km2 = 65610,
sl.currency = "LKR",
sl.languages = ["Sinhala", "Tamil", "English"],
sl.timezone = "Asia/Colombo",
sl.calling_code = "+94",
sl.created_at = datetime(),
sl.description = "Democratic Socialist Republic of Sri Lanka - Island nation in South Asia"
  ON MATCH SET
sl.updated_at = datetime();

// ============================================================================
// STEP 2: Create 12 Domain Nodes
// ============================================================================

// Domain 1: Destination & Attraction
MERGE (d1:Domain { name: "Destination & Attraction" })
  ON CREATE SET
d1.order = 1,
d1.code = "DEST",
d1.description = "Core static knowledge of places with attributes, geolocation, accessibility, and timing",
d1.examples = ["Anuradhapura", "Sigiriya", "Yala National Park", "Galle Fort"],
d1.color = "#FF6B6B",
d1.icon = "map-pin",
d1.status = "active",
d1.created_at = datetime();

// Domain 2: Event & Activity
MERGE (d2:Domain { name: "Event & Activity" })
  ON CREATE SET
d2.order = 2,
d2.code = "EVENT",
d2.description = "Dynamic experiences using event-based models (4W1H: When, Where, Who, What, How)",
d2.examples = ["Hiking in Ella", "Cultural Festival", "Whale Watching", "Temple Visit"],
d2.color = "#4ECDC4",
d2.icon = "calendar",
d2.status = "planned",
d2.created_at = datetime();

// Domain 3: Accommodation & Hospitality
MERGE (d3:Domain { name: "Accommodation & Hospitality" })
  ON CREATE SET
d3.order = 3,
d3.code = "ACCOM",
d3.description = "Hotels, resorts, and lodging with pricing, amenities, and reviews",
d3.examples = ["Jetwing Blue", "Cinnamon Grand", "Homestay in Kandy"],
d3.color = "#95E1D3",
d3.icon = "home",
d3.status = "planned",
d3.created_at = datetime();

// Domain 4: Transportation
MERGE (d4:Domain { name: "Transportation" })
  ON CREATE SET
d4.order = 4,
d4.code = "TRANS",
d4.description = "Travel modes, routes, and accessibility between destinations",
d4.examples = ["Bus Route 87", "Colombo–Kandy Train", "Airport Shuttle", "Uber"],
d4.color = "#F38181",
d4.icon = "truck",
d4.status = "planned",
d4.created_at = datetime();

// Domain 5: Food & Cuisine
MERGE (d5:Domain { name: "Food & Cuisine" })
  ON CREATE SET
d5.order = 5,
d5.code = "FOOD",
d5.description = "Culinary entities and relationships between destinations and local dishes",
d5.examples = ["Kottu Roti", "Hoppers", "Jaffna Crab Curry", "Ceylon Tea"],
d5.color = "#FFEAA7",
d5.icon = "coffee",
d5.status = "planned",
d5.created_at = datetime();

// Domain 6: Cultural & Heritage
MERGE (d6:Domain { name: "Cultural & Heritage" })
  ON CREATE SET
d6.order = 6,
d6.code = "CULTURE",
d6.description = "Tangible and intangible heritage, traditions, crafts, festivals, and rituals",
d6.examples = ["Kandyan Dance", "Esala Perahera", "Wood Carving", "Mask Art"],
d6.color = "#DFE6E9",
d6.icon = "book",
d6.status = "planned",
d6.created_at = datetime();

// Domain 7: Climate & Geography
MERGE (d7:Domain { name: "Climate & Geography" })
  ON CREATE SET
d7.order = 7,
d7.code = "CLIMATE",
d7.description = "Environmental and contextual attributes for decision-making",
d7.examples = ["Tropical", "Dry Zone", "Rainy Season", "Coastal Belt"],
d7.color = "#74B9FF",
d7.icon = "cloud",
d7.status = "planned",
d7.created_at = datetime();

// Domain 8: User & Behavior
MERGE (d8:Domain { name: "User & Behavior" })
  ON CREATE SET
d8.order = 8,
d8.code = "USER",
d8.description = "User profiles, behaviors, interests, feedback, and travel history for personalization",
d8.examples = ["User123", "Prefers Adventure", "Visited Cultural Sites", "Positive Reviews"],
d8.color = "#A29BFE",
d8.icon = "user",
d8.status = "planned",
d8.created_at = datetime();

// Domain 9: Temporal
MERGE (d9:Domain { name: "Temporal" })
  ON CREATE SET
d9.order = 9,
d9.code = "TIME",
d9.description = "Temporal reasoning for events, seasons, and availability",
d9.examples = ["Season: Winter", "Festival: April 2025", "Monsoon Period"],
d9.color = "#FD79A8",
d9.icon = "clock",
d9.status = "planned",
d9.created_at = datetime();

// Domain 10: Economic & Policy
MERGE (d10:Domain { name: "Economic & Policy" })
  ON CREATE SET
d10.order = 10,
d10.code = "POLICY",
d10.description = "Visa rules, currency, cost models, and sustainability policies",
d10.examples = ["Visa on Arrival", "Carbon Offset Policy", "Tourism Levy"],
d10.color = "#FDCB6E",
d10.icon = "dollar-sign",
d10.status = "planned",
d10.created_at = datetime();

// Domain 11: Sentiment & Experience
MERGE (d11:Domain { name: "Sentiment & Experience" })
  ON CREATE SET
d11.order = 11,
d11.code = "SENTIMENT",
d11.description = "Reviews, emotions, and experience levels from user-generated content",
d11.examples = ["Sentiment: Positive", "Experience: Terrific", "Complaint: Overcrowding"],
d11.color = "#6C5CE7",
d11.icon = "heart",
d11.status = "planned",
d11.created_at = datetime();

// Domain 12: Cross-Field Associations (Meta-domain)
MERGE (d12:Domain { name: "Cross-Field Associations" })
  ON CREATE SET
d12.order = 12,
d12.code = "META",
d12.description = "Multi-domain relationships enabling semantic interoperability and reasoning",
d12.examples = ["Sigiriya ↔ Kassapa Era", "Kandy ↔ Esala Perahera"],
d12.color = "#00B894",
d12.icon = "share-2",
d12.status = "planned",
d12.created_at = datetime();

// Domain 13: Geographic (Structural Domain)
MERGE (d13:Domain { name: "Geographic" })
  ON CREATE SET
d13.order = 13,
d13.code = "GEO",
d13.description = "Structural domain for administrative geography hierarchy (Provinces and Districts)",
d13.examples = ["Western Province", "Colombo District", "Administrative Boundaries"],
d13.color = "#3498DB",
d13.icon = "map",
d13.status = "active",
d13.created_at = datetime()
  ON MATCH SET
d13.status = "active",
d13.updated_at = datetime();

// ============================================================================
// STEP 3: Link Domains to Country
// ============================================================================

MATCH (sl:Country { name: "Sri Lanka" })
MATCH (d:Domain)
MERGE (sl)-[r:HAS_DOMAIN]->(d)
  ON CREATE SET r.created_at = datetime();

// ============================================================================
// STEP 4: Link Existing Administrative Structure to Country
// ============================================================================

// Link provinces to country
MATCH (sl:Country { name: "Sri Lanka" })
MATCH (p:Province)
MERGE (sl)-[r1:HAS_PROVINCE]->(p)
  ON CREATE SET r1.created_at = datetime()
MERGE (p)-[r2:IN_COUNTRY]->(sl)
  ON CREATE SET r2.created_at = datetime();

// ============================================================================
// STEP 5: Link Existing Attractions to Domain
// ============================================================================

MATCH (a:Attraction)
MATCH (d:Domain { name: "Destination & Attraction" })
MERGE (a)-[r:BELONGS_TO_DOMAIN]->(d)
  ON CREATE SET r.created_at = datetime(), r.migrated = true ;

// ============================================================================
// STEP 6: Create Indexes for Performance
// ============================================================================

CREATE INDEX domain_name IF NOT EXISTS FOR (d:Domain) ON (d.name);

CREATE INDEX domain_code IF NOT EXISTS FOR (d:Domain) ON (d.code);

CREATE INDEX domain_order IF NOT EXISTS FOR (d:Domain) ON (d.order);

CREATE INDEX country_name IF NOT EXISTS FOR (c:Country) ON (c.name);

// ============================================================================
// STEP 7: Return Summary
// ============================================================================

MATCH (sl:Country { name: "Sri Lanka" })-[:HAS_DOMAIN]->(d:Domain)
RETURN sl.name AS Country,
count(d) AS TotalDomains,
collect(d.name) AS Domains
 ORDER BY sl.name;
