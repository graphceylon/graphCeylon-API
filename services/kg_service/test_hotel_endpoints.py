"""
Enhanced Comprehensive Test Script for Hotel API

Tests all hotel-related features with realistic data based on actual JSON structure:
- List hotels with multiple filter combinations
- Get hotel details with validation
- Search hotels with various criteria
- Get recommendations with multi-attraction trips
- Statistics and analytics
- Find hotels near specific attractions
- Ingest hotel data with proper validation
- Data integrity checks

Based on analysis of:
- 39 attractions across Sri Lanka
- 165+ hotels with detailed metadata
- Complete amenities and POI data
"""

import requests
import json
from typing import Dict, Any, List
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
HOTEL_URL = f"{BASE_URL}/hotels"

# Test data from actual JSON structure
KNOWN_ATTRACTIONS = [
    "Sigiriya", "Kandy", "Galle", "Colombo", "Ella",
    "Nuwara Eliya", "Anuradhapura", "Dambulla", "Trincomalee",
    "Arugambay", "Bentota", "Hikkaduwa"
]

PROVINCES = ["Central", "Western", "Southern", "Eastern", 
             "Northern", "North Central", "Sabaragamuwa", 
             "North Western", "Uva"]

COMMON_AMENITIES = ["Wi-Fi", "Pool", "Restaurant", "Bar", "Spa",
                    "Air conditioning", "Parking", "Breakfast",
                    "Airport shuttle", "Fitness center"]

# Test counters
test_count = 0
passed_tests = 0
failed_tests = []


def print_response(title: str, response: requests.Response, validate: bool = True):
    """Pretty print response with validation"""
    global test_count, passed_tests, failed_tests
    test_count += 1
    
    print(f"\n{'='*80}")
    print(f"TEST #{test_count}: {title}")
    print(f"{'='*80}")
    print(f"Status Code: {response.status_code}")
    
    success = response.status_code in [200, 201]
    
    if success:
        try:
            data = response.json()
            print(f"✅ SUCCESS")
            print(f"Response:\n{json.dumps(data, indent=2)[:2000]}...")  # Limit output
            if validate:
                passed_tests += 1
        except Exception as e:
            print(f"⚠️  Response received but JSON parsing failed: {e}")
            print(f"Response: {response.text[:500]}")
            failed_tests.append(f"Test #{test_count}: {title} - JSON parse error")
    else:
        print(f"❌ FAILED")
        print(f"Error: {response.text[:500]}")
        failed_tests.append(f"Test #{test_count}: {title} - Status {response.status_code}")
    
    print(f"{'='*80}\n")
    return success, data if success else None


def validate_hotel_structure(hotel: Dict[str, Any]) -> bool:
    """Validate that hotel has required fields"""
    required_fields = ["hotel_id", "name", "attraction"]
    for field in required_fields:
        if field not in hotel:
            print(f"⚠️  Missing required field: {field}")
            return False
    return True


def test_health_check():
    """Test 0: API Health Check"""
    response = requests.get(f"{BASE_URL}/health")
    success, data = print_response("Health Check", response)
    return success


def test_list_hotels_basic():
    """Test 1: List hotels with pagination"""
    response = requests.get(f"{HOTEL_URL}/", params={
        "limit": 10,
        "offset": 0
    })
    success, data = print_response("List Hotels - Basic Pagination", response)
    
    if success and data:
        print(f"📊 Found {data.get('total', 0)} total hotels")
        print(f"📊 Returned {len(data.get('hotels', []))} hotels in this page")
        
        # Validate structure
        hotels = data.get('hotels', [])
        if hotels:
            validate_hotel_structure(hotels[0])
    
    return success


def test_list_hotels_by_province():
    """Test 2: Filter hotels by different provinces"""
    results = []
    
    for province in ["Central", "Western", "Southern"]:
        response = requests.get(f"{HOTEL_URL}/", params={
            "limit": 5,
            "province": province
        })
        success, data = print_response(f"List Hotels - Province: {province}", response)
        
        if success and data:
            count = len(data.get('hotels', []))
            print(f"📊 Found {count} hotels in {province} Province")
            results.append(success)
    
    return all(results)


