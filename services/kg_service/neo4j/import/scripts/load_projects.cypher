// ============================================================================
// Load Tourism Projects from JSON
// This script loads SLTDA tourism projects and connects them to locations
// ============================================================================

// ============================================================================
// STEP 1: Load Projects from JSON using APOC
// ============================================================================

CALL apoc.load.json('file: ///data/sltda_projects.json') YIELD value

// Extract projects from the projects array
UNWIND value.projects AS project

// Create unique ID and project_type from title
WITH project, value,
toLower(replace(project.title, ' ', '_')) + '_' + toString(timestamp()) AS project_id,


CASE
 WHEN toLower(project.title) CONTAINS 'infrastructure' THEN 'Infrastructure'
 WHEN toLower(project.title) CONTAINS 'regional' THEN 'Regional'
 WHEN toLower(project.title) CONTAINS 'beach' OR toLower(project.title) CONTAINS 'resort' THEN 'Resort Development'
 WHEN toLower(project.title) CONTAINS 'lake' THEN 'Lake Development'
 WHEN toLower(project.title) CONTAINS 'wild' OR toLower(project.title) CONTAINS 'yala' THEN 'Wildlife Tourism'
ELSE 'General'
END AS project_type

// Create TourismProject node with all properties
MERGE (p:TourismProject { id: project_id })
  ON CREATE SET
p.title = project.title,
p.image = project.image,
p.description = project.description,
p.details = project.details,
p.contact_text = project.contact_text,
p.href = project.href,
p.project_type = project_type,
p.scraped_at = value.scraped_at,
p.created_at = datetime()
  ON MATCH SET
p.updated_at = datetime(),
p.project_type = project_type

// Link projects to country
WITH p
MATCH (c:Country { name: "Sri Lanka" })
MERGE (p)-[:IN_COUNTRY]->(c);

// Link projects to appropriate domain
MATCH (p:TourismProject)
MATCH (d:Domain)
WHERE d.name IN ["Destination & Attraction", "Infrastructure & Development"]
MERGE (p)-[:BELONGS_TO_DOMAIN]->(d);

// ============================================================================
// STEP 2: Link Projects to Provinces and Districts
// ============================================================================

// Link projects to provinces based on project details
MATCH (p:TourismProject)
WHERE p.details IS NOT null

UNWIND p.details AS detail
WITH p, detail
WHERE toLower(detail) CONTAINS 'province'

// Extract province name from detail
WITH p,


CASE
 WHEN toLower(detail) CONTAINS 'eastern' THEN 'Eastern'
 WHEN toLower(detail) CONTAINS 'western' THEN 'Western'
 WHEN toLower(detail) CONTAINS 'southern' THEN 'Southern'
 WHEN toLower(detail) CONTAINS 'northern' THEN 'Northern'
 WHEN toLower(detail) CONTAINS 'central' THEN 'Central'
 WHEN toLower(detail) CONTAINS 'north western' THEN 'North Western'
 WHEN toLower(detail) CONTAINS 'north central' THEN 'North Central'
 WHEN toLower(detail) CONTAINS 'uva' THEN 'Uva'
 WHEN toLower(detail) CONTAINS 'sabaragamuwa' THEN 'Sabaragamuwa'
ELSE null
END AS province_name

WHERE province_name IS NOT null

MATCH (prov:Province { name: province_name })
MERGE (p)-[:LOCATED_IN_PROVINCE]->(prov);

// Link projects to districts based on project details
MATCH (p:TourismProject)
WHERE p.details IS NOT null

UNWIND p.details AS detail
WITH p, detail
WHERE toLower(detail) CONTAINS 'district'

// Extract district name from detail
WITH p,


CASE
 WHEN toLower(detail) CONTAINS 'trincomalee' THEN 'Trincomalee'
 WHEN toLower(detail) CONTAINS 'hambantota' THEN 'Hambantota'
 WHEN toLower(detail) CONTAINS 'puttalam' THEN 'Puttalam'
 WHEN toLower(detail) CONTAINS 'batticaloa' THEN 'Batticaloa'
 WHEN toLower(detail) CONTAINS 'galle' THEN 'Galle'
 WHEN toLower(detail) CONTAINS 'kalutara' THEN 'Kalutara'
ELSE null
END AS district_name

WHERE district_name IS NOT null

MATCH (dist:District { name: district_name })
MERGE (p)-[:LOCATED_IN_DISTRICT]->(dist);

// ============================================================================
// STEP 3: Link specific known projects by title
// ============================================================================

// Kuchchaweli Beach Resort -> Trincomalee
MATCH (p:TourismProject)
WHERE toLower(p.title) CONTAINS 'kuchchaweli'
MATCH (dist:District { name: 'Trincomalee' })
MERGE (p)-[:LOCATED_IN_DISTRICT]->(dist);

// Dedduwa Lake Resort -> Kalutara
MATCH (p:TourismProject)
WHERE toLower(p.title) CONTAINS 'dedduwa'
MATCH (dist:District { name: 'Kalutara' })
MERGE (p)-[:LOCATED_IN_DISTRICT]->(dist);

// Kalpitiya Project -> Puttalam
MATCH (p:TourismProject)
WHERE toLower(p.title) CONTAINS 'kalpitiya'
MATCH (dist:District { name: 'Puttalam' })
MERGE (p)-[:LOCATED_IN_DISTRICT]->(dist);

// Passikudah Resort -> Batticaloa
MATCH (p:TourismProject)
WHERE toLower(p.title) CONTAINS 'passikudah'
MATCH (dist:District { name: 'Batticaloa' })
MERGE (p)-[:LOCATED_IN_DISTRICT]->(dist);

// Yala Wild Resort -> Hambantota
MATCH (p:TourismProject)
WHERE toLower(p.title) CONTAINS 'yala'
MATCH (dist:District { name: 'Hambantota' })
MERGE (p)-[:LOCATED_IN_DISTRICT]->(dist);

// ============================================================================
// STEP 4: Link provinces to projects (inverse relationship)
// ============================================================================

MATCH (p:TourismProject)-[:LOCATED_IN_PROVINCE]->(prov:Province)
MERGE (prov)-[:HAS_PROJECT]->(p);

// Link districts to projects (inverse relationship)
MATCH (p:TourismProject)-[:LOCATED_IN_DISTRICT]->(dist:District)
MERGE (dist)-[:HAS_PROJECT]->(p);

// ============================================================================
// STEP 5: Return summary
// ============================================================================

MATCH (p:TourismProject)
OPTIONAL MATCH (p)-[:LOCATED_IN_PROVINCE]->(prov:Province)
OPTIONAL MATCH (p)-[:LOCATED_IN_DISTRICT]->(dist:District)
RETURN
count( DISTINCT p) AS total_projects,
count( DISTINCT prov) AS projects_with_province,
count( DISTINCT dist) AS projects_with_district,
collect( DISTINCT p.project_type) AS project_types;
