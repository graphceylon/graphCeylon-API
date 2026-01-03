-- GraphCeylon User Service Database Setup
-- Run this script to create the users table and initial data

-- Create the users table
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  role VARCHAR(50) NOT NULL DEFAULT 'user',
  is_active BOOLEAN DEFAULT true,
  avatar VARCHAR(500),
  bio TEXT,
  preferences JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  last_login_at TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- Create enum type for user roles (optional, for type safety)
DO $$ BEGIN
  CREATE TYPE user_role AS ENUM ('user', 'admin', 'moderator');
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

-- Update role column to use enum (optional)
-- ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role;

-- Display table structure
\d users
