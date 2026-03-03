// ============================================================================
// Initialize Sub-Attraction (POI) Schema
// Creates constraints and indexes for SubAttraction and POIGroup nodes
// ============================================================================

// ============================================================================
// STEP 1: Create Constraints
// ============================================================================

// Unique constraint on SubAttraction by Google Place ID (primary identifier)
CREATE CONSTRAINT sub_attraction_place_id IF NOT EXISTS FOR (s:SubAttraction) REQUIRE s.googlePlaceId IS UNIQUE;

// Unique constraint on POIGroup by name
CREATE CONSTRAINT poi_group_name IF NOT EXISTS FOR (g:POIGroup) REQUIRE g.name IS UNIQUE;

// ============================================================================
// STEP 2: Create Indexes for Performance
// ============================================================================

CREATE INDEX sub_attraction_name IF NOT EXISTS FOR (s:SubAttraction) ON (s.name);

CREATE INDEX sub_attraction_parent IF NOT EXISTS FOR (s:SubAttraction) ON (s.parentLocation);

CREATE INDEX sub_attraction_rating IF NOT EXISTS FOR (s:SubAttraction) ON (s.rating);

CREATE INDEX sub_attraction_district IF NOT EXISTS FOR (s:SubAttraction) ON (s.district);

CREATE INDEX sub_attraction_province IF NOT EXISTS FOR (s:SubAttraction) ON (s.province);

CREATE INDEX sub_attraction_amenity IF NOT EXISTS FOR (s:SubAttraction) ON (s.amenityType);

CREATE INDEX sub_attraction_business_status IF NOT EXISTS FOR (s:SubAttraction) ON (s.businessStatus);

CREATE INDEX sub_attraction_coords IF NOT EXISTS FOR (s:SubAttraction) ON (s.latitude, s.longitude);

CREATE INDEX poi_group_name_idx IF NOT EXISTS FOR (g:POIGroup) ON (g.name);

// ============================================================================
// STEP 3: Create Vector Index for Semantic Search (Neo4j 5.x)
// ============================================================================

// Vector index for embedding-based semantic search
// Using cosine similarity for normalized embeddings
// Dimension 768 matches sentence-transformers/all-mpnet-base-v2
CALL db.index.vector.createNodeIndex(
    'sub_attraction_embeddings',
    'SubAttraction',
    'embedding',
    768,
    'cosine'
);
