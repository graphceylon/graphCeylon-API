# Railway & Train Schedules API Documentation

## Overview

This documentation covers the complete Railway and Train Schedules API integration for the GraphCeylon Tourism Knowledge Graph. The railway system is integrated into **Domain 4: Transportation** of the knowledge graph architecture.

## Architecture Integration

### Domain Structure
- **Domain**: Transportation (Domain 4)
- **Node Types**: 
  - `RailwayStation` (labeled as `:TransportationInfrastructure`)
  - `TrainSchedule` (labeled as `:TransportationService`)
- **Relationships**:
  - `BELONGS_TO_DOMAIN` → Transportation Domain
  - `LOCATED_IN_PROVINCE` → Province nodes
  - `LOCATED_IN_DISTRICT` → District nodes
  - `DEPARTS_FROM` → Starting railway station
  - `ARRIVES_AT` → Ending railway station
  - `CONNECTED_BY_TRAIN` → Direct connections between stations

### Data Sources
1. **Railway Stations**: `railway_stations_enriched.json`
   - 203 enriched stations with geolocation
   - Google Places data integration
   - Administrative area mappings (province, district, city)

2. **Train Schedules**: `train_schedules.csv`
   - 1774 schedule records
   - Multiple train types (Express, Semi Express, Slow, Intercity)
   - Pricing information (2nd and 3rd class)
   - Complete route information

## API Endpoints

### Railway Stations

#### 1. Get All Railway Stations
```http
GET /railway/stations
```

**Query Parameters:**
- `province` (optional): Filter by province (e.g., "Western Province")
- `district` (optional): Filter by district (e.g., "Colombo")
- `name_pattern` (optional): Search station names (case-insensitive)
- `is_major` (optional): Filter major stations only (true/false)
- `limit` (optional, default: 50, max: 200): Maximum results

**Example:**
```bash
curl "http://localhost:8000/railway/stations?province=Western%20Province&limit=20"
```

**Response:**
```json
{
  "stations": [
    {
      "name": "Colombo Fort",
      "station_id": "CMB_FORT",
      "enriched": true,
      "is_major_station": true,
      "platform_count": 10,
      "geolocation": {
        "coordinates": {
          "latitude": 6.9344,
          "longitude": 79.8428,
          "accuracy": "high"
        },
        "address_info": {
          "administrative_areas": {
            "province": "Western Province",
            "district": "Colombo",
            "city": "Colombo"
          }
        }
      },
      "google_place_data": {
        "rating": 4.2,
        "user_ratings_total": 1523
      }
    }
  ],
  "count": 1,
  "query_info": {
    "province": "Western Province",
    "limit": 20
  }
}
```

#### 2. Get Station by Name
```http
GET /railway/stations/by-name/{station_name}
```

**Example:**
```bash
curl "http://localhost:8000/railway/stations/by-name/Colombo%20Fort"
```

#### 3. Get Stations by Province
```http
GET /railway/stations/by-province/{province}
```

**Example:**
```bash
curl "http://localhost:8000/railway/stations/by-province/Central%20Province"
```

#### 4. Get Stations by District
```http
GET /railway/stations/by-district/{district}
```

#### 5. Get Station Statistics
```http
GET /railway/stations/statistics
```

**Response:**
```json
{
  "total_stations": 203,
  "enriched_stations": 203,
  "major_stations": 15,
  "stations_by_province": {
    "Western Province": 78,
    "Central Province": 45,
    "Southern Province": 32,
    "Uva Province": 18,
    "North Western Province": 20,
    "Sabaragamuwa Province": 10
  },
  "stations_by_district": {
    "Colombo": 45,
    "Gampaha": 33,
    "Kandy": 28,
    "Galle": 20
  }
}
```

#### 6. Create Railway Station
```http
POST /railway/stations/create
```

**Request Body:**
```json
{
  "name": "New Station",
  "geolocation": {
    "coordinates": {
      "latitude": 6.9271,
      "longitude": 79.8612,
      "accuracy": "high"
    },
    "address_info": {
      "administrative_areas": {
        "province": "Western Province",
        "district": "Colombo",
        "city": "Colombo"
      }
    }
  },
  "facilities": ["Ticket Office", "Waiting Room", "Restrooms"],
  "platform_count": 3,
  "is_major_station": false
}
```

#### 7. Initialize Railway Stations
```http
POST /railway/stations/initialize
```

Loads all 203 stations from `railway_stations_enriched.json` into the knowledge graph.

#### 8. Cleanup Railway Data
```http
DELETE /railway/stations/cleanup
```

Removes all railway stations and schedules. **Use with caution!**

### Train Schedules

#### 1. Get All Train Schedules
```http
GET /railway/schedules
```

