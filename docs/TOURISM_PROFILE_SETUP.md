# Tourism Profile System - Setup & Testing Guide

## 🎯 Overview

This guide walks you through setting up the complete tourism profile system with rich user preferences for personalized recommendations.

## 📋 Prerequisites

- PostgreSQL 16 running (port 5432)
- Redis 7 running (port 6379)
- Node.js 18+
- Both services built and ready

---

## Step 1: Database Migration

### Run the migration SQL script:

```bash
cd services/user_service
psql -U postgres -d graphceylon_users -f migrations/002_create_user_profiles.sql
```

**What this does:**
- Creates `user_profiles` table with JSONB columns
- Adds indexes for fast queries
- Sets up auto-update triggers for `updated_at`

### (Optional) Migrate existing users:

If you have existing users in the old `users` table:

```bash
cd services/user_service
node migrations/migrate_existing_users.js
```

---

## Step 2: Environment Configuration

### Auth Service (.env):

```bash
# services/auth_service/.env

# Server
PORT=8004

# JWT (use same secret in both services!)
JWT_SECRET=your-super-secret-jwt-key-change-in-production
JWT_REFRESH_SECRET=your-super-secret-refresh-key-change-in-production

# User Service Integration
USER_SERVICE_URL=http://localhost:8005
SERVICE_TOKEN=your-internal-service-secret-token

# Email (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
EMAIL_FROM=your-email@gmail.com

# Frontend
FRONTEND_URL=http://localhost:5173
```

### User Service (.env):

```bash
# services/user_service/.env

# Server
PORT=8005

# Database
DB_HOST=localhost
DB_PORT=5432
DB_USERNAME=postgres
DB_PASSWORD=postgres
DB_DATABASE=graphceylon_users

# JWT (MUST match auth service!)
JWT_SECRET=your-super-secret-jwt-key-change-in-production

# Service Token (for internal calls)
SERVICE_TOKEN=your-internal-service-secret-token
```

---

## Step 3: Install Dependencies & Build

### Auth Service:

```bash
cd services/auth_service
npm install axios  # Add axios for HTTP requests
npm run build
```

### User Service:

```bash
cd services/user_service
npm run build
```

---

## Step 4: Start Services

### Terminal 1 - Auth Service:

```bash
cd services/auth_service
npm start
```

Should see:
```
🚀 Auth Service listening on port 8004
✅ Redis connected successfully
```

### Terminal 2 - User Service:

```bash
cd services/user_service
npm start
```

Should see:
```
🚀 User Service listening on port 8005
✅ Database connected successfully
```

### Terminal 3 - Frontend:

```bash
cd services/auth-frontend
npm run dev
```

---

## Step 5: Test Registration Flow

### 1. Register a new user:

Go to http://localhost:5173/register

Fill in:
- Email: `devanga@example.com`
- Password: `Devanga@123`
- First Name: `Devanga`
- Last Name: `Palliyaguru`

**Behind the scenes:**
1. Auth service creates user in memory
2. Auth service calls user service: `POST /api/users/profile/create-minimal`
3. User service creates basic profile in PostgreSQL
4. User gets JWT tokens
5. User is logged in

### 2. Check the database:

```sql
SELECT user_id, email, full_name, onboarding->'completed' as onboarding_status
FROM user_profiles;
```

You should see the new user with `onboarding_status = false`.

---

## Step 6: Test Profile Endpoints

### Get current user's profile:

```bash
# Get token from localStorage in browser console:
# localStorage.getItem('token')

curl -X GET http://localhost:8005/api/users/profile/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "identity": {
      "userId": "uuid-here",
      "email": "devanga@example.com",
      "fullName": "Devanga Palliyaguru"
    },
    "onboarding": {
      "completed": false,
      "questionnaireVersion": 1,
      "answers": {}
    },
    "preferenceOverrides": {
      "accommodationType": "any",
      "starPreference": "any",
      "travelStyle": [],
      ...
    }
  }
}
```

---

## Step 7: Complete Onboarding

### Submit onboarding questionnaire:

```bash
curl -X POST http://localhost:8005/api/users/profile/YOUR_USER_ID/onboarding \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "answers": {
      "likes_nature": true,
      "travels_with_kids": true,
      "preferred_activities": ["hiking", "cultural_tours", "wildlife"],
      "accommodation_type": "hotel",
      "star_rating": "3_star_plus",
      "max_budget_per_night": 18000,
      "budget_flexibility": 0.4,
      "dietary_restrictions": ["halal"],
      "preferred_transport": ["train", "car"],
      "avoid_crowds": true,
      "adventure_seeker": true,
      "eco_conscious": true
    }
  }'
```

