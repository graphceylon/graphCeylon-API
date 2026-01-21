"""Script to delete and reload attractions with updated schema."""

import requests
import json

BASE_URL = "http://localhost:8000"

def delete_all_attractions():
    """Delete all attraction nodes."""
    print("Deleting all existing attractions...")
    
    # Use the query endpoint with raw cypher
    payload = {
        "query": "MATCH (a:Attraction) DETACH DELETE a"
    }
    
    response = requests.post(f"{BASE_URL}/kg/query", json=payload)
    if response.status_code == 200:
        print("✅ Successfully deleted attractions")
    else:
        print(f"❌ Failed to delete attractions: {response.status_code}")
        print(response.text)
    
    return response.status_code == 200

def reload_attractions():
    """Reload attractions with new schema."""
    print("\nReloading attractions with updated schema...")
    
    response = requests.post(f"{BASE_URL}/attractions/initialize")
    if response.status_code == 200:
        print("✅ Successfully reloaded attractions")
        result = response.json()
        print(f"   - Loaded: {result['data']['attractions_loaded']} attractions")
        print(f"   - Skipped: {result['data']['skipped']} attractions")
        print(f"   - Total in DB: {result['data']['statistics']['total_attractions']}")
    else:
        print(f"❌ Failed to reload attractions: {response.status_code}")
        print(response.text)
    
    return response.status_code == 200

def verify_attractions():
    """Verify loaded attractions have all fields."""
    print("\nVerifying attraction data...")
    
    response = requests.get(f"{BASE_URL}/attractions?limit=1")
    if response.status_code == 200:
        data = response.json()
        if data['attractions']:
            attraction = data['attractions'][0]
            print(f"✅ Sample attraction: {attraction['title']}")
            print(f"   - Image URL: {'✓' if attraction.get('imageUrl') else '✗'}")
            print(f"   - Coordinates: {'✓' if attraction.get('latitude') else '✗'}")
            print(f"   - District: {'✓' if attraction.get('district') else '✗'}")
            print(f"   - Website: {'✓' if attraction.get('website') else '✗'}")
            print(f"   - Links: {'✓' if attraction.get('links') else '✗'}")
            print(f"   - Google Maps URL: {'✓' if attraction.get('googleMapsUrl') else '✗'}")
            print(f"   - Formatted Address: {'✓' if attraction.get('formattedAddress') else '✗'}")
            print("\nFull data:")
            print(json.dumps(attraction, indent=2))
        else:
            print("⚠️ No attractions found")
    else:
        print(f"❌ Failed to verify: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    print("=" * 60)
    print("ATTRACTIONS RELOAD SCRIPT")
    print("=" * 60)
    
    # Step 1: Delete existing attractions
    if delete_all_attractions():
        # Step 2: Reload with new schema
        if reload_attractions():
            # Step 3: Verify
            verify_attractions()
    
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
