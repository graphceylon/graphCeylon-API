"""
Inspect Neo4j database schema to understand what's actually in the graph.
This helps configure GNN extraction properly.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from neo4j import GraphDatabase
from core.config import settings
import json

def inspect_database():
    """Inspect Neo4j database schema and content."""
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    with driver.session() as session:
        print("=" * 80)
        print("NEO4J DATABASE INSPECTION")
        print("=" * 80)
        
        # 1. Node Labels
        print("\n1. NODE LABELS:")
        print("-" * 80)
        labels_result = session.run("""
            MATCH (n)
            UNWIND labels(n) AS label
            RETURN label, count(*) AS count
            ORDER BY count DESC
        """)
        
        all_labels = []
        for record in labels_result:
            label = record["label"]
            count = record["count"]
            all_labels.append(label)
            print(f"  {label}: {count} nodes")
        
        # 2. Relationship Types
        print("\n2. RELATIONSHIP TYPES:")
        print("-" * 80)
        rel_result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS relationshipType, count(*) AS count
            ORDER BY count DESC
        """)
        
        for record in rel_result:
            rel_type = record["relationshipType"]
            count = record["count"]
            print(f"  {rel_type}: {count} relationships")
        
        # 3. Sample Nodes from Each Label
        print("\n3. SAMPLE NODES:")
        print("-" * 80)
        
        for label in all_labels[:10]:  # Top 10 labels
            print(f"\n  Label: {label}")
            sample_query = f"""
            MATCH (n:{label})
            RETURN 
                elementId(n) AS id,
                properties(n) AS props,
                labels(n) AS labels
            LIMIT 3
            """
            
            sample_result = session.run(sample_query)
            for i, record in enumerate(sample_result, 1):
                props = record["props"]
                print(f"    Sample {i}:")
                print(f"      ID: {record['id']}")
                print(f"      Labels: {record['labels']}")
                print(f"      Properties: {json.dumps(props, indent=8, default=str)}")
        
        # 4. Property Keys Analysis
        print("\n4. PROPERTY KEYS PER LABEL:")
        print("-" * 80)
        
        for label in all_labels[:10]:
            props_query = f"""
            MATCH (n:{label})
            WITH keys(n) AS propKeys
            UNWIND propKeys AS key
            RETURN DISTINCT key, count(*) AS count
            ORDER BY count DESC
            LIMIT 10
            """
            
            props_result = session.run(props_query)
            print(f"\n  {label}:")
            for record in props_result:
                print(f"    - {record['key']}: {record['count']} nodes")
        
        # 5. Graph Statistics
        print("\n5. GRAPH STATISTICS:")
        print("-" * 80)
        
        stats_query = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]->()
        RETURN 
            count(DISTINCT n) AS total_nodes,
            count(DISTINCT r) AS total_relationships,
            count(DISTINCT labels(n)) AS unique_label_combinations
        """
        
        stats = session.run(stats_query).single()
        print(f"  Total Nodes: {stats['total_nodes']}")
        print(f"  Total Relationships: {stats['total_relationships']}")
        print(f"  Density: {stats['total_relationships'] / (stats['total_nodes'] * (stats['total_nodes'] - 1)) * 100:.4f}%")
        
        # 6. APOC Meta Schema Analysis
        print("\n6. APOC META SCHEMA (Detailed Graph Structure):")
        print("-" * 80)
        
        try:
            apoc_schema = session.run("CALL apoc.meta.schema()").single()
            schema_data = apoc_schema[0] if apoc_schema else {}
            
            print("\n  Node Type Relationships:")
            for label, info in list(schema_data.items())[:15]:  # Show top 15
                if info.get('type') == 'node':
                    print(f"\n  {label} ({info.get('count', 0)} nodes):")
                    
                    # Show properties
                    props = info.get('properties', {})
                    if props:
                        print(f"    Properties:")
                        for prop_name, prop_info in list(props.items())[:10]:
                            prop_type = prop_info.get('type', 'unknown')
                            existence = prop_info.get('existence', 0) * 100
                            print(f"      - {prop_name}: {prop_type} ({existence:.1f}% of nodes)")
                    
                    # Show relationships
                    rels = info.get('relationships', {})
                    if rels:
                        print(f"    Relationships:")
                        for rel_type, rel_info in list(rels.items())[:10]:
                            direction = rel_info.get('direction', 'out')
                            labels_list = rel_info.get('labels', [])
                            arrow = '->' if direction == 'out' else '<-'
                            print(f"      - {arrow} {rel_type} {arrow} {', '.join(labels_list)}")
        except Exception as e:
            print(f"  APOC not available or error: {e}")
        
        # 7. APOC Node Type Properties (Enhanced analysis)
        print("\n7. APOC NODE TYPE PROPERTIES (Type System):")
        print("-" * 80)
        
        try:
            node_props = session.run("""
                CALL apoc.meta.nodeTypeProperties()
                YIELD nodeType, propertyName, propertyTypes, mandatory
                RETURN nodeType, propertyName, propertyTypes, mandatory
                ORDER BY nodeType, mandatory DESC, propertyName
                LIMIT 100
            """)
            
            current_type = None
            for record in node_props:
                node_type = record['nodeType']
                if node_type != current_type:
                    current_type = node_type
                    print(f"\n  {node_type}:")
                
                prop_name = record['propertyName']
                prop_types = record['propertyTypes']
                mandatory = "✓" if record['mandatory'] else " "
                print(f"    [{mandatory}] {prop_name}: {prop_types}")
        except Exception as e:
            print(f"  APOC meta not available: {e}")
        
        # 8. APOC Relationship Type Properties
        print("\n8. APOC RELATIONSHIP TYPE PROPERTIES:")
        print("-" * 80)
        
        try:
            rel_props = session.run("""
                CALL apoc.meta.relTypeProperties()
                YIELD relType, sourceNodeLabels, targetNodeLabels, propertyName, propertyTypes
                RETURN relType, sourceNodeLabels, targetNodeLabels, propertyName, propertyTypes
                ORDER BY relType
                LIMIT 50
            """)
            
            current_rel = None
            for record in rel_props:
                rel_type = record['relType']
                if rel_type != current_rel:
                    current_rel = rel_type
                    src = ', '.join(record['sourceNodeLabels']) if record['sourceNodeLabels'] else 'Any'
                    tgt = ', '.join(record['targetNodeLabels']) if record['targetNodeLabels'] else 'Any'
                    print(f"\n  :{rel_type}")
                    print(f"    From: {src}")
                    print(f"    To: {tgt}")
                    print(f"    Properties:")
                
                if record['propertyName']:
                    prop_name = record['propertyName']
                    prop_types = record['propertyTypes']
                    print(f"      - {prop_name}: {prop_types}")
        except Exception as e:
            print(f"  APOC rel properties not available: {e}")
        
        # 9. n10s Configuration & RDF Data
        print("\n9. N10S (NEOSEMANTICS) ANALYSIS:")
        print("-" * 80)
        
        try:
            # Check n10s config
            n10s_config = session.run("CALL n10s.graphconfig.show()").single()
            if n10s_config:
                print("\n  n10s Configuration Active:")
                config = dict(n10s_config)
                for key, value in config.items():
                    print(f"    {key}: {value}")
            
            # Check for RDF/Resource nodes
            rdf_check = session.run("""
                MATCH (r:Resource)
                RETURN count(r) AS resource_count,
                       collect(DISTINCT labels(r))[0..5] AS sample_labels
            """).single()
            
            if rdf_check and rdf_check['resource_count'] > 0:
                print(f"\n  RDF Resources Found: {rdf_check['resource_count']}")
                print(f"  Sample Labels: {rdf_check['sample_labels']}")
                
                # Show sample RDF properties
                rdf_sample = session.run("""
                    MATCH (r:Resource)
                    RETURN r.uri AS uri, 
                           labels(r) AS labels,
                           properties(r) AS props
                    LIMIT 3
                """)
                
                print("\n  Sample RDF Resources:")
                for record in rdf_sample:
                    print(f"    URI: {record['uri']}")
                    print(f"    Labels: {record['labels']}")
                    print(f"    Props: {json.dumps(record['props'], indent=6, default=str)}")
            else:
                print("\n  No RDF data detected (n10s available but not in use)")
                
        except Exception as e:
            print(f"  n10s not configured: {e}")
        
        # 10. APOC Graph Statistics (Advanced metrics)
        print("\n10. APOC GRAPH STATISTICS:")
        print("-" * 80)
        
        try:
            stats = session.run("""
                CALL apoc.meta.stats()
                YIELD nodeCount, relCount, labelCount, relTypeCount, propertyKeyCount,
                      labels, relTypes
                RETURN nodeCount, relCount, labelCount, relTypeCount, propertyKeyCount,
                       labels, relTypes
            """).single()
            
            print(f"  Total Nodes: {stats['nodeCount']}")
            print(f"  Total Relationships: {stats['relCount']}")
            print(f"  Label Count: {stats['labelCount']}")
            print(f"  Relationship Types: {stats['relTypeCount']}")
            print(f"  Property Keys: {stats['propertyKeyCount']}")
            
            print("\n  Label Distribution:")
            for label, count in sorted(stats['labels'].items(), key=lambda x: x[1], reverse=True)[:15]:
                print(f"    {label}: {count}")
            
            print("\n  Relationship Distribution:")
            for rel, count in sorted(stats['relTypes'].items(), key=lambda x: x[1], reverse=True)[:15]:
                print(f"    {rel}: {count}")
        except Exception as e:
            print(f"  APOC stats not available: {e}")
        
        # 11. Find nodes that might be attractions
        print("\n11. POTENTIAL ATTRACTION NODES:")
        print("-" * 80)
        
        attraction_queries = [
            # Nodes with location or place-like properties
            """
            MATCH (n)
            WHERE n.location IS NOT NULL 
               OR n.latitude IS NOT NULL
               OR n.address IS NOT NULL
            RETURN 
                elementId(n) AS id,
                labels(n) AS labels,
                properties(n) AS props
            LIMIT 5
            """,
            # Nodes with description
            """
            MATCH (n)
            WHERE n.description IS NOT NULL
            RETURN 
                elementId(n) AS id,
                labels(n) AS labels,
                properties(n) AS props
            LIMIT 5
            """,
            # Nodes with rating
            """
            MATCH (n)
            WHERE n.rating IS NOT NULL
            RETURN 
                elementId(n) AS id,
                labels(n) AS labels,
                properties(n) AS props
            LIMIT 5
            """
        ]
        
        for i, query in enumerate(attraction_queries, 1):
            print(f"\n  Query {i} results:")
            result = session.run(query)
            for record in result:
                print(f"    - Labels: {record['labels']}")
                print(f"      Props: {json.dumps(record['props'], indent=8, default=str)}")
        
        # 12. APOC Path Finding Potential
        print("\n12. APOC PATH PATTERNS (Sample Connected Nodes):")
        print("-" * 80)
        
        try:
            # Find interesting paths
            paths = session.run("""
                MATCH path = (a)-[*1..2]-(b)
                WHERE a <> b
                WITH path, length(path) AS len
                ORDER BY len DESC
                LIMIT 5
                RETURN [node in nodes(path) | labels(node)[0]] AS node_labels,
                       [rel in relationships(path) | type(rel)] AS rel_types,
                       len
            """)
            
            print("\n  Sample paths in graph:")
            for i, record in enumerate(paths, 1):
                print(f"    Path {i} (length {record['len']}):")
                print(f"      Nodes: {' -> '.join(record['node_labels'])}")
                print(f"      Rels: {' -> '.join(record['rel_types'])}")
        except Exception as e:
            print(f"  Path analysis error: {e}")
        
        # 13. Suggest GNN Configuration (Updated)
        print("\n13. RECOMMENDED GNN CONFIGURATION:")
        print("-" * 80)
        
        # Find the most common property for identifying nodes
        common_props_query = """
        MATCH (n)
        WITH keys(n) AS propKeys
        UNWIND propKeys AS key
        RETURN key, count(*) AS frequency
        ORDER BY frequency DESC
        LIMIT 5
        """
        
        common_props = session.run(common_props_query)
        print("\n  Most common node properties (use for entity identification):")
        for record in common_props:
            print(f"    - {record['key']}: {record['frequency']} nodes")
        
        # Find labels suitable for GNN training
        print("\n  Recommended node labels for GNN training:")
        suitable_labels = []
        for label in all_labels:
            # Get average degree
            degree_query = f"""
            MATCH (n:{label})
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) AS degree
            RETURN avg(degree) AS avg_degree, count(n) AS count
            """
            result = session.run(degree_query).single()
            avg_degree = result['avg_degree'] or 0
            count = result['count']
            
            # Include if nodes have connections and reasonable count
            if avg_degree > 1 and count > 5:
                suitable_labels.append((label, count, avg_degree))
                print(f"    ✓ {label}: {count} nodes, avg degree {avg_degree:.2f}")
        
        print("\n" + "=" * 80)
        print("INSPECTION COMPLETE")
        print("=" * 80)
        
        # Generate config suggestion
        print("\nSUGGESTED CODE FOR gnn_embeddings.py:")
        print("-" * 80)
        print("# Use these labels for GNN training:")
        print(f"TOURISM_LABELS = {[label for label, _, _ in suitable_labels[:5]]}")
        print("\n# Common properties for entity search:")
        common_search_props = session.run("""
            MATCH (n)
            WHERE n.name IS NOT NULL OR n.title IS NOT NULL OR n.id IS NOT NULL
            WITH CASE 
                WHEN n.name IS NOT NULL THEN 'name'
                WHEN n.title IS NOT NULL THEN 'title'
                WHEN n.id IS NOT NULL THEN 'id'
            END AS prop
            RETURN prop, count(*) AS count
            ORDER BY count DESC
        """)
        print("SEARCH_PROPERTIES = [")
        for record in common_search_props:
            if record['prop']:
                print(f"    '{record['prop']}',  # {record['count']} nodes")
        print("]")
    
    driver.close()

if __name__ == "__main__":
    inspect_database()