**Query Parameters:**
- `start_station` (optional): Filter by departure station
- `end_station` (optional): Filter by arrival station
- `schedule_date` (optional): Filter by date (YYYY-MM-DD format)
- `train_type` (optional): Express | Semi Express | Slow | Intercity
- `limit` (optional, default: 100, max: 500): Maximum results

**Example:**
```bash
curl "http://localhost:8000/railway/schedules?start_station=Colombo%20Fort&end_station=Kandy&schedule_date=2026-01-09"
```

**Response:**
```json
{
  "schedules": [
    {
      "schedule_id": "1005_2026-01-09",
      "schedule_date": "2026-01-09",
      "start_station": "Colombo Fort",
      "end_station": "Kandy",
      "departure_time": "06:50 AM",
      "arrival_time": "09:30 AM",
      "duration": "2h 40m",
      "train_number": "1005",
      "train_type": "Express",
      "distance": "120.5 km",
      "price_2nd_class": "Rs. 300.00",
      "price_3rd_class": "Rs. 150.00",
      "train_stops": "Colombo Fort, Ragama, Gampaha, Polgahawela, Rambukkana, Peradeniya, Kandy"
    }
  ],
  "count": 1,
  "query_info": {
    "start_station": "Colombo Fort",
    "end_station": "Kandy",
    "schedule_date": "2026-01-09"
  }
}
```

#### 2. Get Schedules by Train Number
```http
GET /railway/schedules/by-train/{train_number}
```

**Query Parameters:**
- `schedule_date` (optional): Filter by specific date

#### 3. Find Routes Between Stations
```http
POST /railway/schedules/find-routes
```

**Request Body:**
```json
{
  "start_station": "Colombo Fort",
  "end_station": "Ella",
  "max_transfers": 2,
  "preferred_train_type": "Express"
}
```

**Response:**
```json
{
  "routes": [
    {
      "segments": [
        {
          "start_station": "Colombo Fort",
          "end_station": "Ella",
          "departure_time": "08:00 AM",
          "arrival_time": "02:15 PM",
          "duration": "6h 15m",
          "train_number": "1005",
          "train_type": "Express",
          "distance_km": 290.5,
          "price_2nd_class": "Rs. 600.00",
          "price_3rd_class": "Rs. 300.00"
        }
      ],
      "total_duration": "6h 15m",
      "total_distance_km": 290.5,
      "transfer_count": 0,
      "total_price_2nd_class": 600.0,
      "total_price_3rd_class": 300.0
    }
  ],
  "count": 1,
  "query": {
    "start_station": "Colombo Fort",
    "end_station": "Ella",
    "max_transfers": 2
  }
}
```

#### 4. Get Station Connections
```http
GET /railway/schedules/connections/{station_name}
```

Returns all stations directly connected via train routes.

**Example:**
```bash
curl "http://localhost:8000/railway/schedules/connections/Colombo%20Fort"
```

#### 5. Get Schedule Statistics
```http
GET /railway/schedules/statistics
```

**Response:**
```json
{
  "total_schedules": 1774,
  "unique_trains": 156,
  "unique_routes": 89,
  "schedules_by_train_type": {
    "Express": 876,
    "Semi Express": 324,
    "Slow": 456,
    "Intercity": 118
  },
  "date_range": {
    "earliest": "2026-01-09",
    "latest": "2026-01-15"
  }
}
```

#### 6. Create Train Schedule
```http
POST /railway/schedules/create
```

**Request Body:**
```json
{
  "schedule_date": "2026-01-15",
  "start_station": "Colombo Fort",
  "end_station": "Kandy",
  "departure_time": "08:00 AM",
  "arrival_time": "10:45 AM",
  "duration": "2h 45m",
  "train_number": "1007",
  "train_type": "Express",
  "distance": "120.5 km",
  "price_2nd_class": "Rs. 300.00",
  "price_3rd_class": "Rs. 150.00"
}
```

#### 7. Initialize Train Schedules
```http
POST /railway/schedules/initialize
```

Loads all schedules from `train_schedules.csv`. **Railway stations must be initialized first!**

## Setup Guide

### Step 1: Initialize Railway Stations

```bash
curl -X POST http://localhost:8000/railway/stations/initialize
```

This loads all 203 railway stations into the knowledge graph.

### Step 2: Verify Stations

```bash
curl http://localhost:8000/railway/stations/statistics
```

Should show 203 total stations.

### Step 3: Initialize Train Schedules

```bash
curl -X POST http://localhost:8000/railway/schedules/initialize
```

This loads all train schedules and creates route connections.

### Step 4: Verify Schedules

```bash
curl http://localhost:8000/railway/schedules/statistics
```