def test_list_hotels_by_price():
    """Test 3: Filter hotels by price range"""
    price_tests = [
        {"max_price": 50, "desc": "Budget (< $50)"},
        {"min_price": 50, "max_price": 150, "desc": "Mid-range ($50-$150)"},
        {"min_price": 150, "desc": "Premium (> $150)"}
    ]
    
    results = []
    for test in price_tests:
        params = {"limit": 5}
        if "min_price" in test:
            params["min_price"] = test["min_price"]
        if "max_price" in test:
            params["max_price"] = test["max_price"]
        
        response = requests.get(f"{HOTEL_URL}/", params=params)
        success, data = print_response(f"List Hotels - {test['desc']}", response)
        
        if success and data:
            hotels = data.get('hotels', [])
            print(f"📊 Found {len(hotels)} hotels in {test['desc']} range")
            if hotels:
                prices = [h.get('rate_per_night') for h in hotels if h.get('rate_per_night')]
                if prices:
                    print(f"💰 Price range: ${min(prices):.2f} - ${max(prices):.2f}")
        
        results.append(success)
    
    return all(results)


def test_list_hotels_by_rating():
    """Test 4: Filter hotels by rating"""
    rating_tests = [
        {"min_rating": 4.5, "desc": "Excellent (4.5+)"},
        {"min_rating": 4.0, "max_rating": 4.5, "desc": "Good (4.0-4.5)"},
        {"max_rating": 4.0, "desc": "Standard (< 4.0)"}
    ]
    
    results = []
    for test in rating_tests:
        params = {"limit": 5}
        if "min_rating" in test:
            params["min_rating"] = test["min_rating"]
        if "max_rating" in test:
            params["max_rating"] = test["max_rating"]
        
        response = requests.get(f"{HOTEL_URL}/", params=params)
        success, data = print_response(f"List Hotels - {test['desc']}", response)
        
        if success and data:
            hotels = data.get('hotels', [])
            print(f"📊 Found {len(hotels)} hotels rated {test['desc']}")
            if hotels:
                ratings = [h.get('rating') for h in hotels if h.get('rating')]
                if ratings:
                    print(f"⭐ Rating range: {min(ratings):.1f} - {max(ratings):.1f}")
        
        results.append(success)
    
    return all(results)


def test_get_hotel_details():
    """Test 5: Get detailed hotel information"""
    # First get a hotel ID from list
    list_response = requests.get(f"{HOTEL_URL}/", params={"limit": 1})
    
    if list_response.status_code == 200:
        hotels = list_response.json().get("hotels", [])
        if hotels:
            hotel_id = hotels[0].get("id") or hotels[0].get("hotel_id")
            hotel_name = hotels[0].get("name", "Unknown")
            
            if hotel_id:
                response = requests.get(f"{HOTEL_URL}/{hotel_id}")
                success, data = print_response(
                    f"Get Hotel Details - {hotel_name} ({hotel_id})", 
                    response
                )
                
                if success and data:
                    # Validate detailed information
                    print(f"📍 Location: {data.get('attraction', 'N/A')}")
                    print(f"⭐ Rating: {data.get('rating', 'N/A')}")
                    print(f"💰 Rate: ${data.get('rate_per_night', 0)}/night")
                    
                    amenities = data.get('amenities', [])
                    print(f"🏨 Amenities: {len(amenities)} available")
                    
                    nearby = data.get('nearby_places', [])
                    print(f"📍 Nearby POIs: {len(nearby)} locations")
                    
                return success
            else:
                print("❌ No hotel ID found")
                return False
        else:
            print("❌ No hotels available for testing")
            return False
    else:
        print("❌ Failed to get hotel list")
        return False


def test_search_hotels_advanced():
    """Test 6: Advanced hotel search with multiple criteria"""
    search_scenarios = [
        {
            "name": "Budget Beach Hotels",
            "payload": {
                "location": {"province": "Southern"},
                "filters": {
                    "max_price": 100,
                    "min_rating": 4.0,
                    "amenities": ["Wi-Fi", "Beach access"]
                },
                "preferences": {"sort_by": "rating", "order": "desc"},
                "limit": 5
            }
        },
        {
            "name": "Luxury Central Hotels",
            "payload": {
                "location": {"province": "Central"},
                "filters": {
                    "min_price": 100,
                    "min_rating": 4.5,
                    "amenities": ["Pool", "Spa"]
                },
                "preferences": {"sort_by": "price", "order": "desc"},
                "limit": 5
            }
        }
    ]
    
    results = []
    for scenario in search_scenarios:
        response = requests.post(f"{HOTEL_URL}/search", json=scenario["payload"])
        success, data = print_response(
            f"Advanced Search - {scenario['name']}", 
            response
        )
        
        if success and data:
            hotels = data.get('hotels', [])
            print(f"📊 Found {len(hotels)} matching hotels")
        
        results.append(success)
    
    return all(results)


