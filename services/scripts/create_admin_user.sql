-- Script to Create Super Admin User
-- Run this in your PostgreSQL database

-- First, let's check if the user already exists
SELECT * FROM users WHERE email = 'admin@graphceylon.com';

-- If user doesn't exist, insert the admin user
-- Note: This password is 'Admin@123456' hashed with bcrypt (10 rounds)
-- You should generate your own hash using bcrypt

INSERT INTO users (
  id,
  email,
  password,
  "firstName",
  "lastName",
  role,
  "isEmailVerified",
  "isActive",
  "createdAt",
  "updatedAt"
)
SELECT
  gen_random_uuid(),
  'admin@graphceylon.com',
  '$2b$10$vXZ5J8ZQf6F7hGJ8K5YyZuXqR5YqH6L7K8M9N0P1Q2R3S4T5U6V7W', -- This is a placeholder, generate actual hash
  'Super',
  'Admin',
  'admin',
  true,
  true,
  NOW(),
  NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM users WHERE email = 'admin@graphceylon.com'
);

-- Alternative: If you registered via the API and want to upgrade to admin
-- Uncomment the line below and replace the email
-- UPDATE users SET role = 'admin', "isEmailVerified" = true WHERE email = 'admin@graphceylon.com';

-- Create a few test users with different roles
INSERT INTO users (
  id,
  email,
  password,
  "firstName",
  "lastName",
  role,
  "isEmailVerified",
  "isActive",
  "createdAt",
  "updatedAt"
)
SELECT
  gen_random_uuid(),
  'user@graphceylon.com',
  '$2b$10$vXZ5J8ZQf6F7hGJ8K5YyZuXqR5YqH6L7K8M9N0P1Q2R3S4T5U6V7W',
  'Regular',
  'User',
  'user',
  true,
  true,
  NOW(),
  NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM users WHERE email = 'user@graphceylon.com'
);

INSERT INTO users (
  id,
  email,
  password,
  "firstName",
  "lastName",
  role,
  "isEmailVerified",
  "isActive",
  "createdAt",
  "updatedAt"
)
SELECT
  gen_random_uuid(),
  'moderator@graphceylon.com',
  '$2b$10$vXZ5J8ZQf6F7hGJ8K5YyZuXqR5YqH6L7K8M9N0P1Q2R3S4T5U6V7W',
  'Test',
  'Moderator',
  'moderator',
  true,
  true,
  NOW(),
  NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM users WHERE email = 'moderator@graphceylon.com'
);

-- Verify the users were created
SELECT id, email, "firstName", "lastName", role, "isEmailVerified", "isActive" 
FROM users 
WHERE email IN ('admin@graphceylon.com', 'user@graphceylon.com', 'moderator@graphceylon.com');