Should show all loaded schedules.

## Use Cases

### 1. Tourist Journey Planning

Find trains from Colombo to scenic destinations:

```bash
# Colombo to Ella (scenic hill country route)
curl -X POST http://localhost:8000/railway/schedules/find-routes \
  -H "Content-Type: application/json" \
  -d '{
    "start_station": "Colombo Fort",
    "end_station": "Ella",
    "max_transfers": 1,
    "preferred_train_type": "Express"
  }'

# Colombo to Galle (coastal route)
curl "http://localhost:8000/railway/schedules?start_station=Colombo%20Fort&end_station=Galle&train_type=Express"
```

### 2. Regional Station Discovery

Find stations in tourist regions:

```bash
# Hill country stations
curl "http://localhost:8000/railway/stations?province=Central%20Province"

# Coastal stations
curl "http://localhost:8000/railway/stations?district=Galle"
```

### 3. Major Hub Analysis

Get information about major railway hubs:

```bash
curl "http://localhost:8000/railway/stations?is_major=true"
```

### 4. Route Network Analysis

Analyze station connectivity:

```bash
curl "http://localhost:8000/railway/schedules/connections/Colombo%20Fort"
```

## Data Model

### RailwayStation Node
```cypher
(:RailwayStation:TransportationInfrastructure {
  name: "Colombo Fort",
  station_id: "CMB_FORT",
  enriched: true,
  is_major_station: true,
  platform_count: 10,
  latitude: 6.9344,
  longitude: 79.8428,
  coordinates_accuracy: "high",
  province: "Western Province",
  district: "Colombo",
  city: "Colombo",
  google_rating: 4.2,
  google_ratings_total: 1523,
  facilities: ["Ticket Office", "Waiting Room"],
  created_at: datetime()
})
```

### TrainSchedule Node
```cypher
(:TrainSchedule:TransportationService {
  schedule_id: "1005_2026-01-09",
  schedule_date: "2026-01-09",
  departure_time: "06:50 AM",
  arrival_time: "09:30 AM",
  duration: "2h 40m",
  train_number: "1005",
  train_type: "Express",
  distance: "120.5 km",
  distance_km: 120.5,
  price_2nd_class: "Rs. 300.00",
  price_3rd_class: "Rs. 150.00",
  train_stops: "Colombo Fort, Ragama, ...",
  created_at: datetime()
})
```

### Relationships
```cypher
// Domain linkage
(station:RailwayStation)-[:BELONGS_TO_DOMAIN]->(domain:Domain {name: "Transportation"})

// Administrative linkage
(station:RailwayStation)-[:LOCATED_IN_PROVINCE]->(province:Province)
(station:RailwayStation)-[:LOCATED_IN_DISTRICT]->(district:District)

// Schedule connections
(schedule:TrainSchedule)-[:DEPARTS_FROM]->(start:RailwayStation)
(schedule:TrainSchedule)-[:ARRIVES_AT]->(end:RailwayStation)

// Station network
(start:RailwayStation)-[:CONNECTED_BY_TRAIN]->(end:RailwayStation)
```

## Error Handling

All endpoints return standard HTTP status codes:

- **200 OK**: Successful request
- **404 Not Found**: Resource not found (e.g., station doesn't exist)
- **500 Internal Server Error**: Server error with detailed message

**Error Response Format:**
```json
{
  "detail": "Railway station not found: Unknown Station"
}
```

## Performance Considerations

1. **Indexing**: Ensure Neo4j indexes on:
   - `RailwayStation.name`
   - `RailwayStation.province`
   - `RailwayStation.district`
   - `TrainSchedule.train_number`
   - `TrainSchedule.schedule_date`

2. **Query Optimization**: Use appropriate limits for large result sets

3. **Bulk Loading**: Use initialization endpoints for bulk data loading rather than individual creates

## Integration with Other Domains

The railway system integrates with:

1. **Destination & Attraction**: Stations near tourist attractions
2. **Accommodation & Hospitality**: Hotels near railway stations
3. **Geographic**: Province and district administrative hierarchy
4. **Temporal**: Schedule timing and seasonal variations
5. **User & Behavior**: Tourist travel patterns and preferences

## Postman Collection

Import the provided `Railway_API_Postman_Collection.json` for comprehensive API testing:

- Pre-configured requests for all endpoints
- Example queries for common use cases
- Complete setup workflow
- Variable-based configuration

## Support

For issues or questions:
- Check API documentation: http://localhost:8000/docs
- Review Postman collection examples
- Consult knowledge graph schema documentation

---

**Version**: 1.0.0  
**Domain**: Transportation (Domain 4)  
**Last Updated**: January 3, 2026
