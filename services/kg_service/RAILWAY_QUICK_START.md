# Railway & Train Schedules - Quick Start Guide

## 🚂 Overview

Complete integration of Sri Lanka Railway system into the GraphCeylon Tourism Knowledge Graph. This includes 203 railway stations and comprehensive train schedules across the country.

## 📁 Files Created/Modified

### New Files
1. **Models**: `src/models/domain/railway.py`
   - Railway station and train schedule Pydantic models
   - Request/response schemas
   - Statistics models

2. **Repository**: `src/database/repositories/railway_repository.py`
   - Cypher queries for stations and schedules
   - Bulk loading functions
   - Statistics and analytics

3. **Routers**:
   - `src/api/routers/railway_stations.py` - Railway station endpoints
   - `src/api/routers/train_schedules.py` - Train schedule endpoints

4. **Documentation**:
   - `RAILWAY_API_DOCUMENTATION.md` - Complete API documentation
   - `Railway_API_Postman_Collection.json` - Postman collection

### Modified Files
1. `src/database/repositories/__init__.py` - Added RailwayRepository export
2. `src/database/manager.py` - Added railway repository to DatabaseManager
3. `src/models/schemas.py` - Added railway model exports
4. `src/api/main.py` - Integrated railway routers

## 🚀 Quick Start (3 Steps)

### Step 1: Start the API Server

```bash
cd services/kg_service
python -m uvicorn src.main:app --reload --port 8000
```

### Step 2: Initialize Railway Stations

```bash
# Load all 203 railway stations
curl -X POST http://localhost:8000/railway/stations/initialize
```

Expected response:
```json
{
  "success": true,
  "message": "Railway stations initialized successfully",
  "total": 203,
  "created": 203,
  "failed": 0
}
```

### Step 3: Initialize Train Schedules

```bash
# Load all train schedules
curl -X POST http://localhost:8000/railway/schedules/initialize
```

Expected response:
```json
{
  "success": true,
  "message": "Train schedules initialized successfully",
  "total": 1774,
  "created": 1774,
  "failed": 0
}
```

## ✅ Verify Installation

### Check Station Statistics
```bash
curl http://localhost:8000/railway/stations/statistics
```

Should show:
- Total stations: 203
- Enriched stations: 203
- Breakdown by province and district

### Check Schedule Statistics
```bash
curl http://localhost:8000/railway/schedules/statistics
```

Should show:
- Total schedules loaded
- Unique trains
- Unique routes
- Breakdown by train type

## 📖 Common API Calls

### 1. Find Trains from Colombo to Galle
```bash
curl "http://localhost:8000/railway/schedules?start_station=Colombo%20Fort&end_station=Galle&schedule_date=2026-01-09"
```

### 2. Get All Stations in Western Province
```bash
curl "http://localhost:8000/railway/stations?province=Western%20Province"
```

### 3. Find Routes with Transfers
```bash
curl -X POST http://localhost:8000/railway/schedules/find-routes \
  -H "Content-Type: application/json" \
  -d '{
    "start_station": "Colombo Fort",
    "end_station": "Ella",
    "max_transfers": 1,
    "preferred_train_type": "Express"
  }'
```

### 4. Get Station Information
```bash
curl "http://localhost:8000/railway/stations/by-name/Colombo%20Fort"
```

### 5. Get Station Connections
```bash
curl "http://localhost:8000/railway/schedules/connections/Colombo%20Fort"
```

## 🎯 Use Cases

### Tourism Planning
- **Scenic Routes**: Find trains to Ella, Kandy, or Galle
- **Coastal Route**: Colombo to Matara/Galle (ocean views)
- **Hill Country**: Colombo to Kandy, Nuwara Eliya, Ella (mountain scenery)

### Integration Points
- Link railway stations to nearby hotels
- Connect stations to tourist attractions
- Integrate with itinerary planning
- Route optimization for multi-destination trips

## 📊 Knowledge Graph Structure

### Domain: Transportation (Domain 4)

```
Country: Sri Lanka
  ↓
Domain: Transportation
  ↓
├─ RailwayStation (203 nodes)
│  ├─ BELONGS_TO_DOMAIN → Transportation
│  ├─ LOCATED_IN_PROVINCE → Province
│  └─ LOCATED_IN_DISTRICT → District
│
└─ TrainSchedule (1774 nodes)
   ├─ BELONGS_TO_DOMAIN → Transportation
   ├─ DEPARTS_FROM → RailwayStation
   └─ ARRIVES_AT → RailwayStation

Station Network:
RailwayStation -[CONNECTED_BY_TRAIN]-> RailwayStation
```

## 🧪 Testing with Postman

1. Import `Railway_API_Postman_Collection.json` into Postman
2. Collection includes:
   - **Setup & Initialization** folder (run in order)
   - **Railway Stations** folder (all station endpoints)
   - **Train Schedules** folder (all schedule endpoints)
   - **Common Examples** folder (tourism scenarios)

## 🔍 Interactive API Documentation

Visit: http://localhost:8000/docs

FastAPI automatic documentation with:
- All endpoints with try-it-out functionality
- Request/response schemas
- Parameter descriptions

## 📝 Data Format

### Railway Station Example
```json
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
  }
}
```

### Train Schedule Example
```json
{
  "schedule_date": "2026-01-09",
  "start_station": "Colombo Fort",
  "end_station": "Galle",
  "departure_time": "06:50 AM",
  "arrival_time": "09:10 AM",
  "duration": "2h 20m",
  "train_number": "8050",
  "train_type": "Express",
  "distance": "115.0 km",
  "price_2nd_class": "Rs. 500.00",
  "price_3rd_class": "Rs. 260.00"
}
```

## 🛠️ Troubleshooting

### Issue: Stations won't load
**Solution**: Check file path in `railway_repository.py` matches your data location:
```python
json_file = "data/kg_service/data/train_schedule/railway_stations_enriched.json"
```

### Issue: Schedules fail to load
**Cause**: Stations must be loaded first
**Solution**: Run station initialization before schedule initialization

### Issue: Station not found errors
**Cause**: Station names must match exactly (case-insensitive)
**Solution**: Use station listing endpoints to find exact names

## 🔄 Reset/Cleanup

To remove all railway data:
```bash
curl -X DELETE http://localhost:8000/railway/stations/cleanup
```

Then re-run initialization steps.

## 📈 Next Steps

1. **Integration**: Link stations to nearby attractions and hotels
2. **Analytics**: Add GNN-based recommendations for routes
3. **Real-time**: Integrate live schedule data if available
4. **Optimization**: Add route optimization algorithms
5. **Multi-modal**: Combine with bus routes and other transportation

## 🎓 Architecture Highlights

- **Clean Architecture**: Separation of models, repositories, services, and routers
- **Domain-Driven**: Integrated into Domain 4 (Transportation)
- **Graph-Native**: Leverages Neo4j relationships for route finding
- **Enriched Data**: Google Places integration for stations
- **Type-Safe**: Full Pydantic model validation
- **RESTful**: Standard HTTP methods and status codes

## 📚 Additional Resources

- **Full Documentation**: `RAILWAY_API_DOCUMENTATION.md`
- **Postman Collection**: `Railway_API_Postman_Collection.json`
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

**Status**: ✅ Ready for Testing  
**Version**: 1.0.0  
**Domain**: Transportation (Domain 4)  
**Created**: January 3, 2026
