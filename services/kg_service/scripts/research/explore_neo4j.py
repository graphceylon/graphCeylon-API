"""
Neo4j Database Explorer

Discovers all node labels, relationship types, properties, and statistics
in your knowledge graph to understand the complete schema.
"""

from neo4j import GraphDatabase
from typing import Dict, List, Any
import json
from datetime import datetime

# Neo4j connection
NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # UPDATE THIS!


class Neo4jExplorer:
    """Explore and analyze Neo4j database schema and content."""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
    def close(self):
        self.driver.close()
    
    def get_all_labels(self) -> List[str]:
        """Get all node labels in the database."""
        with self.driver.session() as session:
            result = session.run("CALL db.labels()")
            return [record["label"] for record in result]
    
    def get_all_relationship_types(self) -> List[str]:
        """Get all relationship types in the database."""
        with self.driver.session() as session:
            result = session.run("CALL db.relationshipTypes()")
            return [record["relationshipType"] for record in result]
    
    def get_label_counts(self) -> Dict[str, int]:
        """Count nodes for each label."""
        labels = self.get_all_labels()
        counts = {}
        
        with self.driver.session() as session:
            for label in labels:
                result = session.run(f"MATCH (n:`{label}`) RETURN count(n) as count")
                counts[label] = result.single()["count"]
        
        return counts
    
    def get_relationship_counts(self) -> Dict[str, int]:
        """Count relationships for each type."""
        rel_types = self.get_all_relationship_types()
        counts = {}
        
        with self.driver.session() as session:
            for rel_type in rel_types:
                result = session.run(f"MATCH ()-[r:`{rel_type}`]->() RETURN count(r) as count")
                counts[rel_type] = result.single()["count"]
        
        return counts
    
    def get_properties_for_label(self, label: str) -> Dict[str, Any]:
        """Get all properties and their sample values for a label."""
        with self.driver.session() as session:
            # Get all property keys
            result = session.run(f"""
                MATCH (n:`{label}`)
                UNWIND keys(n) AS key
                RETURN DISTINCT key
                LIMIT 1000
            """)
            properties = [record["key"] for record in result]
            
            # Get sample values
            sample_values = {}
            for prop in properties:
                result = session.run(f"""
                    MATCH (n:`{label}`)
                    WHERE n.`{prop}` IS NOT NULL
                    RETURN DISTINCT n.`{prop}` as value
                    LIMIT 5
                """)
                values = [record["value"] for record in result]
                sample_values[prop] = values
            
            return sample_values
    
    def get_relationship_patterns(self) -> List[Dict[str, str]]:
        """Get all relationship patterns (source label -> rel type -> target label)."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a)-[r]->(b)
                WITH labels(a) as source_labels, type(r) as rel_type, labels(b) as target_labels
                UNWIND source_labels as source
                UNWIND target_labels as target
                RETURN DISTINCT source, rel_type, target
                ORDER BY source, rel_type, target
            """)
            
            patterns = []
            for record in result:
                patterns.append({
                    "source": record["source"],
                    "relationship": record["rel_type"],
                    "target": record["target"]
                })
            
            return patterns
    
    def get_sample_nodes(self, label: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Get sample nodes for a label."""
        with self.driver.session() as session:
            result = session.run(f"""
                MATCH (n:`{label}`)
                RETURN n
                LIMIT {limit}
            """)
            
            samples = []
            for record in result:
                node = dict(record["n"])
                samples.append(node)
            
            return samples
    
    def generate_full_report(self) -> Dict[str, Any]:
        """Generate comprehensive database report."""
        print("🔍 Exploring Neo4j Database...")
        print("=" * 70)
        
        # Get all labels
        print("\n📊 Fetching node labels...")
        labels = self.get_all_labels()
        label_counts = self.get_label_counts()
        
        print(f"✓ Found {len(labels)} node labels")
        
        # Get all relationship types
        print("\n🔗 Fetching relationship types...")
        rel_types = self.get_all_relationship_types()
        rel_counts = self.get_relationship_counts()
        
        print(f"✓ Found {len(rel_types)} relationship types")
        
        # Get relationship patterns
        print("\n🔄 Analyzing relationship patterns...")
        patterns = self.get_relationship_patterns()
        
        print(f"✓ Found {len(patterns)} unique patterns")
        
        # Get properties for each label
        print("\n📝 Analyzing properties for each label...")
        label_properties = {}
        label_samples = {}
        
        for label in labels:
            print(f"  - Analyzing '{label}'...")
            label_properties[label] = self.get_properties_for_label(label)
            label_samples[label] = self.get_sample_nodes(label, limit=2)
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_labels": len(labels),
                "total_relationship_types": len(rel_types),
                "total_nodes": sum(label_counts.values()),
                "total_relationships": sum(rel_counts.values()),
                "unique_patterns": len(patterns)
            },
            "labels": {
                label: {
                    "count": label_counts.get(label, 0),
                    "properties": label_properties.get(label, {}),
                    "sample_nodes": label_samples.get(label, [])
                }
                for label in sorted(labels)
            },
            "relationships": {
                rel_type: rel_counts.get(rel_type, 0)
                for rel_type in sorted(rel_types)
            },
            "patterns": patterns
        }
        
        return report
    
    def print_report(self, report: Dict[str, Any]):
        """Print human-readable report."""
        print("\n" + "=" * 70)
        print("📋 NEO4J DATABASE REPORT")
        print("=" * 70)
        
        # Summary
        summary = report["summary"]
        print(f"\n🎯 SUMMARY:")
        print(f"  Total Node Labels: {summary['total_labels']}")
        print(f"  Total Nodes: {summary['total_nodes']:,}")
        print(f"  Total Relationship Types: {summary['total_relationship_types']}")
        print(f"  Total Relationships: {summary['total_relationships']:,}")
        print(f"  Unique Patterns: {summary['unique_patterns']}")
        
        # Node Labels
        print(f"\n📊 NODE LABELS:")
        print("  " + "-" * 66)
        print(f"  {'Label':<30} {'Count':>10} {'Properties':>10}")
        print("  " + "-" * 66)
        
        for label, info in report["labels"].items():
            prop_count = len(info["properties"])
            print(f"  {label:<30} {info['count']:>10,} {prop_count:>10}")
        
        # Relationship Types
        print(f"\n🔗 RELATIONSHIP TYPES:")
        print("  " + "-" * 66)
        print(f"  {'Type':<40} {'Count':>20}")
        print("  " + "-" * 66)
        
        for rel_type, count in report["relationships"].items():
            print(f"  {rel_type:<40} {count:>20,}")
        
        # Top Patterns
        print(f"\n🔄 RELATIONSHIP PATTERNS (showing first 20):")
        print("  " + "-" * 66)
        
        for i, pattern in enumerate(report["patterns"][:20]):
            print(f"  {pattern['source']} --[{pattern['relationship']}]--> {pattern['target']}")
        
        if len(report["patterns"]) > 20:
            print(f"  ... and {len(report['patterns']) - 20} more patterns")
        
        # Detailed Properties
        print(f"\n📝 DETAILED PROPERTY ANALYSIS:")
        print("  " + "=" * 66)
        
        for label, info in report["labels"].items():
            if info["properties"]:
                print(f"\n  📌 {label} ({info['count']} nodes)")
                print("  " + "-" * 66)
                
                for prop, values in info["properties"].items():
                    value_str = ", ".join([str(v)[:30] for v in values[:3]])
                    if len(values) > 3:
                        value_str += "..."
                    print(f"    • {prop}: {value_str}")
                
                # Show sample node
                if info["sample_nodes"]:
                    print(f"\n    Sample node:")
                    sample = info["sample_nodes"][0]
                    for key, value in list(sample.items())[:5]:
                        print(f"      {key}: {str(value)[:60]}")
        
        print("\n" + "=" * 70)


def main():
    print("=" * 70)
    print("🔍 NEO4J DATABASE EXPLORER")
    print("=" * 70)
    
    explorer = Neo4jExplorer(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # Test connection
        with explorer.driver.session() as session:
            session.run("RETURN 1").single()
        print("✓ Connected to Neo4j successfully\n")
        
        # Generate report
        report = explorer.generate_full_report()
        
        # Print report
        explorer.print_report(report)
        
        # Save to JSON
        output_file = "neo4j_schema_report.json"
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n💾 Full report saved to: {output_file}")
        print("\n💡 Next Steps:")
        print("  1. Review the schema above")
        print("  2. I'll create SHACL shapes for all node types")
        print("  3. Update GNN training to include all entity types")
        print("  4. Enhance API endpoints for new entity types")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        explorer.close()


if __name__ == "__main__":
    main()
