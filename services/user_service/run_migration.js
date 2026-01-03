/**
 * Run Database Migration: Create User Profiles Table
 * 
 * Run with: node run_migration.js
 */

const { Pool } = require('pg');
const fs = require('fs');
const path = require('path');

const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432'),
  user: process.env.DB_USERNAME || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  database: process.env.DB_DATABASE || 'graphceylon_users',
});

async function runMigration() {
  const client = await pool.connect();
  
  try {
    console.log('🔧 Starting database migration...\n');

    // Read the SQL file
    const sqlFilePath = path.join(__dirname, 'migrations', '002_create_user_profiles.sql');
    const sql = fs.readFileSync(sqlFilePath, 'utf8');

    // Execute the migration
    await client.query(sql);

    console.log('✅ Migration completed successfully!\n');
    console.log('Created:');
    console.log('  - user_profiles table');
    console.log('  - Indexes for fast queries');
    console.log('  - Auto-update trigger for updated_at');
    console.log('  - GIN indexes for JSONB columns\n');

    // Verify the table was created
    const result = await client.query(`
      SELECT column_name, data_type 
      FROM information_schema.columns 
      WHERE table_name = 'user_profiles'
      ORDER BY ordinal_position
    `);

    console.log('📋 Table structure:');
    result.rows.forEach(row => {
      console.log(`  - ${row.column_name}: ${row.data_type}`);
    });

  } catch (error) {
    console.error('❌ Migration failed:', error.message);
    
    if (error.message.includes('already exists')) {
      console.log('\n⚠️  Table already exists. Migration skipped.');
    } else {
      throw error;
    }
  } finally {
    client.release();
    await pool.end();
  }
}

runMigration().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
