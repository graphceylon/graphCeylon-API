"""
Comprehensive SHACL Validation Shapes for Sri Lanka Tourism Knowledge Graph

Based on discovered schema with 27 node types:
- Geographic: Country, Province, District, City
- Tourism: Attraction, Hotel, Restaurant, Event
- Immigration: Authority, Document, VisaPolicy, VisaRequirement, VisaType, Country
- Administrative: Holiday, Project, News, SLTDAProject
- Domain Organization: Domain, EntityDomain
- And more...
"""

from neo4j import Driver
import logging

logger = logging.getLogger(__name__)


class ComprehensiveSHACLShapes:
    """SHACL validation shapes for all entity types in the knowledge graph."""
    
    def __init__(self, driver: Driver):
        self.driver = driver
        
    def install_all_shapes(self):
        """Install SHACL shapes for all entity types."""
        
        shapes = {
            # Geographic Entities
            "CountryShape": self._get_country_shape(),
            "ProvinceShape": self._get_province_shape(),
            "DistrictShape": self._get_district_shape(),
            "CityShape": self._get_city_shape(),
            
            # Tourism Entities
            "AttractionShape": self._get_attraction_shape(),
            "HotelShape": self._get_hotel_shape(),
            "RestaurantShape": self._get_restaurant_shape(),
            "EventShape": self._get_event_shape(),
            
            # Immigration Entities
            "AuthorityShape": self._get_authority_shape(),
            "DocumentShape": self._get_document_shape(),
            "VisaPolicyShape": self._get_visa_policy_shape(),
            "VisaTypeShape": self._get_visa_type_shape(),
            
            # Administrative Entities
            "HolidayShape": self._get_holiday_shape(),
            "ProjectShape": self._get_project_shape(),
            "NewsShape": self._get_news_shape(),
            
            # Domain Organization
            "DomainShape": self._get_domain_shape(),
        }
        
        results = {}
        with self.driver.session() as session:
            for shape_name, shape_cypher in shapes.items():
                try:
                    session.run(shape_cypher)
                    results[shape_name] = "installed"
                    logger.info(f"✓ Installed {shape_name}")
                except Exception as e:
                    results[shape_name] = f"error: {str(e)}"
                    logger.error(f"✗ Failed to install {shape_name}: {e}")
        
        return results
    
    def _get_country_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'CountryShape',
            targetClass: 'Country',
            description: 'Validation for Country nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'name',
            minCount: 1,
            datatype: 'xsd:string',
            description: 'Country must have a name'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop2:SHACLProperty {
            path: 'code',
            pattern: '^[A-Z]{2,3}$',
            description: 'Country code must be 2-3 uppercase letters'
        })
        """
    
    def _get_province_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'ProvinceShape',
            targetClass: 'Province',
            description: 'Validation for Province nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'name',
            minCount: 1,
            maxCount: 1,
            datatype: 'xsd:string',
            description: 'Province must have exactly one name'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop2:SHACLProperty {
            path: 'capital',
            datatype: 'xsd:string'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop3:SHACLProperty {
            path: 'area',
            datatype: 'xsd:decimal',
            minInclusive: 0
        })
        """
    
    def _get_district_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'DistrictShape',
            targetClass: 'District',
            description: 'Validation for District nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'name',
            minCount: 1,
            datatype: 'xsd:string'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop2:SHACLProperty {
            path: 'population',
            datatype: 'xsd:integer',
            minInclusive: 0
        })
        """
    
    def _get_city_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'CityShape',
            targetClass: 'City',
            description: 'Validation for City nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'name',
            minCount: 1,
            datatype: 'xsd:string'
        })
        """
    
    def _get_attraction_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'AttractionShape',
            targetClass: 'Attraction',
            description: 'Validation for Attraction nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'title',
            minCount: 1,
            datatype: 'xsd:string',
            description: 'Attraction must have a title'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop2:SHACLProperty {
            path: 'latitude',
            datatype: 'xsd:decimal',
            minInclusive: -90,
            maxInclusive: 90
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop3:SHACLProperty {
            path: 'longitude',
            datatype: 'xsd:decimal',
            minInclusive: -180,
            maxInclusive: 180
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop4:SHACLProperty {
            path: 'rating',
            datatype: 'xsd:decimal',
            minInclusive: 0,
            maxInclusive: 5
        })
        """
    
    def _get_hotel_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'HotelShape',
            targetClass: 'Hotel',
            description: 'Validation for Hotel nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'name',
            minCount: 1,
            datatype: 'xsd:string'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop2:SHACLProperty {
            path: 'rating',
            datatype: 'xsd:decimal',
            minInclusive: 0,
            maxInclusive: 5
        })
        """
    
    def _get_restaurant_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'RestaurantShape',
            targetClass: 'Restaurant',
            description: 'Validation for Restaurant nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'name',
            minCount: 1,
            datatype: 'xsd:string'
        })
        """
    
    def _get_event_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'EventShape',
            targetClass: 'Event',
            description: 'Validation for Event nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'name',
            minCount: 1,
            datatype: 'xsd:string'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop2:SHACLProperty {
            path: 'date',
            datatype: 'xsd:date'
        })
        """
    
    def _get_authority_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'AuthorityShape',
            targetClass: 'Authority',
            description: 'Validation for Authority nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'name',
            minCount: 1,
            datatype: 'xsd:string'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop2:SHACLProperty {
            path: 'id',
            minCount: 1,
            datatype: 'xsd:string'
        })
        """
    
    def _get_document_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'DocumentShape',
            targetClass: 'Document',
            description: 'Validation for Document nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'title',
            minCount: 1,
            datatype: 'xsd:string'
        })
        """
    
    def _get_visa_policy_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'VisaPolicyShape',
            targetClass: 'VisaPolicy',
            description: 'Validation for VisaPolicy nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'policy',
            minCount: 1,
            datatype: 'xsd:string'
        })
        """
    
    def _get_visa_type_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'VisaTypeShape',
            targetClass: 'VisaType',
            description: 'Validation for VisaType nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'name',
            minCount: 1,
            datatype: 'xsd:string'
        })
        """
    
    def _get_holiday_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'HolidayShape',
            targetClass: 'Holiday',
            description: 'Validation for Holiday nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'title',
            minCount: 1,
            datatype: 'xsd:string'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop2:SHACLProperty {
            path: 'date',
            datatype: 'xsd:date'
        })
        """
    
    def _get_project_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'ProjectShape',
            targetClass: 'Project',
            description: 'Validation for Project nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'title',
            minCount: 1,
            datatype: 'xsd:string'
        })
        """
    
    def _get_news_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'NewsShape',
            targetClass: 'News',
            description: 'Validation for News nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'title',
            minCount: 1,
            datatype: 'xsd:string'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop2:SHACLProperty {
            path: 'publishedDate',
            datatype: 'xsd:dateTime'
        })
        """
    
    def _get_domain_shape(self) -> str:
        return """
        CREATE (shape:SHACLShape {
            name: 'DomainShape',
            targetClass: 'Domain',
            description: 'Validation for Domain nodes'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop1:SHACLProperty {
            path: 'name',
            minCount: 1,
            datatype: 'xsd:string'
        })
        MERGE (shape)-[:HAS_PROPERTY]->(prop2:SHACLProperty {
            path: 'description',
            datatype: 'xsd:string'
        })
        """
    
    def validate_all(self) -> dict:
        """Run validation for all entity types."""
        results = {}
        
        # Get all labels from database
        with self.driver.session() as session:
            labels_result = session.run("CALL db.labels()")
            labels = [record["label"] for record in labels_result]
            
            for label in labels:
                try:
                    # Count total nodes
                    count_result = session.run(f"MATCH (n:`{label}`) RETURN count(n) as count")
                    total_count = count_result.single()["count"]
                    
                    # Check for required properties (basic validation)
                    violations = []
                    
                    # Check for nodes missing common required properties
                    if label in ["Province", "District", "City", "Attraction", "Holiday", "News", "Project"]:
                        # Check for name/title
                        name_check = session.run(f"""
                            MATCH (n:`{label}`)
                            WHERE (n.name IS NULL OR n.name = '') 
                              AND (n.title IS NULL OR n.title = '')
                            RETURN count(n) as missing_count
                        """)
                        missing = name_check.single()["missing_count"]
                        
                        if missing > 0:
                            violations.append({
                                "severity": "error",
                                "message": f"{missing} {label} nodes missing name/title",
                                "count": missing
                            })
                    
                    results[label] = {
                        "total_nodes": total_count,
                        "violations": violations,
                        "conforms": len(violations) == 0
                    }
                    
                except Exception as e:
                    results[label] = {
                        "error": str(e)
                    }
        
        return results


def main():
    """Install and test SHACL shapes."""
    from neo4j import GraphDatabase
    
    NEO4J_URI = "bolt://127.0.0.1:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "password"  # UPDATE THIS!
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    print("=" * 70)
    print("🔍 SHACL VALIDATION SYSTEM")
    print("=" * 70)
    
    shacl = ComprehensiveSHACLShapes(driver)
    
    print("\n📝 Installing SHACL shapes...")
    install_results = shacl.install_all_shapes()
    
    for shape, status in install_results.items():
        if status == "installed":
            print(f"  ✓ {shape}")
        else:
            print(f"  ✗ {shape}: {status}")
    
    print("\n🔍 Running validation...")
    validation_results = shacl.validate_all()
    
    print("\n" + "=" * 70)
    print("VALIDATION REPORT")
    print("=" * 70)
    
    total_conforming = 0
    total_violations = 0
    
    for label, result in validation_results.items():
        if "error" in result:
            print(f"\n❌ {label}: ERROR - {result['error']}")
            continue
        
        violations = result.get("violations", [])
        conforms = result.get("conforms", True)
        
        if conforms:
            print(f"\n✓ {label}: VALID ({result['total_nodes']} nodes)")
            total_conforming += 1
        else:
            print(f"\n✗ {label}: VIOLATIONS ({result['total_nodes']} nodes)")
            total_violations += len(violations)
            for violation in violations:
                print(f"    - {violation['message']}")
    
    print("\n" + "=" * 70)
    print(f"Summary: {total_conforming} valid / {len(validation_results)} total entity types")
    print(f"Total violations: {total_violations}")
    print("=" * 70)
    
    driver.close()


if __name__ == "__main__":
    main()
