/**
 * Script to Create Super Admin User
 * Run this with: node create_admin_user.js
 * 
 * Make sure to:
 * 1. Install dependencies: npm install bcrypt pg
 * 2. Update DATABASE_URL with your connection string
 */

const bcrypt = require('bcrypt');
const { Pool } = require('pg');

// Database configuration
const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432'),
  user: process.env.DB_USERNAME || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  database: process.env.DB_DATABASE || 'graphceylon_users',
});

// Admin user details
const adminUser = {
  email: 'admin@graphceylon.com',
  password: 'Admin@123456',
  firstName: 'Super',
  lastName: 'Admin',
  role: 'admin',
};

const regularUser = {
  email: 'user@graphceylon.com',
  password: 'User@123456',
  firstName: 'Regular',
  lastName: 'User',
  role: 'user',
};

const moderatorUser = {
  email: 'moderator@graphceylon.com',
  password: 'Moderator@123456',
  firstName: 'Test',
  lastName: 'Moderator',
  role: 'moderator',
};

async function createUser(user) {
  const client = await pool.connect();
  
  try {
    // Check if user already exists
    const checkResult = await client.query(
      'SELECT id FROM users WHERE email = $1',
      [user.email]
    );

    if (checkResult.rows.length > 0) {
      console.log(`✓ User ${user.email} already exists`);
      return;
    }

    // Hash password
    const hashedPassword = await bcrypt.hash(user.password, 10);

    // Insert user
    const insertResult = await client.query(
      `INSERT INTO users (
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
      ) VALUES (
        gen_random_uuid(),
        $1,
        $2,
        $3,
        $4,
        $5,
        true,
        true,
        NOW(),
        NOW()
      )
      RETURNING id, email, "firstName", "lastName", role`,
      [user.email, hashedPassword, user.firstName, user.lastName, user.role]
    );

    const createdUser = insertResult.rows[0];
    console.log(`✓ Created ${user.role}: ${createdUser.email}`);
    console.log(`  ID: ${createdUser.id}`);
    console.log(`  Name: ${createdUser.firstName} ${createdUser.lastName}`);
    console.log(`  Password: ${user.password}`);
    console.log('');

  } catch (error) {
    console.error(`✗ Error creating user ${user.email}:`, error.message);
  } finally {
    client.release();
  }
}

async function main() {
  console.log('='.repeat(60));
  console.log('Creating Test Users for GraphCeylon');
  console.log('='.repeat(60));
  console.log('');

  try {
    // Test database connection
    await pool.query('SELECT NOW()');
    console.log('✓ Database connection successful\n');

    // Create users
    await createUser(adminUser);
    await createUser(regularUser);
    await createUser(moderatorUser);

    // Display summary
    const result = await pool.query(
      `SELECT id, email, "firstName", "lastName", role, "isEmailVerified", "isActive"
       FROM users 
       WHERE email IN ($1, $2, $3)
       ORDER BY 
         CASE role 
           WHEN 'admin' THEN 1 
           WHEN 'moderator' THEN 2 
           WHEN 'user' THEN 3 
         END`,
      [adminUser.email, regularUser.email, moderatorUser.email]
    );

    if (result.rows.length > 0) {
      console.log('='.repeat(60));
      console.log('Test Users Summary:');
      console.log('='.repeat(60));
      console.log('');
      result.rows.forEach(user => {
        const password = user.role === 'admin' ? adminUser.password 
          : user.role === 'moderator' ? moderatorUser.password 
          : regularUser.password;
        
        console.log(`Role: ${user.role.toUpperCase()}`);
        console.log(`  Email: ${user.email}`);
        console.log(`  Password: ${password}`);
        console.log(`  Name: ${user.firstName} ${user.lastName}`);
        console.log(`  Verified: ${user.isEmailVerified ? 'Yes' : 'No'}`);
        console.log(`  Active: ${user.isActive ? 'Yes' : 'No'}`);
        console.log('');
      });
    }

    console.log('='.repeat(60));
    console.log('You can now login with any of these accounts!');
    console.log('='.repeat(60));

  } catch (error) {
    console.error('Fatal error:', error.message);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

// Run the script
main();
