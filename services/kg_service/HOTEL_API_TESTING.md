# Hotel API Testing Guide

Make sure your kg_service is running first:
```bash
cd C:\Users\DananjayaAbey\Desktop\graphCeylon-API\services\kg_service
.\.venv\Scripts\Activate.ps1
cd src
python main.py
```

Then in a NEW terminal, run these tests:

## 1. Health Check
```bash
curl http://localhost:8000/health
```

## 2. List All Hotels (Basic)
```bash
curl "http://localhost:8000/hotels/?limit=5&offset=0"
```

## 3. List Hotels with Filters
```bash
curl "http://localhost:8000/hotels/?limit=5&province=Western&min_rating=4.0"
```

## 4. Get Hotel Details (replace {hotel_id} with actual ID)
```bash
curl "http://localhost:8000/hotels/{hotel_id}"
```

## 5. Search Hotels (Advanced)
```bash
curl -X POST "http://localhost:8000/hotels/search" ^
  -H "Content-Type: application/json" ^
  -d "{\"location\": {\"province\": \"Western\", \"district\": \"Colombo\"}, \"filters\": {\"min_rating\": 3.5, \"max_price\": 15000}, \"limit\": 10}"
```

## 6. Get Hotel Recommendations
```bash
curl -X POST "http://localhost:8000/hotels/recommend" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_preferences\": {\"budget\": 20000, \"min_rating\": 4.0}, \"constraints\": {\"province\": \"Southern\"}, \"limit\": 5}"
```

## 7. Get Hotel Statistics
```bash
curl "http://localhost:8000/hotels/statistics/overview"
```

## 8. Find Hotels Near Attraction
```bash
curl "http://localhost:8000/hotels/near/Sigiriya?radius_km=5&limit=5"
```

## 9. Ingest Sample Hotel
```bash
curl -X POST "http://localhost:8000/hotels/ingest" ^
  -H "Content-Type: application/json" ^
  -d "{\"hotels\": [{\"name\": \"Test Resort\", \"rating\": 4.5, \"price_per_night\": 12000, \"location\": {\"province\": \"Southern\", \"district\": \"Galle\"}}], \"link_to_nearby\": true}"
```

## 10. View API Documentation
Open in browser: http://localhost:8000/docs

This will show you the interactive Swagger UI where you can test all endpoints visually.
