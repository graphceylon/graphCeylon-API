# 📮 Postman Guide - Hotel Data Ingestion

Complete guide to manually ingest hotel data using Postman.

---

## 🚀 Quick Start

### **Endpoint Details**
- **URL:** `http://localhost:8000/hotels/ingest`
- **Method:** `POST`
- **Content-Type:** `multipart/form-data`
- **Body Type:** Form-data with file upload

---

## 📋 Step-by-Step Instructions

### **Step 1: Open Postman**
1. Launch Postman application
2. Create a new request or use an existing collection

### **Step 2: Configure Request**
1. **Method:** Select `POST` from dropdown
2. **URL:** Enter `http://localhost:8000/hotels/ingest`
3. **Headers:** (Auto-configured by Postman for file upload)
   - `Content-Type: multipart/form-data` (automatic)

### **Step 3: Setup Body**
1. Click on **"Body"** tab
2. Select **"form-data"** radio button
3. In the KEY column:
   - Enter: `file`
   - Change type from "Text" to **"File"** using the dropdown on the right
4. In the VALUE column:
   - Click **"Select Files"** button
   - Choose your hotel JSON file (e.g., `hotels_sample.json`)

### **Step 4: Send Request**
1. Click the blue **"Send"** button
2. Wait for response (typically 1-2 seconds)
3. Check response in the lower panel

---

## 📦 Sample JSON Files

### **Option 1: Single Hotel (Minimal)**
File: `hotel_single_minimal.json`

```json
{
  "attractions": [
    {
      "attraction": "Kandy",
      "attraction_description": "Cultural capital of Sri Lanka",
      "geolocation": {
        "latitude": 7.2906,
        "longitude": 80.6337
      },
      "hotels": [
        {
          "name": "Paradise View Hotel",
          "description": "Scenic hotel with mountain views",
          "link": "https://example.com/paradise-view",
          "gps_coordinates": {
            "latitude": 7.2906,
            "longitude": 80.6337
          },
          "rate_per_night": 85.0,
          "check_in_time": "2:00 PM",
          "check_out_time": "12:00 PM",
          "rating": 4.5,
          "reviews_count": 250,
          "amenities": ["Wi-Fi", "Pool", "Restaurant"],
          "images": ["https://example.com/image1.jpg"],
          "nearby_places": []
        }
      ]
    }
  ],
  "scrape_metadata": {
    "source": "manual_postman",
    "timestamp": "2025-12-31T12:00:00"
  }
}
```

### **Option 2: Multiple Hotels (Complete)**
File: `hotels_sample_complete.json`

```json
{
  "attractions": [
    {
      "attraction": "Galle",
      "attraction_description": "Historic fort city on southern coast",
      "geolocation": {
        "latitude": 6.0535,
        "longitude": 80.2210
      },
      "hotels": [
        {
          "name": "Ocean Blue Resort",
          "description": "Beachfront resort with stunning ocean views",
          "link": "https://example.com/ocean-blue",
          "gps_coordinates": {
            "latitude": 6.0535,
            "longitude": 80.2210
          },
          "type": "hotel",
          "province": "Southern",
          "rate_per_night": 150.0,
          "check_in_time": "3:00 PM",
          "check_out_time": "11:00 AM",
          "rating": 4.7,
          "reviews_count": 456,
          "amenities": [
            "Wi-Fi",
            "Pool",
            "Beach access",
            "Restaurant",
            "Bar",
            "Spa",
            "Air conditioning",
            "Parking"
          ],
          "images": [
            "https://example.com/ocean1.jpg",
            "https://example.com/ocean2.jpg"
          ],
          "nearby_places": [
            {
              "name": "Galle Fort",
              "category": "Historical landmark",
              "rating": 4.8,
              "reviews": 5000
            },
            {
              "name": "Unawatuna Beach",
              "category": "Beach",
              "rating": 4.6,
              "reviews": 3200
            }
          ]
        },
        {
          "name": "Fort Heritage Inn",
          "description": "Colonial-style boutique hotel inside the fort",
          "link": "https://example.com/fort-heritage",
          "gps_coordinates": {
            "latitude": 6.0271,
            "longitude": 80.2168
          },
          "type": "boutique",
          "province": "Southern",
          "rate_per_night": 120.0,
          "check_in_time": "2:00 PM",
          "check_out_time": "12:00 PM",
          "rating": 4.8,
          "reviews_count": 320,
          "amenities": [
            "Wi-Fi",
            "Restaurant",
            "Air conditioning",
            "Breakfast",
            "Room service"
          ],
          "images": [
            "https://example.com/fort1.jpg"
          ],
          "nearby_places": [
            {
              "name": "Dutch Reformed Church",
              "category": "Church",
              "rating": 4.5,
              "reviews": 800
            },
            {
              "name": "National Maritime Museum",
              "category": "Museum",
              "rating": 4.2,
              "reviews": 450
            }
          ]
        }
      ]
    },
    {
      "attraction": "Ella",
      "attraction_description": "Scenic hill country town",
      "geolocation": {
        "latitude": 6.8667,
        "longitude": 81.0467
      },
      "hotels": [
        {
          "name": "Mountain Peak Lodge",
          "description": "Cozy lodge with panoramic mountain views",
          "link": "https://example.com/mountain-peak",
          "gps_coordinates": {
            "latitude": 6.8667,
            "longitude": 81.0467
          },
          "type": "lodge",
          "province": "Uva",
          "rate_per_night": 65.0,
          "check_in_time": "2:00 PM",
          "check_out_time": "11:00 AM",
          "rating": 4.6,
          "reviews_count": 180,
          "amenities": [
            "Wi-Fi",
            "Restaurant",
            "Mountain view",
            "Hot water",
            "Parking"
          ],
          "images": [
            "https://example.com/mountain1.jpg"
          ],
          "nearby_places": [
            {
              "name": "Nine Arch Bridge",
              "category": "Bridge",
              "rating": 4.9,
              "reviews": 2500
            },
            {
              "name": "Little Adam's Peak",
              "category": "Hiking trail",
              "rating": 4.7,
              "reviews": 1800
            }
          ]
        }
      ]
    }
  ],
  "scrape_metadata": {
    "source": "postman_manual",
    "timestamp": "2025-12-31T12:00:00",
    "check_in_date": "2026-01-15",
    "check_out_date": "2026-01-17"
  }
}
```

