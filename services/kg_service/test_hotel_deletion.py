"""
Test script for Hotel Deletion API endpoints

Demonstrates how to delete hotels manually through the API:
1. Delete a specific hotel by ID
2. Delete all hotels for an attraction
3. Clear all hotel data (with confirmation)
"""

import requests
import json

BASE_URL = "http://localhost:8000"
HOTEL_URL = f"{BASE_URL}/hotels"


def print_response(title: str, response: requests.Response):
    """Pretty print API response"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")
    print(f"Status: {response.status_code}")
    
    if response.status_code in [200, 404, 400]:
        try:
            data = response.json()
            print(json.dumps(data, indent=2))
        except:
            print(response.text)
    else:
        print(f"Error: {response.text}")
    print(f"{'='*80}\n")


def test_delete_single_hotel():
    """Test 1: Delete a specific hotel by ID"""
    print("\n" + "="*80)
    print("TEST 1: Delete Single Hotel")
    print("="*80)
    
    # First, get a hotel ID to delete (get the test hotel we created)
    response = requests.get(f"{HOTEL_URL}/", params={"limit": 200})
    
    if response.status_code == 200:
        hotels = response.json().get("hotels", [])
        
        # Find the test hotel we created earlier
        test_hotel = None
        for hotel in hotels:
            if "Test Integration Hotel" in hotel.get("name", ""):
                test_hotel = hotel
                break
        
        if test_hotel:
            hotel_id = test_hotel.get("hotel_id")
            hotel_name = test_hotel.get("name")
            
            print(f"\n🎯 Found test hotel to delete:")
            print(f"   ID: {hotel_id}")
            print(f"   Name: {hotel_name}")
            
            # Delete the hotel
            delete_response = requests.delete(f"{HOTEL_URL}/{hotel_id}")
            print_response(f"Delete Hotel: {hotel_name}", delete_response)
            
            # Verify deletion
            verify_response = requests.get(f"{HOTEL_URL}/{hotel_id}")
            if verify_response.status_code == 404:
                print("✅ Hotel successfully deleted (404 on GET)")
            else:
                print("⚠️  Hotel may still exist")
        else:
            print("\n⚠️  No test hotel found to delete. Creating one first...")
            print("   Run: test_hotel_endpoints.py to create test hotel")
    else:
        print("❌ Failed to fetch hotel list")


def test_delete_by_attraction():
    """Test 2: Delete all hotels for a specific attraction"""
    print("\n" + "="*80)
    print("TEST 2: Delete Hotels by Attraction")
    print("="*80)
    
    # First check which attractions have hotels
    stats_response = requests.get(f"{HOTEL_URL}/statistics/overview")
    
    if stats_response.status_code == 200:
        stats = stats_response.json()
        coverage = stats.get("coverage_map", {})
        
        # Find an attraction with exactly 1 hotel (safest to delete)
        single_hotel_attractions = [
            attr for attr, hotels in coverage.items() 
            if len(hotels) == 1
        ]
        
        if single_hotel_attractions:
            test_attraction = single_hotel_attractions[0]
            print(f"\n🎯 Testing deletion for: {test_attraction}")
            print(f"   (Has 1 hotel - safe for demo)")
            
            # Attempt without confirmation (should fail)
            response = requests.delete(
                f"{HOTEL_URL}/attraction/{test_attraction}"
            )
            print_response("Delete Without Confirmation (Should Fail)", response)
            
            # Now with confirmation
            response = requests.delete(
                f"{HOTEL_URL}/attraction/{test_attraction}",
                params={"confirm": True}
            )
            print_response(f"Delete Hotels for {test_attraction} (Confirmed)", response)
        else:
            print("\n⚠️  No single-hotel attractions found for safe demo")
    else:
        print("❌ Failed to fetch statistics")


def test_clear_all_hotels():
    """Test 3: Clear all hotel data (DANGEROUS - requires confirmation)"""
    print("\n" + "="*80)
    print("TEST 3: Clear All Hotels (DEMO ONLY - NOT EXECUTED)")
    print("="*80)
    
    print("\n⚠️  WARNING: This endpoint deletes ALL hotel data!")
    print("\nTo execute this dangerous operation, uncomment the code below.")
    print("\nAPI Usage:")
    print(f"   DELETE {HOTEL_URL}/clear?confirm=true")
    
    # Uncomment to actually test (DANGER!)
    # response = requests.delete(f"{HOTEL_URL}/clear", params={"confirm": True})
    # print_response("Clear All Hotels", response)
    
    print("\n✅ Test skipped for safety")


def demonstrate_api_usage():
    """Show example API calls"""
    print("\n" + "="*80)
    print("HOTEL DELETION API - USAGE EXAMPLES")
    print("="*80)
    
    examples = [
        {
            "title": "Delete Single Hotel",
            "method": "DELETE",
            "url": f"{HOTEL_URL}/hotel_royal_retreat_kandy",
            "description": "Removes specific hotel by ID"
        },
        {
            "title": "Delete Hotels by Attraction",
            "method": "DELETE",
            "url": f"{HOTEL_URL}/attraction/Colombo?confirm=true",
            "description": "Removes all hotels for an attraction (requires confirm=true)"
        },
        {
            "title": "Clear All Hotels",
            "method": "DELETE",
            "url": f"{HOTEL_URL}/clear?confirm=true",
            "description": "⚠️  DANGER: Deletes ALL hotels (requires confirm=true)"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['title']}")
        print(f"   Method: {example['method']}")
        print(f"   URL: {example['url']}")
        print(f"   {example['description']}")


def main():
    """Run deletion tests"""
    print("\n" + "="*80)
    print("HOTEL DELETION API TEST SUITE")
    print("="*80)
    
    try:
        # Show API usage examples
        demonstrate_api_usage()
        
        # Test deletion operations
        print("\n" + "="*80)
        print("RUNNING DELETION TESTS")
        print("="*80)
        
        test_delete_single_hotel()
        
        # Uncomment to test attraction-level deletion
        # test_delete_by_attraction()
        
        # Clear all is intentionally not executed for safety
        test_clear_all_hotels()
        
        print("\n" + "="*80)
        print("DELETION TESTS COMPLETED")
        print("="*80)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to the server.")
        print("Make sure the kg_service is running on http://localhost:8000")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")


if __name__ == "__main__":
    main()