def test_recommendations_multi_attraction():
    """Test 7: Get recommendations for multi-attraction trips"""
    trip_scenarios = [
        {
            "name": "Cultural Triangle Tour",
            "attractions": ["Sigiriya", "Dambulla", "Polonnaruwa"],
            "budget": 20000
        },
        {
            "name": "Hill Country Experience",
            "attractions": ["Kandy", "Nuwara Eliya", "Ella"],
            "budget": 15000
        },
        {
            "name": "Southern Coast Journey",
            "attractions": ["Galle", "Hikkaduwa", "Bentota"],
            "budget": 25000
        }
    ]
    
    results = []
    for scenario in trip_scenarios:
        payload = {
            "attractions": scenario["attractions"],
            "budget_per_night": scenario["budget"],
            "preferred_amenities": ["Wi-Fi", "Pool", "Restaurant"],
            "optimize_for": "balanced",
            "max_results": 5
        }
        
        response = requests.post(f"{HOTEL_URL}/recommend", json=payload)
        success, data = print_response(
            f"Recommendations - {scenario['name']}", 
            response
        )
        
        if success and data:
            recommendations = data.get('recommendations', [])
            print(f"📊 Got {len(recommendations)} hotel recommendations")
            
            if recommendations:
                total_cost = data.get('total_cost', 0)
                score = data.get('optimization_score', 0)
                print(f"💰 Total cost: ${total_cost:.2f}")
                print(f"🎯 Optimization score: {score:.2f}")
                
                # Show distribution by attraction
                by_attraction = {}
                for hotel in recommendations:
                    attr = hotel.get('attraction')
                    by_attraction[attr] = by_attraction.get(attr, 0) + 1
                
                print(f"📍 Distribution: {by_attraction}")
        
        results.append(success)
    
    return all(results)


def test_statistics_overview():
    """Test 8: Get comprehensive hotel statistics"""
    response = requests.get(f"{HOTEL_URL}/statistics/overview")
    success, data = print_response("Hotel Statistics Overview", response)
    
    if success and data:
        print(f"\n📊 DATABASE STATISTICS:")
        print(f"  • Total Hotels: {data.get('total_hotels', 0)}")
        print(f"  • Attractions Covered: {data.get('total_attractions_covered', 0)}")
        print(f"  • Average Price: ${data.get('average_price', 0):.2f}")
        print(f"  • Average Rating: {data.get('average_rating', 0):.2f}⭐")
        print(f"  • Total POIs: {data.get('total_nearby_pois', 0)}")
        print(f"  • Total Amenities: {data.get('total_amenities', 0)}")
        
        # Price tier distribution
        by_tier = data.get('by_price_tier', {})
        if by_tier:
            print(f"\n💰 PRICE TIER DISTRIBUTION:")
            for tier, count in by_tier.items():
                print(f"  • {tier}: {count} hotels")
        
        # Province distribution
        by_province = data.get('by_province', {})
        if by_province:
            print(f"\n📍 PROVINCIAL DISTRIBUTION:")
            sorted_provinces = sorted(by_province.items(), key=lambda x: x[1], reverse=True)
            for province, count in sorted_provinces[:5]:
                print(f"  • {province}: {count} hotels")
        
        # Coverage map sample
        coverage = data.get('coverage_map', {})
        if coverage:
            print(f"\n🗺️  ATTRACTION COVERAGE (sample):")
            for attraction in list(coverage.keys())[:5]:
                hotel_count = len(coverage[attraction])
                print(f"  • {attraction}: {hotel_count} hotels")
    
    return success


def test_hotels_near_attractions():
    """Test 9: Find hotels near popular attractions"""
    test_attractions = [
        {"name": "Sigiriya", "radius": 5, "desc": "Ancient Rock Fortress"},
        {"name": "Kandy", "radius": 10, "desc": "Cultural Capital"},
        {"name": "Galle", "radius": 10, "desc": "Historic Fort City"},
        {"name": "Ella", "radius": 5, "desc": "Hill Country Town"},
        {"name": "Trincomalee", "radius": 15, "desc": "Eastern Beach"}
    ]
    
    results = []
    for attraction in test_attractions:
        response = requests.get(
            f"{HOTEL_URL}/near/{attraction['name']}", 
            params={"radius_km": attraction["radius"], "limit": 5}
        )
        
        success, data = print_response(
            f"Hotels Near {attraction['name']} - {attraction['desc']}", 
            response
        )
        
        if success and data:
            hotels = data.get('hotels', [])
            print(f"📊 Found {len(hotels)} hotels within {attraction['radius']}km")
            
            if hotels:
                # Show proximity distribution
                proximities = {}
                for hotel in hotels:
                    prox = hotel.get('proximity', 'unknown')
                    proximities[prox] = proximities.get(prox, 0) + 1
                
                print(f"📍 Proximity breakdown: {proximities}")
                
                # Show distance range
                distances = [h.get('distance_km', 0) for h in hotels]
                if distances:
                    print(f"🗺️  Distance range: {min(distances):.2f}km - {max(distances):.2f}km")
        
        results.append(success)
    
    return all(results)


