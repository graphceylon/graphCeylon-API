-- Quick Test Queries for Tourism Profile System
-- Run these in DBeaver or any PostgreSQL client

-- 1. Check if user_profiles table exists and is empty
SELECT COUNT(*) as total_profiles FROM user_profiles;

-- 2. After registering a new user, check if profile was created
SELECT 
    user_id,
    email,
    full_name,
    country,
    budget_level,
    onboarding->>'completed' as onboarding_completed,
    created_at
FROM user_profiles 
ORDER BY created_at DESC 
LIMIT 5;

-- 3. View full profile with all JSONB data
SELECT 
    user_id,
    email,
    full_name,
    jsonb_pretty(preference_overrides) as preferences,
    jsonb_pretty(onboarding) as onboarding_data,
    jsonb_pretty(events) as events_log
FROM user_profiles 
ORDER BY created_at DESC 
LIMIT 1;

-- 4. Check specific preference overrides
SELECT 
    email,
    preference_overrides->'accommodation'->>'type' as preferred_accommodation,
    preference_overrides->'accommodation'->'amenities' as required_amenities
FROM user_profiles
WHERE preference_overrides IS NOT NULL;

-- 5. View onboarding questionnaire answers
SELECT 
    email,
    onboarding->>'completed' as completed,
    onboarding->'answers'->>'travelFrequency' as travel_frequency,
    onboarding->'answers'->>'travelPurpose' as travel_purpose
FROM user_profiles
WHERE onboarding IS NOT NULL;

-- 6. View user events/activity log
SELECT 
    email,
    events->'savedPOIs' as saved_places,
    events->'completedTrips' as completed_trips
FROM user_profiles
WHERE events IS NOT NULL;
