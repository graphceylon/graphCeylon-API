// Constraints & indexes
CREATE CONSTRAINT province_name_unique IF NOT EXISTS
FOR (p:Province) REQUIRE p.name IS UNIQUE;

CREATE CONSTRAINT district_name_unique IF NOT EXISTS
FOR (d:District) REQUIRE d.name IS UNIQUE;

CREATE INDEX district_province_idx IF NOT EXISTS
FOR (d:District) ON (d.provinceCode);

// Provinces
WITH [
{ name:"Western", iso:"LK-1" },
{ name:"Central", iso:"LK-2" },
{ name:"Southern", iso:"LK-3" },
{ name:"Northern", iso:"LK-4" },
{ name:"Eastern", iso:"LK-5" },
{ name:"North Western", iso:"LK-6" },
{ name:"North Central", iso:"LK-7" },
{ name:"Uva", iso:"LK-8" },
{ name:"Sabaragamuwa", iso:"LK-9" }
] AS provs
UNWIND provs AS p
MERGE (pr:Province { name:p.name })
  ON CREATE SET pr.isoCode = p.iso;

// Country (Sri Lanka) and link provinces to country
MERGE (c:Country { name: 'Sri Lanka' })
  ON CREATE SET c.isoCode = 'LK';

// Link provinces to country (ensure we bind the Country node)
MATCH (c:Country)
MATCH (pr:Province)
MERGE (c)-[:HAS_PROVINCE]->(pr)
MERGE (pr)-[:IN_COUNTRY]->(c);

// Districts (expanded as a list to avoid map-literal parsing issues)
UNWIND [
{ prov:'Western', d:'Colombo' }, {prov:'Western', d:'Gampaha'}, {prov:'Western', d:'Kalutara'},
{ prov:'Central', d:'Kandy' }, {prov:'Central', d:'Matale'}, {prov:'Central', d:'Nuwara Eliya'},
{ prov:'Southern', d:'Galle' }, {prov:'Southern', d:'Matara'}, {prov:'Southern', d:'Hambantota'},
{ prov:'Northern', d:'Jaffna' }, {prov:'Northern', d:'Kilinochchi'}, {prov:'Northern', d:'Mannar'}, {prov:'Northern', d:'Vavuniya'}, {prov:'Northern', d:'Mullaitivu'},
{ prov:'Eastern', d:'Trincomalee' }, {prov:'Eastern', d:'Batticaloa'}, {prov:'Eastern', d:'Ampara'},
{ prov:'North Western', d:'Kurunegala' }, {prov:'North Western', d:'Puttalam'},
{ prov:'North Central', d:'Anuradhapura' }, {prov:'North Central', d:'Polonnaruwa'},
{ prov:'Uva', d:'Badulla' }, {prov:'Uva', d:'Monaragala'},
{ prov:'Sabaragamuwa', d:'Ratnapura' }, {prov:'Sabaragamuwa', d:'Kegalle'}
] AS row
MATCH (p:Province { name:row.prov })
MERGE (d:District { name:row.d })
  ON CREATE SET d.provinceCode = p.isoCode
MERGE (p)-[:HAS_DISTRICT]->(d)
MERGE (d)-[:IN_PROVINCE]->(p);

// Optional roll-up for convenience
MATCH (p:Province)-[:HAS_DISTRICT]->(d:District)
WITH p, count(d) AS c
 SET p.districtCount = c;

// ============================================================================
// Link Provinces and Districts to Geographic Domain
// ============================================================================

// Ensure Geographic Domain exists
MERGE (geo:Domain { name: "Geographic" })
  ON CREATE SET
geo.order = 13,
geo.code = "GEO",
geo.description = "Structural domain for administrative geography hierarchy",
geo.status = "active",
geo.created_at = datetime()
  ON MATCH SET
geo.updated_at = datetime();

// Link Geographic Domain to Country
MATCH (c:Country { name: "Sri Lanka" })
MATCH (geo:Domain { name: "Geographic" })
MERGE (c)-[r1:HAS_DOMAIN]->(geo)
  ON CREATE SET r1.created_at = datetime();

// Link all Provinces to Geographic Domain
MATCH (geo:Domain { name: "Geographic" })
MATCH (p:Province)
MERGE (geo)-[r2:HAS_PROVINCE]->(p)
  ON CREATE SET r2.created_at = datetime()
MERGE (p)-[r3:BELONGS_TO_DOMAIN]->(geo)
  ON CREATE SET r3.created_at = datetime();

// Link all Districts to Geographic Domain
MATCH (geo:Domain { name: "Geographic" })
MATCH (d:District)
MERGE (geo)-[r4:HAS_DISTRICT]->(d)
  ON CREATE SET r4.created_at = datetime()
MERGE (d)-[r5:BELONGS_TO_DOMAIN]->(geo)
  ON CREATE SET r5.created_at = datetime();
