"""
Semantic Web API Endpoints
RDF/OWL/SHACL operations using n10s (Neo4j Semantics)

This module provides REST API endpoints for semantic web operations:
- RDF import/export
- SPARQL-style queries
- SHACL validation
- Ontology reasoning
- Semantic data integration
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

from database.manager import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/semantic", tags=["Semantic Web"])


# ============================================================================
# Pydantic Models
# ============================================================================

class RDFFormat(str, Enum):
    """Supported RDF serialization formats"""
    TURTLE = "Turtle"
    NTRIPLES = "N-Triples"
    RDFXML = "RDF/XML"
    JSONLD = "JSON-LD"
    TRIG = "TriG"


class RDFImportRequest(BaseModel):
    """Request model for RDF import"""
    source: str = Field(..., description="URL or file path to RDF data")
    format: RDFFormat = Field(RDFFormat.TURTLE, description="RDF serialization format")
    commit_size: int = Field(500, description="Batch size for import", ge=1, le=10000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "source": "file:///import/data/lk-admin.ttl",
                "format": "Turtle",
                "commit_size": 500
            }
        }


class RDFExportRequest(BaseModel):
    """Request model for RDF export"""
    cypher_query: str = Field(..., description="Cypher query to select data for export")
    format: RDFFormat = Field(RDFFormat.TURTLE, description="RDF serialization format")
    
    class Config:
        json_schema_extra = {
            "example": {
                "cypher_query": "MATCH (p:Province) RETURN p",
                "format": "Turtle"
            }
        }


class SHACLValidationRequest(BaseModel):
    """Request model for SHACL validation"""
    shapes_source: str = Field(..., description="URL or file path to SHACL shapes")
    format: RDFFormat = Field(RDFFormat.TURTLE, description="SHACL shapes format")
    
    class Config:
        json_schema_extra = {
            "example": {
                "shapes_source": "file:///import/data/lk-shapes.ttl",
                "format": "Turtle"
            }
        }


class NamespaceRequest(BaseModel):
    """Request model for namespace operations"""
    prefix: str = Field(..., description="Namespace prefix")
    uri: str = Field(..., description="Namespace URI")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prefix": "lk",
                "uri": "http://example.org/lk#"
            }
        }


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/config", summary="Get n10s Configuration")
async def get_n10s_config():
    """
    Get current n10s (Neo4j Semantics) configuration.
    
    Returns details about RDF/OWL settings including:
    - Vocabulary URI handling
    - Multi-value handling
    - Neo4j naming conventions
    - Schema namespaces
    
    **Research Significance:**
    This endpoint exposes the semantic web configuration that enables
    RDF/OWL ontology integration and SHACL-based validation.
    """
    try:
        db = DatabaseManager()
        query = "CALL n10s.graphconfig.show()"
        
        result = db.execute_query(query)
        
        if not result or not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="n10s not configured. Run initialization script first."
            )
        
        config = result["data"][0]
        
        return {
            "status": "configured",
            "configuration": config,
            "description": "Neo4j Semantics (n10s) configuration for RDF/OWL support",
            "capabilities": [
                "RDF import/export",
                "SPARQL-style queries",
                "SHACL validation",
                "Ontology reasoning",
                "Semantic data integration"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting n10s config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/rdf", summary="Import RDF Data")
async def import_rdf(request: RDFImportRequest):
    """
    Import RDF data into the knowledge graph.
    
    Supports multiple RDF serialization formats and can import from:
    - File URIs (file:///import/data/...)
    - HTTP/HTTPS URLs
    
    **Research Significance:**
    Enables semantic data integration from external RDF sources,
    allowing the knowledge graph to consume and integrate with
    the broader Linked Open Data ecosystem.
    
    **Example:**
    ```json
    {
        "source": "file:///import/data/lk-admin.ttl",
        "format": "Turtle",
        "commit_size": 500
    }
    ```
    """
    try:
        db = DatabaseManager()
        
        query = f"""
        CALL n10s.rdf.import.fetch(
            '{request.source}',
            '{request.format.value}',
            {{commitSize: {request.commit_size}}}
        )
        """
        
        result = db.execute_query(query)
        
        if result and result.get("data"):
            stats = result["data"][0]
            return {
                "status": "success",
                "source": request.source,
                "format": request.format.value,
                "statistics": {
                    "triples_loaded": stats.get("triplesLoaded", 0),
                    "triples_parsed": stats.get("triplesParsed", 0),
                    "namespaces": stats.get("namespaces", {}),
                    "extra_info": stats.get("extraInfo", "")
                },
                "message": "RDF data imported successfully"
            }
        
        return {"status": "completed", "message": "Import completed"}
        
    except Exception as e:
        logger.error(f"Error importing RDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/rdf", summary="Export Graph as RDF")
async def export_rdf(request: RDFExportRequest):
    """
    Export knowledge graph data as RDF.
    
    Uses Cypher query to select which data to export,
    then serializes it in the specified RDF format.
    
    **Research Significance:**
    Enables knowledge graph data to be shared and integrated
    with other semantic web applications and Linked Open Data
    platforms using standard RDF formats.
    
    **Example:**
    ```json
    {
        "cypher_query": "MATCH (p:Province) RETURN p LIMIT 5",
        "format": "Turtle"
    }
    ```
    """
    try:
        db = DatabaseManager()
        
        query = f"""
        CALL n10s.rdf.export.cypher(
            '{request.cypher_query}',
            {{format: '{request.format.value}'}}
        )
        """
        
        result = db.execute_query(query)
        
        if result and result.get("data"):
            # n10s returns RDF as string in result
            rdf_output = []
            for record in result["data"]:
                if "result" in record:
                    rdf_output.append(record["result"])
            
            return {
                "status": "success",
                "format": request.format.value,
                "rdf_output": "\n".join(rdf_output),
                "triple_count": len(rdf_output),
                "message": "Data exported as RDF successfully"
            }
        
        return {"status": "completed", "rdf_output": "", "message": "No data to export"}
        
    except Exception as e:
        logger.error(f"Error exporting RDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate/shacl", summary="SHACL Validation")
async def validate_shacl(request: SHACLValidationRequest):
    """
    Validate knowledge graph against SHACL shapes.
    
    SHACL (Shapes Constraint Language) is a W3C standard for
    validating RDF graphs against a set of constraints.
    
    **Research Significance:**
    Provides automated validation of data quality and consistency
    against formally defined ontological constraints, ensuring
    the knowledge graph maintains semantic integrity.
    
    **Example:**
    ```json
    {
        "shapes_source": "file:///import/data/lk-shapes.ttl",
        "format": "Turtle"
    }
    ```
    """
    try:
        db = DatabaseManager()
        
        # First import SHACL shapes
        import_query = f"""
        CALL n10s.validation.shacl.import.fetch(
            '{request.shapes_source}',
            '{request.format.value}'
        )
        """
        
        import_result = db.execute_query(import_query)
        
        # Then validate
        validate_query = "CALL n10s.validation.shacl.validate()"
        
        validation_result = db.execute_query(validate_query)
        
        violations = []
        if validation_result and validation_result.get("data"):
            violations = validation_result["data"]
        
        return {
            "status": "validated",
            "shapes_source": request.shapes_source,
            "validation_result": {
                "is_valid": len(violations) == 0,
                "violation_count": len(violations),
                "violations": violations
            },
            "message": "SHACL validation completed"
        }
        
    except Exception as e:
        logger.error(f"Error in SHACL validation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/namespaces", summary="List RDF Namespaces")
async def list_namespaces():
    """
    List all registered RDF namespaces.
    
    Namespaces are used to abbreviate URIs in RDF data,
    making it more readable and easier to work with.
    
    **Research Significance:**
    Shows integration with standard semantic web vocabularies
    (OWL, RDFS, SHACL) and custom ontologies for Sri Lankan data.
    """
    try:
        db = DatabaseManager()
        query = "CALL n10s.nsprefixes.list()"
        
        result = db.execute_query(query)
        
        namespaces = []
        if result and result.get("data"):
            namespaces = result["data"]
        
        return {
            "status": "success",
            "namespace_count": len(namespaces),
            "namespaces": namespaces,
            "description": "Registered RDF namespace prefixes"
        }
        
    except Exception as e:
        logger.error(f"Error listing namespaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/namespaces", summary="Add RDF Namespace")
async def add_namespace(request: NamespaceRequest):
    """
    Add a new RDF namespace prefix.
    
    Namespaces allow shortening of URIs, e.g.:
    - `owl:Class` instead of `http://www.w3.org/2002/07/owl#Class`
    
    **Research Significance:**
    Enables integration with domain-specific ontologies and
    vocabularies by registering their namespace prefixes.
    """
    try:
        db = DatabaseManager()
        
        query = f"""
        CALL n10s.nsprefixes.add('{request.prefix}', '{request.uri}')
        """
        
        result = db.execute_query(query)
        
        return {
            "status": "success",
            "prefix": request.prefix,
            "uri": request.uri,
            "message": f"Namespace '{request.prefix}' added successfully"
        }
        
    except Exception as e:
        logger.error(f"Error adding namespace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/namespaces/{prefix}", summary="Remove RDF Namespace")
async def remove_namespace(prefix: str):
    """
    Remove an RDF namespace prefix.
    
    **Note:** Some standard namespaces (owl, rdfs, rdf) may not be removable.
    """
    try:
        db = DatabaseManager()
        
        query = f"CALL n10s.nsprefixes.remove('{prefix}')"
        
        result = db.execute_query(query)
        
        return {
            "status": "success",
            "prefix": prefix,
            "message": f"Namespace '{prefix}' removed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error removing namespace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/info", summary="Get Ontology Information")
async def get_ontology_info():
    """
    Get information about loaded ontologies and their structure.
    
    **Research Significance:**
    Provides insights into the semantic structure of the knowledge graph,
    showing classes, properties, and relationships defined by ontologies.
    """
    try:
        db = DatabaseManager()
        
        # Get class hierarchy
        class_query = """
        MATCH (c:Class)
        OPTIONAL MATCH (c)-[:SCO]->(parent:Class)
        RETURN c.name AS class_name, 
               collect(parent.name) AS parent_classes,
               labels(c) AS labels
        ORDER BY c.name
        """
        
        class_result = db.execute_query(class_query)
        
        # Get property definitions
        property_query = """
        MATCH (p:Property)
        OPTIONAL MATCH (p)-[:DOMAIN]->(domain)
        OPTIONAL MATCH (p)-[:RANGE]->(range)
        RETURN p.name AS property_name,
               labels(p) AS property_type,
               collect(DISTINCT domain.name) AS domain_classes,
               collect(DISTINCT range.name) AS range_classes
        ORDER BY p.name
        """
        
        property_result = db.execute_query(property_query)
        
        return {
            "status": "success",
            "ontology_structure": {
                "classes": class_result.get("data", []) if class_result else [],
                "properties": property_result.get("data", []) if property_result else [],
            },
            "description": "Ontology class and property definitions in the knowledge graph"
        }
        
    except Exception as e:
        logger.error(f"Error getting ontology info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities", summary="List Semantic Web Capabilities")
async def get_capabilities():
    """
    List all available semantic web capabilities and procedures.
    
    **Research Significance:**
    Demonstrates the full range of semantic web operations
    supported by the knowledge graph system.
    """
    try:
        db = DatabaseManager()
        
        query = """
        SHOW PROCEDURES YIELD name, description
        WHERE name STARTS WITH 'n10s'
        RETURN name, description
        ORDER BY name
        """
        
        result = db.execute_query(query)
        
        procedures = []
        if result and result.get("data"):
            procedures = result["data"]
        
        # Categorize procedures
        categories = {
            "rdf": [],
            "validation": [],
            "inference": [],
            "mapping": [],
            "experimental": []
        }
        
        for proc in procedures:
            name = proc.get("name", "")
            if "rdf" in name:
                categories["rdf"].append(proc)
            elif "validation" in name or "shacl" in name:
                categories["validation"].append(proc)
            elif "inference" in name:
                categories["inference"].append(proc)
            elif "mapping" in name:
                categories["mapping"].append(proc)
            elif "experimental" in name:
                categories["experimental"].append(proc)
        
        return {
            "status": "success",
            "total_procedures": len(procedures),
            "capabilities": {
                "rdf_operations": f"{len(categories['rdf'])} procedures",
                "validation": f"{len(categories['validation'])} procedures",
                "inference": f"{len(categories['inference'])} procedures",
                "mapping": f"{len(categories['mapping'])} procedures",
                "experimental": f"{len(categories['experimental'])} procedures"
            },
            "procedures_by_category": categories,
            "description": "n10s (Neo4j Semantics) capabilities for RDF/OWL/SHACL operations"
        }
        
    except Exception as e:
        logger.error(f"Error getting capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))
