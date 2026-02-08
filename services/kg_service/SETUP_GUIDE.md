# 🚀 Quick Setup Guide - Hotel Search API

## Prerequisites

- Python 3.9+ installed
- Neo4j database running (bolt://localhost:7687)
- Virtual environment activated: `kg_service`

---

## 📁 Step 1: Place the hotels.json File

The `hotels.json` file should be placed in:

```
graphCeylon-API/
└── data/
    └── kg_service/
        └── data/
            └── hotels.json    <-- Place your file here
```

**Full path**: `C:\Users\[YourName]\Desktop\graphCeylon-API\data\kg_service\data\hotels.json`

---

## 🗄️ Step 2: Ingest Hotels to Neo4j

### Option A: Using the Ingestion Script (Recommended)

1. **Navigate to scripts folder**:
   ```powershell
   cd C:\Users\[YourName]\Desktop\graphCeylon-API\services\kg_service
   cd scripts
   ```

2. **Run the ingestion script**:
   ```powershell
   python ingest_hotels.py
   ```

3. **Confirm when prompted**:
   ```
   ❓ Continue with ingestion? (y/n): y
   ```

4. **Wait for completion**:
   ```
   ✅ Successfully ingested X hotels
   ```

### Option B: Using the API Endpoint (via Postman/curl)

This method is useful if the script doesn't work or you want to ingest via API.

**Endpoint**: `POST http://localhost:8000/hotels/ingest`

**Steps in Postman**:
1. Set method to **POST**
2. URL: `http://localhost:8000/hotels/ingest`
3. Go to **Body** tab
4. Select **form-data**
5. Add key: `file` (change type to **File**)
6. Select your `hotels.json` file
7. Click **Send**

---

## 🔍 Step 3: Verify Data Was Ingested

### Method 1: Check via Neo4j Browser

1. Open Neo4j Browser: http://localhost:7474
2. Run query:
   ```cypher
   MATCH (h:Hotel) RETURN count(h) as total_hotels
   ```
3. Should see: `total_hotels: 165` (or your number of hotels)

### Method 2: Check via API

**Endpoint**: `GET http://localhost:8000/hotels/statistics/overview`

**In Postman**:
1. Method: **GET**
2. URL: `http://localhost:8000/hotels/statistics/overview`
3. Click **Send**

**Expected Response**:
```json
{
  "total_hotels": 165,
  "by_province": {...},
  "average_price": 76.15,
  ...
}
```

---

## 🧪 Step 4: Test Orchestrator Search Endpoint

### Start the Backend Server

1. **Navigate to kg_service**:
   ```powershell
   cd C:\Users\[YourName]\Desktop\graphCeylon-API\services\kg_service
   ```

2. **Activate virtual environment** (if not already):
   ```powershell
   # The prompt should show (kg_service)
   ```

3. **Start the server**:
   ```powershell
   python src/main.py
   ```

4. **Verify server is running**:
   ```
   Starting Knowledge Graph Service...
   API Host: 0.0.0.0
   API Port: 8000
   ```

5. **Open in browser**: http://localhost:8000/docs

---

## 📮 Step 5: Test in Postman

### Test Case 1: Hotels in Galle

**Method**: `POST`
**URL**: `http://localhost:8000/hotels/orchestrator/call/hotels/search`

**Headers**:
```
Content-Type: application/json
```

**Body** (raw JSON):
```json
{
  "intent": "info_accommodation",
  "raw_text": "Hotels in Galle",
  "user_id": "test-user-001",
  "session_id": "postman-test-1",
  "city": "Galle",
  "limit": 10
}
```

**Expected Response**:
```json
{
  "ok": true,
  "count": 15,
  "items": [
    {
      "name": "Hotel Name",
      "city": "Galle",
      "country": "Sri Lanka",
      "star_rating": 5,
      "price_range_lkr": {
        "min": 18000,
        "max": 22000
      },
      "amenities": ["wifi", "pool", "parking"],
      "address": "Galle, Southern",
      "geo": {
        "lat": 6.0535,
        "lon": 80.2210
      },
      "source": "neo4j",
      "kg_id": "Hotel:hotel_xyz"
    }
  ],
  "trace": {
    "cypher_ms": 45.2,
    "filters_applied": {
      "city": "Galle"
    }
  }
}
```

### Test Case 2: Budget Hotels (under 15,000 LKR)

**Body**:
```json
{
  "intent": "info_accommodation",
  "raw_text": "Affordable hotels",
  "user_id": "test-user-002",
  "session_id": "postman-test-2",
  "max_price_lkr": 15000,
  "limit": 10
}
```

### Test Case 3: 5-Star Hotels with Amenities

**Body**:
```json
{
  "intent": "info_accommodation",
  "raw_text": "5-star hotels with wifi and pool",
  "user_id": "test-user-003",
  "session_id": "postman-test-3",
  "min_star_rating": 5,
  "max_star_rating": 5,
  "must_have_amenities": ["wi-fi", "outdoor pool"],
  "limit": 10
}
```

### Test Case 4: All Filters Combined

**Body**:
```json
{
  "intent": "info_accommodation",
  "raw_text": "What are 3-star hotels in Colombo?",
  "user_id": "test-user-004",
  "session_id": "postman-test-4",
  "city": "Colombo",
  "country": "Sri Lanka",
  "min_star_rating": 3,
  "max_star_rating": 3,
  "must_have_amenities": ["wifi", "ac"],
  "max_price_lkr": 50000,
  "limit": 10
}
```

---

## 📊 Pre-Generated Test Cases

Ready-to-use test cases based on your actual data:

**Location**: `services/kg_service/tests/postman_test_cases.json`

**How to use**:
1. Open the file
2. Copy any request body
3. Paste into Postman Body (raw JSON)
4. Send request

---

## 🐛 Troubleshooting

### Issue: "Neo4j connection failed"

**Solution**:
1. Check Neo4j is running: http://localhost:7474
2. Verify credentials in `.env` file:
   ```
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```

### Issue: "No hotels found"

**Solution**:
1. Run ingestion script again
2. Check Neo4j has data:
   ```cypher
   MATCH (h:Hotel) RETURN count(h)
   ```
3. If count is 0, re-run ingestion

### Issue: "Module not found"

**Solution**:
```powershell
# Make sure virtual environment is activated
# Install dependencies
pip install -r requirements.txt
```

### Issue: "Port 8000 already in use"

**Solution**:
1. Kill existing process:
   ```powershell
   # Find process using port 8000
   netstat -ano | findstr :8000
   
   # Kill process (replace PID with actual number)
   taskkill /PID [PID] /F
   ```
2. Or change port in `.env`:
   ```
   API_PORT=8001
   ```

### Issue: "Amenities not matching"

**Note**: Amenity names must be lowercase and match exactly:
- ✅ Correct: `"wi-fi"`, `"outdoor pool"`, `"kid-friendly"`
- ❌ Wrong: `"WiFi"`, `"Pool"`, `"Kid Friendly"`

Check available amenities:
```cypher
MATCH (a:Amenity) 
RETURN DISTINCT a.name 
ORDER BY a.name
LIMIT 20
```

---

## 📝 Quick Reference

### Common Amenity Names
```
wi-fi
parking
air conditioning
outdoor pool
kid-friendly
restaurant
breakfast
airport shuttle
room service
```

### Common Cities in Database
```
Galle
Matale
Ratnapura
Trincomalee
Nuwara Eliya
Kandy
Colombo
Anuradhapura
```

### Price Ranges (per night in LKR)
- **Budget**: < 15,000 LKR
- **Mid-range**: 15,000 - 30,000 LKR
- **Luxury**: 30,000 - 60,000 LKR
- **Premium**: > 60,000 LKR

---

## 🎯 Success Checklist

- [ ] hotels.json placed in correct folder
- [ ] Neo4j database running
- [ ] Hotels ingested successfully (165 hotels)
- [ ] Backend server running on port 8000
- [ ] Can access API docs: http://localhost:8000/docs
- [ ] Postman test returns results
- [ ] Response format matches specification

---

## 📞 Need Help?

1. **Check logs**: Server terminal shows detailed error messages
2. **API Documentation**: http://localhost:8000/docs
3. **Test suite**: Run automated tests:
   ```powershell
   cd tests
   python run_generated_tests.py
   ```

---

## 🎉 You're All Set!

Your friend can now:
- ✅ Ingest hotel data
- ✅ Search hotels by city, rating, amenities, budget
- ✅ Test via Postman
- ✅ Integrate with orchestrator service
