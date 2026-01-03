"""
Hotel Ingestion Script

Quick script to ingest hotels from JSON into Neo4j
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.hotel_ingestion_service import HotelIngestionService


def main():
    """Run hotel ingestion"""
    # Default path from project root
    json_file = Path(__file__).parent.parent.parent.parent / "data" / "kg_service" / "data" / "hotels.json"
    
    if len(sys.argv) > 1:
        json_file = Path(sys.argv[1])
    
    if not json_file.exists():
        print(f"❌ Error: File not found: {json_file}")
        print(f"\nUsage: python ingest_hotels.py [path/to/hotels.json]")
        sys.exit(1)
    
    print("="*80)
    print("🏨 HOTEL INGESTION SCRIPT")
    print("="*80)
    print(f"\n📁 Input file: {json_file}")
    print(f"📊 This will:")
    print(f"   • Create Hotel nodes")
    print(f"   • Create NEAR_ATTRACTION relationships")
    print(f"   • Create geographic relationships")
    print(f"   • Create POI and Amenity nodes")
    print(f"   • Calculate distances")
    
    response = input(f"\n❓ Continue with ingestion? (y/n): ")
    
    if response.lower() != 'y':
        print("❌ Ingestion cancelled")
        sys.exit(0)
    
    print("\n🚀 Starting ingestion...\n")
    
    # Initialize service
    service = HotelIngestionService()
    
    try:
        # Run ingestion
        results = service.ingest_from_json_file(str(json_file))
        
        # Final summary
        print("\n" + "="*80)
        print("✅ INGESTION COMPLETE")
        print("="*80)
        print(f"\n📊 Results:")
        print(f"   • Attractions processed: {results['total_attractions']}")
        print(f"   • Hotels created: {results['total_hotels_created']}")
        print(f"   • Relationships: {results['total_relationships']}")
        print(f"   • POIs: {results['total_pois']}")
        print(f"   • Amenities: {results['total_amenities']}")
        print(f"   • Errors: {results['total_errors']}")
        print(f"   • Time: {results['total_time_seconds']:.2f}s")
        
        print("\n💡 Next steps:")
        print("   1. Test the API: http://localhost:8000/hotels/")
        print("   2. Run GNN training with new hotel nodes")
        print("   3. Query hotels near attractions")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        service.close()


if __name__ == "__main__":
    main()
