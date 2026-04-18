# How to Use the GNN Postman Collection

## 📦 File Location
`tests/GNN_API_Test_Collection.postman_collection.json`

---

## 🚀 Quick Start

### 1. Import into Postman
1. Open Postman
2. Click **Import** button (top left)
3. Select **File** tab
4. Choose: `tests/GNN_API_Test_Collection.postman_collection.json`
5. Click **Import**

### 2. Verify Base URL
- Collection uses variable: `{{base_url}}`
- Default: `http://localhost:8000`
- To change:
  - Click collection name
  - Go to **Variables** tab
  - Edit `base_url` value if needed

### 3. Run Tests

#### Option A: Run Entire Collection (21 tests)
1. Click collection name: **GraphCeylon GNN API - Working Test Suite**
2. Click **Run** button
3. Click **Run GraphCeylon GNN API**
4. Watch all 21 tests execute automatically

**Expected Duration**: ~2-5 seconds total

#### Option B: Run Individual Test
1. Expand collection folders
2. Click any test request
3. Click **Send** button
4. View response and test results

#### Option C: Run by Category
Right-click any folder to run just that section:
- Service Health (1 test)
- Model Information (2 tests)
- Hotel Recommendations (4 tests)
- Top-Rated Hotels (2 tests)
- Similar Hotels (2 tests)
- Route Scoring (4 tests)
- Similar Stations (3 tests)
- Raw Embeddings (2 tests)

---

## 📊 Test Coverage

### ✅ 21 Comprehensive Tests

| Category | Tests | What It Checks |
|----------|-------|----------------|
| **1. Service Health** | 1 | Service status, model availability |
| **2. Model Information** | 2 | Hotel & route model details |
| **3. Hotel Recommendations** | 4 | Similar hotels, error handling |
| **4. Top-Rated Hotels** | 2 | GNN rankings (10 & 20 hotels) |
| **5. Similar Hotels** | 2 | GET endpoint for similarity |
| **6. Route Scoring** | 4 | Route quality, error handling |
| **7. Similar Stations** | 3 | Station similarity queries |
| **8. Raw Embeddings** | 2 | 32-dim embedding vectors |

---

## 🎯 Real Test Data Used

### Hotels (lowercase with underscores)
```
hotel_cinnamon_lakeside_colombo
hotel_amaya_beach_pasikudah
hotel_sigiriya_village_hotel
hotel_riviera_resort
hotel_arugam_bay_roccos
```

### Stations (UPPERCASE)
```
COLOMBO_FORT
GALLE
ELLA
BADULLA
MATARA
```

---

## ✨ Automated Assertions

Each test includes automatic checks:

✅ **Status Code Validation**
- Success tests expect 200
- Error tests expect 404

✅ **Response Structure**
- Validates JSON properties
- Checks data types
- Verifies array lengths

✅ **Business Logic**
- Similarity scores: 0.0 to 1.0
- Inference time < 500ms
- Model info contains correct node types
- Total hotels = 165
- Total stations = 406

✅ **Error Handling**
- Invalid hotel names return 404
- Invalid station names return 404
- Error messages are descriptive

---

## 📈 Expected Results

### ✅ All Tests Should Pass If:
1. API server is running on `http://localhost:8000`
2. Models are trained: `uv run run_gnn.py all`
3. Data files exist in `data/gnn/` and `checkpoints/`

### Sample Successful Output:
```
✓ Status code is 200
✓ Service is GraphCeylon GNN API
✓ Hotel model data available
✓ Route model data available
✓ Returns 5 recommendations
✓ Similarity scores present
✓ Inference time reasonable
```

---

## 🔍 How to Read Results

### Hotel Recommendation Response
```json
{
  "query_hotel": {
    "id": "hotel_cinnamon_lakeside_colombo",
    "type": "Hotel"
  },
  "recommendations": [
    {
      "id": "hotel_ramada_by_wyndham_colombo",
      "similarity_score": 1.0
    }
  ],
  "inference_time_ms": 31.43
}
```

**Key Metrics:**
- `similarity_score`: 1.0 = perfect match, 0.0 = no similarity
- `inference_time_ms`: Should be < 100ms typically

### Route Scoring Response
```json
{
  "source": { "id": "COLOMBO_FORT" },
  "destination": { "id": "GALLE" },
  "connectivity_score": 0.4407,
  "embedding_similarity": 0.994,
  "inference_time_ms": 259.27
}
```

**Key Metrics:**
- `connectivity_score`: GNN-predicted route quality (higher = better)
- `embedding_similarity`: How similar stations are (0-1 range)

---

## 🐛 Troubleshooting

### ❌ All Tests Fail with Connection Error
**Problem**: API server not running  
**Solution**: Start server: `uv run fastapi dev src/main.py`

### ❌ Tests Show "data_available: false"
**Problem**: Graph data not exported  
**Solution**: `uv run run_gnn.py export`

### ❌ Tests Show "checkpoint_available: false"
**Problem**: Models not trained  
**Solution**: `uv run run_gnn.py train hotel && uv run run_gnn.py train route`

### ❌ 404 Errors on Hotel/Station Names
**Problem**: Using wrong ID format  
**Solution**: 
- Hotels: use lowercase `hotel_name_here`
- Stations: use UPPERCASE `STATION_NAME`
- Check [GNN_ACTUAL_TEST_DATA.md](../GNN_ACTUAL_TEST_DATA.md) for valid IDs

### ❌ Some Tests Pass, Some Fail
**Check**:
1. View failed test response body
2. Read error message in `detail` field
3. Verify test data matches your graph

---

## 📚 Related Documentation

- **[GNN_TESTING_SUCCESS_REPORT.md](../GNN_TESTING_SUCCESS_REPORT.md)** - Complete test results
- **[GNN_ACTUAL_TEST_DATA.md](../GNN_ACTUAL_TEST_DATA.md)** - All valid hotel/station IDs
- **[GNN_TESTING_GUIDE.md](../GNN_TESTING_GUIDE.md)** - Detailed testing manual

---

## 🎉 Success Criteria

**All 21 Tests Passing = Your GNN Implementation is 100% Working!**

You should see:
- ✅ 21 passed tests
- ✅ 0 failed tests
- ✅ Total time: 2-5 seconds
- ✅ All response times < 500ms

---

## 💡 Pro Tips

1. **Run collection after any code changes** to verify nothing broke
2. **Export test results** via Postman to share with team
3. **Check "Test Results" tab** in response pane for detailed pass/fail
4. **Use "Console" (View → Show Postman Console)** for debugging
5. **Duplicate tests** to create custom test cases

---

**Ready to test? Import the collection and hit Run!** 🚀
