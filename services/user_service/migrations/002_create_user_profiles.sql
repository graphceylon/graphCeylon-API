/**
 * Migration: Create User Profiles Table
 * 
 * This migration creates a comprehensive user_profiles table with JSONB storage
 * for flexible tourism preferences and onboarding data.
 * 
 * Run with: psql -U postgres -d graphceylon_users -f migrations/002_create_user_profiles.sql
 */

-- Drop old simple table if exists (backup data first if needed!)
-- DROP TABLE IF EXISTS users CASCADE;

-- Create comprehensive user profiles table
CREATE TABLE IF NOT EXISTS user_profiles (
  -- Identity (matches auth service UUID)
  user_id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  username VARCHAR(100),
  full_name VARCHAR(255),
  
  -- Demographics
  country VARCHAR(100),
  date_of_birth DATE,
  
  -- Languages (stored as array for secondary languages)
  primary_language VARCHAR(10) DEFAULT 'en',
  secondary_languages TEXT[] DEFAULT '{}',
  
  -- Travel defaults
  home_city VARCHAR(100),
  default_party VARCHAR(20) DEFAULT 'unknown', -- solo, couple, family, friends, unknown
  budget_level VARCHAR(20) DEFAULT 'unknown',  -- low, mid, high, unknown
  
  -- Core JSONB storage for flexibility
  preference_overrides JSONB DEFAULT '{
    "travelStyle": [],
    "activityPreference": "unknown",
    "pacePreference": "unknown",
    "adventureLevel": "unknown",
    "preferredTransport": [],
    "foodPreferences": [],
    "mustHaveAmenities": [],
    "accommodationType": "any",
    "starPreference": "any",
    "cancellationPreference": "any"
  }',
  
  onboarding JSONB DEFAULT '{
    "completed": false,
    "questionnaireVersion": 1,
    "answers": {}
  }',
  
  events JSONB DEFAULT '[]',
  
  -- RBAC & Status
  role VARCHAR(50) DEFAULT 'user',
  is_active BOOLEAN DEFAULT true,
  
  -- Versioning
  profile_version INTEGER DEFAULT 1,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  last_login_at TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_role ON user_profiles(role);
CREATE INDEX IF NOT EXISTS idx_user_profiles_country ON user_profiles(country);
CREATE INDEX IF NOT EXISTS idx_user_profiles_budget_level ON user_profiles(budget_level);
CREATE INDEX IF NOT EXISTS idx_user_profiles_is_active ON user_profiles(is_active);

-- GIN indexes for JSONB searches (fast lookups inside JSON)
CREATE INDEX IF NOT EXISTS idx_preference_overrides ON user_profiles USING GIN (preference_overrides);
CREATE INDEX IF NOT EXISTS idx_onboarding ON user_profiles USING GIN (onboarding);
CREATE INDEX IF NOT EXISTS idx_events ON user_profiles USING GIN (events);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS trigger_update_user_profiles_updated_at ON user_profiles;
CREATE TRIGGER trigger_update_user_profiles_updated_at
  BEFORE UPDATE ON user_profiles
  FOR EACH ROW
  EXECUTE FUNCTION update_user_profiles_updated_at();

-- Comments for documentation
COMMENT ON TABLE user_profiles IS 'Comprehensive user profiles for tourism recommendations with JSONB storage';
COMMENT ON COLUMN user_profiles.preference_overrides IS 'Travel preferences, accommodation needs, food restrictions, etc.';
COMMENT ON COLUMN user_profiles.onboarding IS 'Onboarding questionnaire answers and completion status';
COMMENT ON COLUMN user_profiles.events IS 'User activity log: saved POIs, completed trips, feedback';
COMMENT ON COLUMN user_profiles.profile_version IS 'Incremented on every update for optimistic locking';