**What happens:**
- Profile service analyzes answers
- Derives structured preferences:
  - `travelStyle`: `["hiking", "cultural_tours", "wildlife"]`
  - `activityPreference`: `"outdoor"`
  - `adventureLevel`: `"high"`
  - `accommodationType`: `"hotel"`
  - `starPreference`: `"3_star_plus"`
  - `budgetPerNightLkr`: `18000`
  - `mustHaveAmenities`: `["wifi", "ac", "family_rooms", "breakfast"]`
  - `avoidCrowds`: `true`
  - `ecoPreference`: `0.8`

### Check updated profile:

```sql
SELECT 
  email,
  onboarding->'completed' as onboarding_complete,
  preference_overrides->'accommodationType' as accommodation,
  preference_overrides->'budgetPerNightLkr' as budget,
  preference_overrides->'travelStyle' as travel_style
FROM user_profiles
WHERE email = 'devanga@example.com';
```

---

## Step 8: Test Profile Patching

### Update preferences incrementally:

```bash
curl -X PATCH http://localhost:8005/api/users/profile/YOUR_USER_ID \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "user_text",
    "homeCity": "Colombo",
    "defaultParty": "family",
    "preferenceOverrides": {
      "walkingToleranceMinutes": 90,
      "rainPreference": "avoid_rain",
      "temperaturePreference": "moderate"
    }
  }'
```

**Result:**
- Profile version incremented
- Preferences merged intelligently
- Timestamp updated

---

## Step 9: Test AI Agent Queries

### Get accommodation preferences (for HotelAgent):

```bash
curl -X GET http://localhost:8005/api/users/profile/YOUR_USER_ID/preferences/accommodation \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "accommodationType": "hotel",
  "starPreference": "3_star_plus",
  "mustHaveAmenities": ["wifi", "ac", "family_rooms", "breakfast"],
  "cancellationPreference": "any",
  "budgetPerNightLkr": 18000,
  "budgetFlexibility": 0.4,
  "partySize": 4
}
```

### Get travel style (for Recommender):

```bash
curl -X GET http://localhost:8005/api/users/profile/YOUR_USER_ID/preferences/travel-style \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "travelStyle": ["hiking", "cultural_tours", "wildlife"],
  "activityPreference": "outdoor",
  "pacePreference": "balanced",
  "adventureLevel": "high",
  "avoidCrowds": true,
  "ecoPreference": 0.8
}
```

---

## Step 10: Test Event Logging

### Log a saved POI:

```bash
curl -X POST http://localhost:8005/api/users/profile/YOUR_USER_ID/events \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "eventType": "saved_poi",
    "payload": {
      "poiId": "sigiriya_rock",
      "poiName": "Sigiriya Rock Fortress",
      "category": "cultural_heritage"
    }
  }'
```

### Log a completed trip:

```bash
curl -X POST http://localhost:8005/api/users/profile/YOUR_USER_ID/events \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "eventType": "completed_trip",
    "payload": {
      "tripId": "trip_123",
      "destinations": ["Kandy", "Ella", "Galle"],
      "duration_days": 7,
      "satisfaction_rating": 5,
      "actual_budget_spent_lkr": 150000
    }
  }'
```

### Check events:

```sql
SELECT 
  email,
  jsonb_array_length(events) as event_count,
  events
FROM user_profiles
WHERE email = 'devanga@example.com';
```

---

## 📊 Verify Complete System

### Check registration sync:

1. Register new user in frontend
2. Watch auth service logs for: `User profile synced with user service`
3. Query database:

```sql
SELECT * FROM user_profiles ORDER BY created_at DESC LIMIT 1;
```

### Check profile versioning:

```sql
SELECT 
  email,
  profile_version,
  updated_at
FROM user_profiles
ORDER BY updated_at DESC;
```

Each PATCH should increment `profile_version`.

---

## 🔍 Troubleshooting

### User service shows "Profile not found":

- Check if profile was created during registration
- Run: `SELECT * FROM user_profiles WHERE email = 'your-email'`
- If missing, auth service didn't sync (check logs)

### Auth service can't reach user service:

- Verify user service is running on port 8005
- Check `.env` has correct `USER_SERVICE_URL`
- Check firewall/network settings

### Database migration failed:

```bash
# Drop and recreate (⚠️ loses data)
DROP TABLE user_profiles;
psql -U postgres -d graphceylon_users -f migrations/002_create_user_profiles.sql
```

### Onboarding doesn't update preferences:

- Check request body has `answers` object
- Verify derived preferences logic in `ProfileService.derivePreferencesFromAnswers()`

---

## 🎉 Success!

You now have a complete tourism profile system with:

✅ Rich user profiles with JSONB storage
✅ Onboarding questionnaire with smart preference derivation
✅ Profile patching for incremental updates
✅ AI agent query endpoints for recommendations
✅ Event logging for learning user behavior
✅ Auth → User service synchronization

Your AI agents (HotelAgent, Recommender, CrowdEngine, Itinerary Planner) can now query user preferences to provide personalized, explainable tourism recommendations! 🚀