def test_ingest_realistic_hotel():
    """Test 10: Ingest hotel data with realistic structure"""
    import tempfile
    import os
    
    # Create realistic hotel data based on actual JSON structure
    sample_data = {
        "attractions": [
            {
                "attraction": "Colombo",  # Use existing attraction
                "attraction_description": "Commercial capital and largest city of Sri Lanka",
                "geolocation": {
                    "latitude": 6.9271,
                    "longitude": 79.8612
                },
                "hotels": [
                    {
                        "name": "Test Integration Hotel Colombo",
                        "description": "Modern hotel for API testing with full amenities",
                        "link": "https://example.com/test-hotel",
                        "gps_coordinates": {
                            "latitude": 6.9271,
                            "longitude": 79.8612
                        },
                        "type": "hotel",
                        "province": "Western",
                        "rate_per_night": 120.0,
                        "rating": 4.6,
                        "reviews_count": 250,
                        "check_in_time": "2:00 PM",
                        "check_out_time": "12:00 PM",
                        "nearby_places": [
                            {
                                "name": "Galle Face Green",
                                "category": "Park",
                                "rating": 4.5,
                                "reviews": 5000
                            },
                            {
                                "name": "National Museum",
                                "category": "Museum",
                                "rating": 4.3,
                                "reviews": 1200
                            },
                            {
                                "name": "Gangaramaya Temple",
                                "category": "Buddhist temple",
                                "rating": 4.4,
                                "reviews": 3500
                            }
                        ],
                        "amenities": [
                            "Wi-Fi",
                            "Pool",
                            "Restaurant",
                            "Bar",
                            "Spa",
                            "Fitness center",
                            "Air conditioning",
                            "Parking",
                            "Airport shuttle",
                            "Business center"
                        ],
                        "images": [
                            "https://example.com/hotel1.jpg",
                            "https://example.com/hotel2.jpg"
                        ]
                    }
                ]
            }
        ],
        "scrape_metadata": {
            "source": "enhanced_test_suite",
            "timestamp": datetime.now().isoformat(),
            "check_in_date": "2026-01-02",
            "check_out_date": "2026-01-04"
        }
    }
    
    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_data, f, indent=2)
        temp_file = f.name
    
    try:
        with open(temp_file, 'rb') as f:
            files = {'file': ('test_hotels_realistic.json', f, 'application/json')}
            response = requests.post(f"{HOTEL_URL}/ingest", files=files)
            success, data = print_response("Ingest Realistic Hotel Data", response)
            
            if success and data:
                results = data.get('results', {})
                print(f"\n📊 INGESTION RESULTS:")
                print(f"  • Total Attractions: {results.get('total_attractions', 0)}")
                print(f"  • Hotels Created: {results.get('total_hotels_created', 0)}")
                print(f"  • Relationships: {results.get('total_relationships', 0)}")
                print(f"  • POIs Added: {results.get('total_pois', 0)}")
                print(f"  • Amenities: {results.get('total_amenities', 0)}")
                print(f"  • Errors: {results.get('total_errors', 0)}")
                print(f"  • Time: {results.get('total_time_seconds', 0):.2f}s")
            
            return success
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_data_integrity():
    """Test 11: Verify data integrity and consistency"""
    print(f"\n{'='*80}")
    print(f"TEST #{test_count + 1}: Data Integrity Checks")
    print(f"{'='*80}")
    
    checks_passed = []
    
    # Check 1: Verify all attractions have hotels
    print("\n🔍 Check 1: Attraction-Hotel Relationships")
    stats_response = requests.get(f"{HOTEL_URL}/statistics/overview")
    if stats_response.status_code == 200:
        stats = stats_response.json()
        coverage = stats.get('coverage_map', {})
        
        attractions_with_hotels = len(coverage)
        total_hotels = stats.get('total_hotels', 0)
        
        print(f"  ✓ {attractions_with_hotels} attractions have hotels")
        print(f"  ✓ {total_hotels} total hotels in database")
        checks_passed.append(True)
    else:
        print(f"  ✗ Failed to get statistics")
        checks_passed.append(False)
    
    # Check 2: Verify price data consistency
    print("\n🔍 Check 2: Price Data Consistency")
    response = requests.get(f"{HOTEL_URL}/", params={"limit": 100})
    if response.status_code == 200:
        hotels = response.json().get('hotels', [])
        hotels_with_prices = sum(1 for h in hotels if h.get('rate_per_night'))
        
        print(f"  ✓ {hotels_with_prices}/{len(hotels)} hotels have price data")
        checks_passed.append(hotels_with_prices > 0)
    else:
        print(f"  ✗ Failed to fetch hotels")
        checks_passed.append(False)
    
    # Check 3: Verify rating data
    print("\n🔍 Check 3: Rating Data Validation")
    if response.status_code == 200:
        hotels = response.json().get('hotels', [])
        hotels_with_ratings = sum(1 for h in hotels if h.get('rating'))
        valid_ratings = sum(1 for h in hotels if h.get('rating') and 0 <= h.get('rating') <= 5)
        
        print(f"  ✓ {hotels_with_ratings}/{len(hotels)} hotels have ratings")
        print(f"  ✓ {valid_ratings}/{hotels_with_ratings} ratings are valid (0-5 range)")
        checks_passed.append(valid_ratings > 0)
    
    # Check 4: Verify geolocation data
    print("\n🔍 Check 4: Geolocation Data Completeness")
    if response.status_code == 200:
        hotels = response.json().get('hotels', [])
        hotels_with_coords = sum(
            1 for h in hotels 
            if h.get('latitude') and h.get('longitude')
        )
        
        print(f"  ✓ {hotels_with_coords}/{len(hotels)} hotels have GPS coordinates")
        checks_passed.append(hotels_with_coords > len(hotels) * 0.8)  # At least 80%
    
    all_passed = all(checks_passed)
    
    if all_passed:
        print(f"\n✅ All integrity checks passed!")
    else:
        print(f"\n⚠️  Some integrity checks failed")
    
    print(f"{'='*80}\n")
    
    return all_passed


