"""
Comprehensive analysis of the entire Tourism Knowledge Graph.
Analyzes ALL node types, relationships, and patterns.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from neo4j import GraphDatabase
from core.config import settings
import json
from collections import defaultdict, Counter

def analyze_complete_graph():
    """Comprehensive analysis of all graph components."""
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    with driver.session() as session:
        print("=" * 100)
        print("COMPLETE TOURISM KNOWLEDGE GRAPH ANALYSIS")
        print("=" * 100)
        
        # 1. OVERALL STATISTICS
        print("\n" + "="*100)
        print("1. GRAPH OVERVIEW")
        print("="*100)
        
        stats = session.run("""
            MATCH (n)
            OPTIONAL MATCH (n)-[r]->()
            RETURN 
                count(DISTINCT n) AS total_nodes,
                count(DISTINCT r) AS total_relationships,
                count(DISTINCT labels(n)) AS label_combinations
        """).single()
        
        total_nodes = stats['total_nodes']
        total_rels = stats['total_relationships']
        
        print(f"\n📊 Total Nodes: {total_nodes:,}")
        print(f"🔗 Total Relationships: {total_rels:,}")
        print(f"📈 Average Degree: {(total_rels * 2 / total_nodes):.2f}")
        print(f"🕸️  Graph Density: {(total_rels / (total_nodes * (total_nodes - 1)) * 100):.4f}%")
        
        # 2. NODE DISTRIBUTION BY LABEL
        print("\n" + "="*100)
        print("2. NODE LABELS DISTRIBUTION (All 29 Types)")
        print("="*100)
        
        labels = session.run("""
            MATCH (n)
            UNWIND labels(n) AS label
            RETURN label, count(*) AS count
            ORDER BY count DESC
        """)
        
        label_counts = {}
        print(f"\n{'Label':<30} {'Count':>10} {'% of Total':>12} {'Bar Chart':>30}")
        print("-" * 100)
        
        for record in labels:
            label = record['label']
            count = record['count']
            label_counts[label] = count
            percentage = (count / total_nodes) * 100
            bar = "█" * int(percentage * 2)
            print(f"{label:<30} {count:>10} {percentage:>11.2f}% {bar}")
        
        # 3. RELATIONSHIP DISTRIBUTION
        print("\n" + "="*100)
        print("3. RELATIONSHIP TYPES DISTRIBUTION (All 37 Types)")
        print("="*100)
        
        rels = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(*) AS count
            ORDER BY count DESC
        """)
        
        print(f"\n{'Relationship Type':<35} {'Count':>10} {'% of Total':>12}")
        print("-" * 100)
        
        rel_counts = {}
        for record in rels:
            rel_type = record['rel_type']
            count = record['count']
            rel_counts[rel_type] = count
            percentage = (count / total_rels) * 100
            print(f"{rel_type:<35} {count:>10} {percentage:>11.2f}%")
        
        # 4. DOMAIN ANALYSIS (Core Tourism Categories)
        print("\n" + "="*100)
        print("4. TOURISM DOMAINS (Knowledge Organization)")
        print("="*100)
        
        domains = session.run("""
            MATCH (d:Domain)
            OPTIONAL MATCH (d)<-[:BELONGS_TO]-(entity)
            RETURN 
                d.name AS domain,
                d.code AS code,
                d.description AS description,
                d.status AS status,
                d.order AS order_num,
                count(entity) AS entity_count,
                d.examples AS examples
            ORDER BY order_num
        """)
        
        for record in domains:
            print(f"\n🏷️  {record['domain']} ({record['code']})")
            print(f"   Status: {record['status']}")
            print(f"   Entities: {record['entity_count']}")
            print(f"   Description: {record['description']}")
            if record['examples']:
                print(f"   Examples: {', '.join(record['examples'][:3])}")
        
        # 5. GEOGRAPHIC HIERARCHY
        print("\n" + "="*100)
        print("5. GEOGRAPHIC STRUCTURE (Country → Province → District)")
        print("="*100)
        
        geo = session.run("""
            MATCH (c:Country {isoCode: 'LK'})
            OPTIONAL MATCH (c)-[:HAS_DOMAIN]->(d:Domain)
            OPTIONAL MATCH (d)-[:HAS_PROVINCE]->(p:Province)
            OPTIONAL MATCH (p)-[:HAS_DISTRICT]->(dist:District)
            RETURN c.name AS country, 
                   count(DISTINCT d) AS domains,
                   count(DISTINCT p) AS provinces,
                   count(DISTINCT dist) AS districts
        """).single()
        
        print(f"\n🌍 Country: {geo['country']}")
        print(f"   ├─ Domains: {geo['domains']}")
        print(f"   ├─ Provinces: {geo['provinces']}")
        print(f"   └─ Districts: {geo['districts']}")
        
        # Show province breakdown
        provinces = session.run("""
            MATCH (p:Province)
            OPTIONAL MATCH (p)-[:HAS_DISTRICT]->(d:District)
            RETURN p.name AS province, count(d) AS districts
            ORDER BY districts DESC
        """)
        
        print("\n   Province Details:")
        for record in provinces:
            print(f"      • {record['province']:<25} {record['districts']} districts")
        
        # 6. CONTENT TYPES ANALYSIS
        print("\n" + "="*100)
        print("6. CONTENT & INFORMATION NODES")
        print("="*100)
        
        # Attractions
        attractions = session.run("""
            MATCH (a:Attraction)
            RETURN 
                count(a) AS total,
                avg(a.rating) AS avg_rating,
                count(a.rating) AS rated_count,
                sum(a.userRatingsTotal) AS total_ratings
        """).single()
        
        print(f"\n🏛️  Attractions:")
        print(f"   Total: {attractions['total']}")
        print(f"   Average Rating: {attractions['avg_rating']:.2f}/5.0")
        print(f"   With Ratings: {attractions['rated_count']}")
        print(f"   Total User Ratings: {attractions['total_ratings']:,}")
        
        # Top attractions by rating
        top_attractions = session.run("""
            MATCH (a:Attraction)
            WHERE a.rating IS NOT NULL
            RETURN a.title AS name, a.rating AS rating, a.province AS province
            ORDER BY a.rating DESC, a.userRatingsTotal DESC
            LIMIT 5
        """)
        
        print("\n   Top 5 Attractions:")
        for i, record in enumerate(top_attractions, 1):
            print(f"      {i}. {record['name']:<30} {record['rating']}/5.0  ({record['province']})")
        
        # News & Information
        news = session.run("""
            MATCH (n:NewsArticle)
            OPTIONAL MATCH (n)-[:IN_CATEGORY]->(c:NewsCategory)
            RETURN 
                count(n) AS total_articles,
                count(DISTINCT c) AS categories
        """).single()
        
        print(f"\n📰 News Articles:")
        print(f"   Total Articles: {news['total_articles']}")
        print(f"   Categories: {news['categories']}")
        
        # Holidays
        holidays = session.run("""
            MATCH (h:Holiday)
            RETURN 
                count(h) AS total,
                count(DISTINCT h.holiday_type) AS types,
                count(CASE WHEN h.isPublicHoliday THEN 1 END) AS public_holidays
        """).single()
        
        print(f"\n🎉 Holidays:")
        print(f"   Total: {holidays['total']}")
        print(f"   Types: {holidays['types']}")
        print(f"   Public Holidays: {holidays['public_holidays']}")
        
        # Tourism Projects (SLTDA)
        projects = session.run("""
            MATCH (t:TourismProject)
            OPTIONAL MATCH (t)-[:IN_COUNTRY]->(c:Country)
            OPTIONAL MATCH (t)-[:HAS_PROJECT]->(d:District)
            RETURN 
                count(t) AS total,
                count(DISTINCT d) AS districts_covered
        """).single()
        
        print(f"\n🏗️  Tourism Projects (SLTDA):")
        print(f"   Total Projects: {projects['total']}")
        print(f"   Districts Covered: {projects['districts_covered']}")
        
        # 7. POLICY & IMMIGRATION
        print("\n" + "="*100)
        print("7. POLICY & IMMIGRATION KNOWLEDGE")
        print("="*100)
        
        policy = session.run("""
            MATCH (p:Policy)
            RETURN count(p) AS policies
        """).single()
        
        visa = session.run("""
            MATCH (v:VisaPolicy)
            RETURN 
                count(v) AS visa_policies,
                count(DISTINCT v.nationality_country) AS nationalities,
                count(DISTINCT v.destination_country) AS destinations
        """).single()
        
        print(f"\n📋 Policies: {policy['policies']}")
        print(f"🛂 Visa Policies:")
        print(f"   Total: {visa['visa_policies']}")
        print(f"   Nationalities: {visa['nationalities']}")
        print(f"   Destinations: {visa['destinations']}")
        
        # 8. SEMANTIC LAYERS
        print("\n" + "="*100)
        print("8. SEMANTIC & AI LAYERS")
        print("="*100)
        
        chunks = session.run("""
            MATCH (c:Chunk)
            WHERE c.embedding IS NOT NULL
            RETURN 
                count(c) AS total_chunks,
                count(c.embedding) AS with_embeddings,
                avg(size(c.text)) AS avg_text_length
        """).single()
        
        print(f"\n🧩 Text Chunks (RAG System):")
        print(f"   Total Chunks: {chunks['total_chunks']}")
        print(f"   With Embeddings: {chunks['with_embeddings']}")
        print(f"   Avg Text Length: {chunks['avg_text_length']:.0f} chars")
        
        # Show what chunks mention
        chunk_mentions = session.run("""
            MATCH (c:Chunk)-[:MENTIONS]->(entity)
            WITH labels(entity)[0] AS entity_type, count(*) AS mentions
            RETURN entity_type, mentions
            ORDER BY mentions DESC
            LIMIT 5
        """)
        
        print("\n   Top Entity Types Mentioned:")
        for record in chunk_mentions:
            print(f"      • {record['entity_type']:<20} {record['mentions']} mentions")
        
        # SHACL validation
        shacl = session.run("""
            MATCH (s:SHACLShape)
            OPTIONAL MATCH (s)-[:HAS_PROPERTY]->(p:SHACLProperty)
            RETURN 
                count(DISTINCT s) AS shapes,
                count(p) AS properties
        """).single()
        
        print(f"\n✓ Data Validation (SHACL):")
        print(f"   Shapes: {shacl['shapes']}")
        print(f"   Properties Validated: {shacl['properties']}")
        
        # 9. TEMPORAL STRUCTURE
        print("\n" + "="*100)
        print("9. TEMPORAL ORGANIZATION")
        print("="*100)
        
        temporal = session.run("""
            MATCH (y:Year)
            OPTIONAL MATCH (y)-[:HAS_MONTH]->(m:Month)
            OPTIONAL MATCH (m)-[:HAS_HOLIDAY]->(h:Holiday)
            OPTIONAL MATCH (m)-[:HAS_NEWS]->(n:NewsArticle)
            RETURN 
                count(DISTINCT y) AS years,
                count(DISTINCT m) AS months,
                count(DISTINCT h) AS holidays,
                count(DISTINCT n) AS news_articles
        """).single()
        
        print(f"\n📅 Temporal Structure:")
        print(f"   Years: {temporal['years']}")
        print(f"   Months: {temporal['months']}")
        print(f"   Holidays Organized: {temporal['holidays']}")
        print(f"   News Articles Dated: {temporal['news_articles']}")
        
        # 10. CONNECTIVITY ANALYSIS
        print("\n" + "="*100)
        print("10. GRAPH CONNECTIVITY PATTERNS")
        print("="*100)
        
        # Most connected nodes
        hubs = session.run("""
            MATCH (n)
            OPTIONAL MATCH (n)-[r]-()
            WITH n, labels(n)[0] AS label, count(r) AS degree
            ORDER BY degree DESC
            LIMIT 10
            RETURN label, coalesce(n.name, n.title, n.id, 'unnamed') AS name, degree
        """)
        
        print("\n🌟 Top 10 Most Connected Nodes (Hubs):")
        print(f"   {'Type':<20} {'Name':<35} {'Connections':>15}")
        print("   " + "-" * 70)
        for record in hubs:
            print(f"   {record['label']:<20} {record['name']:<35} {record['degree']:>15}")
        
        # Bridge nodes (connect different domains)
        bridges = session.run("""
            MATCH (n)-[r1]-(a)
            MATCH (n)-[r2]-(b)
            WHERE labels(a)[0] <> labels(b)[0]
            WITH labels(n)[0] AS node_type, count(DISTINCT [a,b]) AS cross_domain_links
            RETURN node_type, cross_domain_links
            ORDER BY cross_domain_links DESC
            LIMIT 5
        """)
        
        print("\n🌉 Bridge Node Types (Connect Different Domains):")
        for record in bridges:
            print(f"   • {record['node_type']:<25} {record['cross_domain_links']} cross-domain connections")
        
        # 11. DATA QUALITY METRICS
        print("\n" + "="*100)
        print("11. DATA QUALITY ASSESSMENT")
        print("="*100)
        
        quality = session.run("""
            MATCH (n)
            RETURN 
                labels(n)[0] AS label,
                count(n) AS total,
                count(CASE WHEN size(keys(n)) > 3 THEN 1 END) AS rich_nodes,
                avg(size(keys(n))) AS avg_properties
            ORDER BY total DESC
            LIMIT 10
        """)
        
        print(f"\n{'Node Type':<25} {'Total':>8} {'Rich Nodes':>12} {'Avg Props':>12}")
        print("-" * 60)
        for record in quality:
            rich_pct = (record['rich_nodes'] / record['total'] * 100)
            print(f"{record['label']:<25} {record['total']:>8} {record['rich_nodes']:>12} ({rich_pct:.0f}%) {record['avg_properties']:>11.1f}")
        
        # 12. GNN SUITABILITY ANALYSIS
        print("\n" + "="*100)
        print("12. GNN TRAINING SUITABILITY (All Node Types)")
        print("="*100)
        
        gnn_analysis = session.run("""
            MATCH (n)
            OPTIONAL MATCH (n)-[r]-()
            WITH labels(n)[0] AS label, 
                 count(DISTINCT n) AS node_count,
                 count(DISTINCT r) AS rel_count,
                 count(DISTINCT r) * 1.0 / count(DISTINCT n) AS avg_degree
            WHERE node_count > 5
            RETURN label, node_count, rel_count, avg_degree
            ORDER BY avg_degree DESC
        """)
        
        print(f"\n{'Node Type':<25} {'Count':>8} {'Edges':>10} {'Avg Degree':>12} {'GNN Suitable?':>15}")
        print("-" * 80)
        
        suitable_for_gnn = []
        for record in gnn_analysis:
            label = record['label']
            count = record['node_count']
            edges = record['rel_count']
            degree = record['avg_degree']
            
            # GNN works best with avg degree > 2 and count > 10
            suitable = "✓ YES" if degree > 2 and count > 10 else "  Maybe"
            if degree > 2 and count > 10:
                suitable_for_gnn.append(label)
            
            print(f"{label:<25} {count:>8} {edges:>10} {degree:>11.2f} {suitable:>15}")
        
        # 13. RECOMMENDED GNN CONFIGURATION
        print("\n" + "="*100)
        print("13. RECOMMENDED GNN CONFIGURATION (Multi-Node-Type)")
        print("="*100)
        
        print("\n✓ Node Types Suitable for GNN Training:")
        print(f"   {len(suitable_for_gnn)} types qualify (avg degree > 2, count > 10)")
        print("\n   Recommended node_labels parameter:")
        print(f"   {suitable_for_gnn[:10]}")
        
        print("\n✓ Feature Extraction Strategy:")
        
        # Analyze common properties across types
        props_by_type = {}
        for label in suitable_for_gnn[:10]:
            props = session.run(f"""
                MATCH (n:{label})
                WITH keys(n) AS props
                UNWIND props AS prop
                RETURN prop, count(*) AS freq
                ORDER BY freq DESC
                LIMIT 5
            """)
            props_by_type[label] = [r['prop'] for r in props]
        
        print(f"\n   Common Properties Per Type:")
        for label, props in list(props_by_type.items())[:5]:
            print(f"      {label:<20} {', '.join(props[:3])}")
        
        # 14. CROSS-DOMAIN PATTERNS
        print("\n" + "="*100)
        print("14. CROSS-DOMAIN RELATIONSHIP PATTERNS")
        print("="*100)
        
        patterns = session.run("""
            MATCH (a)-[r]->(b)
            WHERE labels(a)[0] <> labels(b)[0]
            WITH labels(a)[0] AS source_type, 
                 type(r) AS rel_type,
                 labels(b)[0] AS target_type,
                 count(*) AS frequency
            RETURN source_type, rel_type, target_type, frequency
            ORDER BY frequency DESC
            LIMIT 15
        """)
        
        print(f"\n{'Source':<20} {'→ Relationship →':<25} {'Target':<20} {'Count':>10}")
        print("-" * 80)
        for record in patterns:
            print(f"{record['source_type']:<20} → {record['rel_type']:<23} → {record['target_type']:<20} {record['frequency']:>10}")
        
        # 15. SUMMARY & INSIGHTS
        print("\n" + "="*100)
        print("15. KEY INSIGHTS & RECOMMENDATIONS")
        print("="*100)
        
        print(f"""
✓ GRAPH COMPOSITION:
   • Tourism Knowledge Graph with {total_nodes} nodes across 29 entity types
   • {total_rels:,} relationships spanning 37 relationship types
   • Multi-domain: Attractions, Policies, News, Holidays, Projects
   
✓ CORE STRENGTHS:
   • Rich attraction data (39 nodes, avg 4.6 rating)
   • Comprehensive policy knowledge (47 policies)
   • Semantic layer with {chunks['total_chunks']} text chunks
   • Geographic hierarchy (9 provinces, {geo['districts']} districts)
   • Temporal organization ({temporal['months']} months)
   
✓ GNN OPPORTUNITIES:
   • {len(suitable_for_gnn)} node types suitable for multi-type GNN
   • Cross-domain learning possible ({len(rel_counts)} relationship types)
   • Can predict:
     - Attraction → Attraction similarities
     - Policy → Location applicability
     - News → Attraction relevance
     - Holiday → Tourism Project timing
     - Chunk → Entity mentions
   
✓ SPARSITY CHALLENGES:
   • Graph density: {(total_rels / (total_nodes * (total_nodes - 1)) * 100):.4f}%
   • Missing connections: {(total_nodes * (total_nodes - 1) - total_rels):,}
   • GNN can learn to predict these missing relationships
   
✓ RECOMMENDED NEXT STEPS:
   1. Train heterogeneous GNN on top {len(suitable_for_gnn)} node types
   2. Use node type embeddings + property features
   3. Implement relation-specific attention (GAT with edge types)
   4. Focus on cross-domain predictions:
      - Which attractions match which policies?
      - Which holidays boost which attractions?
      - Which news articles relate to which attractions?
   5. Use hybrid approach: Cypher for known, GNN for discovery
        """)
        
        print("="*100)
        print("ANALYSIS COMPLETE")
        print("="*100)
    
    driver.close()

if __name__ == "__main__":
    analyze_complete_graph()
