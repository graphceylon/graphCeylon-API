# 🚀 Quick Start - Postman Hotel Ingestion

## 📋 3-Step Process

### **Step 1: Setup in Postman**
1. Open Postman
2. Create **NEW REQUEST**
3. Set **Method:** `POST`
4. Set **URL:** `http://localhost:8000/hotels/ingest`

### **Step 2: Attach File**
1. Go to **Body** tab
2. Select **form-data**
3. Add key: `file` (change type to **File**)
4. Click **Select Files** → Choose JSON file
5. Click **Send**

### **Step 3: Verify**
Check response shows:
```json
{
  "success": true,
  "message": "Successfully ingested X hotels",
  ...
}
```

---

## 📁 Sample Files Provided

| File | Hotels | Best For |
|------|--------|----------|
| `hotel_single_minimal.json` | 1 | Testing/Learning |
| `hotels_multiple_complete.json` | 5 | Production Use |

**Location:** `services/kg_service/postman_samples/`

---

## ✅ Required JSON Structure

```json
{
  "attractions": [
    {
      "attraction": "Kandy",              // ✅ Must exist in DB
      "hotels": [
        {
          "name": "Hotel Name",           // ✅ Required
          "gps_coordinates": {            // ✅ Required
            "latitude": 7.2906,
            "longitude": 80.6337
          },
          "rate_per_night": 85.0,        // Optional
          "rating": 4.5,                  // Optional
          "amenities": ["Wi-Fi", "Pool"]  // Optional
        }
      ]
    }
  ]
}
```

---

## 🎯 Valid Attractions (Your Database)

✅ Use exact names:
- **Central:** Kandy, Nuwara Eliya, Sigiriya, Dambulla
- **Southern:** Galle, Hikkaduwa, Bentota, Matara
- **Eastern:** Trincomalee, Arugambay, Batticaloa
- **Northern:** Jaffna, Mannar
- **Uva:** Ella
- **And 24 more...**

---

## 🔍 Test Endpoints

### **After Upload, Verify:**

1. **List Hotels:**
   - GET `http://localhost:8000/hotels/`

2. **View Details:**
   - GET `http://localhost:8000/hotels/hotel_paradise_view_hotel_postman`

3. **Check Stats:**
   - GET `http://localhost:8000/hotels/statistics/overview`

---

## 🐛 Common Errors

| Error | Solution |
|-------|----------|
| "Attraction not found" | Use exact name from list above |
| "Invalid JSON" | Validate at jsonlint.com |
| "GPS missing" | Add latitude/longitude |
| Hotels created = 0 | Check attraction name matches DB |

---

## 📦 Import Postman Collection

**File:** `GraphCeylon_Hotel_API.postman_collection.json`

**Import Steps:**
1. Postman → **Import** button
2. Select collection JSON file
3. Collection appears in left sidebar
4. Expand folders to see all requests

---

## 💡 Pro Tip

**Environment Variable:**
1. Create Environment: "GraphCeylon"
2. Add variable: `baseUrl` = `http://localhost:8000`
3. Use `{{baseUrl}}/hotels/ingest` in requests

---

**Full Guide:** `POSTMAN_HOTEL_INGESTION_GUIDE.md`

**Ready to ingest! 🎉**