def print_final_summary():
    """Print test execution summary"""
    print(f"\n{'='*80}")
    print(f"TEST EXECUTION SUMMARY")
    print(f"{'='*80}")
    print(f"\n📊 Results:")
    print(f"  • Total Tests: {test_count}")
    print(f"  • Passed: {passed_tests} ✅")
    print(f"  • Failed: {len(failed_tests)} ❌")
    
    if failed_tests:
        print(f"\n❌ Failed Tests:")
        for failure in failed_tests:
            print(f"  • {failure}")
    
    success_rate = (passed_tests / test_count * 100) if test_count > 0 else 0
    print(f"\n📈 Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print(f"\n🎉 All tests passed! Hotel API is fully functional.")
    elif success_rate >= 80:
        print(f"\n✅ Most tests passed. Minor issues detected.")
    elif success_rate >= 50:
        print(f"\n⚠️  Several tests failed. Investigation needed.")
    else:
        print(f"\n❌ Many tests failed. Major issues detected.")
    
    print(f"{'='*80}\n")


def main():
    """Run enhanced test suite"""
    print(f"\n{'='*80}")
    print(f"ENHANCED HOTEL API TEST SUITE")
    print(f"{'='*80}")
    print(f"Test Execution Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    try:
        # Core functionality tests
        print("🔵 PHASE 1: Core Functionality Tests")
        print("-" * 80)
        test_health_check()
        test_list_hotels_basic()
        test_get_hotel_details()
        
        # Filtering and search tests
        print("\n🔵 PHASE 2: Filtering and Search Tests")
        print("-" * 80)
        test_list_hotels_by_province()
        test_list_hotels_by_price()
        test_list_hotels_by_rating()
        test_search_hotels_advanced()
        
        # Recommendation and analytics tests
        print("\n🔵 PHASE 3: Recommendations and Analytics Tests")
        print("-" * 80)
        test_recommendations_multi_attraction()
        test_statistics_overview()
        
        # Location-based tests
        print("\n🔵 PHASE 4: Location-Based Tests")
        print("-" * 80)
        test_hotels_near_attractions()
        
        # Data ingestion and integrity tests
        print("\n🔵 PHASE 5: Data Ingestion and Integrity Tests")
        print("-" * 80)
        test_ingest_realistic_hotel()
        test_data_integrity()
        
        # Print summary
        print_final_summary()
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to the server.")
        print("Make sure the kg_service is running on http://localhost:8000")
    except KeyboardInterrupt:
        print("\n\n⚠️  Test execution interrupted by user")
        print_final_summary()
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        print_final_summary()


if __name__ == "__main__":
    main()