---

## ✅ Expected Response

### **Success Response (200 OK)**
```json
{
  "success": true,
  "message": "Successfully ingested 3 hotels",
  "results": {
    "total_attractions": 2,
    "total_hotels_created": 3,
    "total_relationships": 45,
    "total_pois": 5,
    "total_amenities": 15,
    "total_errors": 0,
    "attraction_results": [
      {
        "attraction": "Galle",
        "hotels_created": 2,
        "relationships": 30,
        "errors": []
      },
      {
        "attraction": "Ella",
        "hotels_created": 1,
        "relationships": 15,
        "errors": []
      }
    ],
    "total_time_seconds": 0.45
  }
}
```

### **Error Responses**

**400 Bad Request - Invalid File Type**
```json
{
  "detail": "Only JSON files are accepted"
}
```

**400 Bad Request - Attraction Not Found**
```json
{
  "success": true,
  "message": "Successfully ingested 0 hotels",
  "results": {
    "total_attractions": 1,
    "total_hotels_created": 0,
    "total_errors": 1,
    "attraction_results": [
      {
        "attraction": "NonExistentPlace",
        "hotels_created": 0,
        "errors": [
          "Attraction 'NonExistentPlace' not found in database"
        ]
      }
    ]
  }
}
```

---

## 🔍 Verification Steps

### **1. Check Ingestion Success**
```bash
# View response in Postman - look for:
- "success": true
- "total_hotels_created": > 0
- "total_errors": 0
```

### **2. Verify via GET Request**
Create a new Postman request:
- **Method:** `GET`
- **URL:** `http://localhost:8000/hotels/`
- **Params:** `limit=10&offset=0`

### **3. Check Hotel Details**
- **Method:** `GET`
- **URL:** `http://localhost:8000/hotels/{hotel_id}`
- Use hotel_id from the list response

### **4. View Statistics**
- **Method:** `GET`
- **URL:** `http://localhost:8000/hotels/statistics/overview`

---

## 🛠️ Troubleshooting

### **Issue: "Attraction not found"**
**Solution:** Ensure attraction name matches exactly with existing attractions in database.

Valid attractions (from your database):
- Sigiriya, Kandy, Galle, Colombo, Ella, Nuwara Eliya, Anuradhapura, Dambulla, etc.

### **Issue: "Invalid JSON file format"**
**Solution:** 
1. Validate JSON at https://jsonlint.com/
2. Ensure proper quotes (use `"` not `'`)
3. Check for trailing commas

### **Issue: "GPS coordinates missing"**
**Solution:** Every hotel MUST have valid `gps_coordinates`:
```json
"gps_coordinates": {
  "latitude": 7.2906,
  "longitude": 80.6337
}
```

### **Issue: Hotels created = 0**
**Solution:**
- Check that attraction exists in database
- Verify GPS coordinates are valid numbers
- Ensure required fields are present (name, gps_coordinates)

---

## 📝 Field Reference

### **Required Fields**
| Field | Type | Example |
|-------|------|---------|
| `name` | string | "Ocean Blue Resort" |
| `gps_coordinates` | object | `{"latitude": 6.0535, "longitude": 80.2210}` |

### **Optional Fields**
| Field | Type | Example |
|-------|------|---------|
| `description` | string | "Beachfront resort..." |
| `link` | string | "https://example.com" |
| `rate_per_night` | number | 150.0 |
| `rating` | number | 4.5 (0-5) |
| `reviews_count` | integer | 250 |
| `check_in_time` | string | "2:00 PM" |
| `check_out_time` | string | "12:00 PM" |
| `amenities` | array | ["Wi-Fi", "Pool"] |
| `images` | array | ["url1", "url2"] |
| `nearby_places` | array | See structure above |
| `type` | string | "hotel", "resort", "boutique" |
| `province` | string | "Southern", "Central" |

---

## 🎯 Best Practices

1. **Start Small:** Test with 1-2 hotels first
2. **Validate JSON:** Use online validators before uploading
3. **Use Existing Attractions:** Match exact names from database
4. **Include GPS:** Always provide valid coordinates
5. **Test Response:** Check for errors before bulk import
6. **Backup Data:** Keep copy of JSON files

---

## 📊 Postman Collection

Save this as a Postman Collection for quick access:

### **Collection Structure**
```
Hotel API
├── Ingest
│   ├── Ingest Single Hotel
│   └── Ingest Multiple Hotels
├── Verify
│   ├── List All Hotels
│   ├── Get Hotel Details
│   └── Get Statistics
└── Cleanup
    ├── Delete Single Hotel
    └── Delete by Attraction
```

---

## 💡 Pro Tips

1. **Use Environment Variables in Postman:**
   - `{{baseUrl}}` = `http://localhost:8000`
   - `{{hotelUrl}}` = `{{baseUrl}}/hotels`

2. **Save Responses:**
   - Use Postman's "Save Response" to keep examples

3. **Automation:**
   - Create tests in Postman to verify `success: true`
   - Use Collection Runner for batch testing

4. **Version Control:**
   - Keep your JSON files in version control
   - Document changes to hotel data structure

---

## 📞 Need Help?

Check the API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

**Happy Testing! 🚀**
