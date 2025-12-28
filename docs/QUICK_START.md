# Quick Start: Tourism Profile System

## ✅ Implementation Complete!

All files have been created and services are ready to run.

## 🚀 Quick Start (5 minutes)

### 1. Run Database Migration

```bash
cd services/user_service
psql -U postgres -d graphceylon_users -f migrations/002_create_user_profiles.sql
```

### 2. Update Environment Files

**Auth Service** (`.env`):
```bash
USER_SERVICE_URL=http://localhost:8005
SERVICE_TOKEN=your-secret-token-here
FRONTEND_URL=http://localhost:5173
```

**User Service** (`.env`):
```bash
SERVICE_TOKEN=your-secret-token-here
```

### 3. Start Services

```bash
# Terminal 1 - Auth Service
cd services/auth_service
npm start

# Terminal 2 - User Service  
cd services/user_service
npm start

# Terminal 3 - Frontend
cd services/auth-frontend
npm run dev
```

### 4. Test Registration

1. Go to http://localhost:5173/register
2. Register a new user
3. Check logs for: `User profile synced with user service`
4. Query database:

```sql
SELECT * FROM user_profiles ORDER BY created_at DESC LIMIT 1;
```

## 📚 What Was Implemented

### New Files Created:

**User Service:**
- `src/types/profile.types.ts` - Complete tourism profile types
- `src/repositories/profile.repository.ts` - JSONB operations
- `src/services/profile.service.ts` - Business logic
- `src/controllers/profile.controller.ts` - API handlers
- `src/routes/profile.routes.ts` - Endpoints
- `migrations/002_create_user_profiles.sql` - Database schema
- `migrations/migrate_existing_users.js` - Migration script

**Auth Service:**
- Updated `src/services/auth.service.ts` - Added profile sync
- Updated `src/config/index.ts` - Added userServiceUrl

**Documentation:**
- `docs/TOURISM_PROFILE_SETUP.md` - Complete setup guide

### New API Endpoints:

```
POST   /api/users/profile/upsert
GET    /api/users/profile/me
GET    /api/users/profile/:userId
PATCH  /api/users/profile/:userId
POST   /api/users/profile/:userId/onboarding
POST   /api/users/profile/:userId/events
GET    /api/users/profile/:userId/preferences/accommodation
GET    /api/users/profile/:userId/preferences/travel-style
POST   /api/users/profile/create-minimal (internal)
```

### Key Features:

✅ JSONB storage for flexible preferences
✅ Onboarding questionnaire with smart derivation
✅ Profile patching for incremental updates
✅ Event logging for user behavior tracking
✅ AI agent query endpoints
✅ Auth → User service synchronization
✅ Profile versioning for optimistic locking
✅ Automatic timestamp management

## 🎯 Next Steps

1. **Run migration** - Creates user_profiles table
2. **Test registration** - Verifies auth→user sync
3. **Test onboarding** - Complete questionnaire via API
4. **Query preferences** - Test AI agent endpoints
5. **Log events** - Track user interactions

## 📖 Full Documentation

See `docs/TOURISM_PROFILE_SETUP.md` for:
- Detailed endpoint testing
- Sample curl commands
- Database queries
- Troubleshooting guide

## 🎉 You're Ready!

Your tourism profile system is now fully implemented and ready for personalized recommendations!
