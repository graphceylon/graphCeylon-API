/**
 * Complete Database Setup and Seeding Script
 * This script will:
 * 1. Create the users table if it doesn't exist
 * 2. Create test users (admin, user, moderator)
 * 
 * Run with: node setup_and_seed.js
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

// Test users to create
const testUsers = [
  {
    email: 'admin@graphceylon.com',
    password: 'Admin@123456',
    firstName: 'Super',
    lastName: 'Admin',
    role: 'admin',
  },
  {
    email: 'user@graphceylon.com',
    password: 'User@123456',
    firstName: 'Regular',
    lastName: 'User',
    role: 'user',
  },
  {
    email: 'moderator@graphceylon.com',
    password: 'Moderator@123456',
    firstName: 'Test',
    lastName: 'Moderator',
    role: 'moderator',
  },
];

async function createUsersTable() {
  const client = await pool.connect();
  
  try {
    console.log('Creating users table...');
    
    await client.query(`
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
      )
    `);

    console.log('✓ Users table created or already exists');

    // Create indexes
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
    `);
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)
    `);
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)
    `);

    console.log('✓ Indexes created');

  } catch (error) {
    console.error('✗ Error creating table:', error.message);
    throw error;
  } finally {
    client.release();
  }
}

async function createUser(user) {
  const client = await pool.connect();
  
  try {
    // Check if user already exists
    const checkResult = await client.query(
      'SELECT id FROM users WHERE email = $1',
      [user.email]
    );

    if (checkResult.rows.length > 0) {
      console.log(`  ⚠ User ${user.email} already exists`);
      return checkResult.rows[0];
    }

    // Hash password
    const hashedPassword = await bcrypt.hash(user.password, 10);

    // Insert user
    const insertResult = await client.query(
      `INSERT INTO users (
        email,
        first_name,
        last_name,
        role,
        is_active,
        preferences
      ) VALUES ($1, $2, $3, $4, true, '{}')
      RETURNING id, email, first_name, last_name, role`,
      [user.email, user.firstName, user.lastName, user.role]
    );

    const createdUser = insertResult.rows[0];
    console.log(`  ✓ Created ${user.role}: ${createdUser.email}`);
    
    return createdUser;

  } catch (error) {
    console.error(`  ✗ Error creating user ${user.email}:`, error.message);
    throw error;
  } finally {
    client.release();
  }
}

async function displayUsers() {
  const client = await pool.connect();
  
  try {
    const result = await client.query(`
      SELECT id, email, first_name, last_name, role, is_active, created_at
      FROM users 
      WHERE email IN ($1, $2, $3)
      ORDER BY 
        CASE role 
          WHEN 'admin' THEN 1 
          WHEN 'moderator' THEN 2 
          WHEN 'user' THEN 3 
        END
    `, [
      testUsers[0].email,
      testUsers[1].email,
      testUsers[2].email,
    ]);

    if (result.rows.length > 0) {
      console.log('\n' + '='.repeat(70));
      console.log('Test Users Summary:');
      console.log('='.repeat(70));
      console.log('');
      
      result.rows.forEach(user => {
        const testUser = testUsers.find(u => u.email === user.email);
        console.log(`📧 ${user.role.toUpperCase()}`);
        console.log(`   Email:    ${user.email}`);
        console.log(`   Password: ${testUser.password}`);
        console.log(`   Name:     ${user.first_name} ${user.last_name}`);
        console.log(`   Active:   ${user.is_active ? 'Yes' : 'No'}`);
        console.log(`   ID:       ${user.id}`);
        console.log('');
      });
    }

    // Display total count
    const countResult = await client.query('SELECT COUNT(*) as count FROM users');
    console.log('='.repeat(70));
    console.log(`Total users in database: ${countResult.rows[0].count}`);
    console.log('='.repeat(70));

  } catch (error) {
    console.error('Error displaying users:', error.message);
  } finally {
    client.release();
  }
}

async function main() {
  console.log('='.repeat(70));
  console.log('GraphCeylon Database Setup & Seed');
  console.log('='.repeat(70));
  console.log('');

  try {
    // Test database connection
    const testResult = await pool.query('SELECT NOW()');
    console.log('✓ Database connection successful');
    console.log(`  Connected at: ${testResult.rows[0].now}`);
    console.log('');

    // Step 1: Create table
    await createUsersTable();
    console.log('');

    // Step 2: Create test users
    console.log('Creating test users...');
    for (const user of testUsers) {
      await createUser(user);
    }
    console.log('');

    // Step 3: Display created users
    await displayUsers();

    console.log('\n✅ Setup complete! You can now:');
    console.log('   1. Start the user service: cd ../user_service && npm start');
    console.log('   2. Start the auth service: cd ../auth_service && npm start');
    console.log('   3. Start the frontend: cd ../auth-frontend && npm run dev');
    console.log('   4. Login with any of the accounts above');
    console.log('');

  } catch (error) {
    console.error('\n❌ Fatal error:', error.message);
    console.error('\nTroubleshooting:');
    console.error('  - Ensure PostgreSQL is running');
    console.error('  - Check database credentials in user_service/.env');
    console.error('  - Verify database "graphceylon_users" exists');
    console.error('  - Try: psql -U postgres -c "CREATE DATABASE graphceylon_users;"');
    process.exit(1);
  } finally {
    await pool.end();
  }
}

// Run the script
main();
