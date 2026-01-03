/**
 * Migration Script: Migrate Existing Users to New Profile Structure
 * 
 * Run with: node migrations/migrate_existing_users.js
 */

const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432'),
  user: process.env.DB_USERNAME || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  database: process.env.DB_DATABASE || 'graphceylon_users',
});

async function migrateUsers() {
  const client = await pool.connect();
  
  try {
    console.log('Starting user migration...\n');

    // Check if old users table exists
    const tableCheck = await client.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'users'
      );
    `);

    if (!tableCheck.rows[0].exists) {
      console.log('Old "users" table does not exist. Skipping migration.');
      return;
    }

    // Get all users from old table
    const result = await client.query('SELECT * FROM users ORDER BY created_at');
    const oldUsers = result.rows;

    console.log(`Found ${oldUsers.length} users to migrate\n`);

    let migratedCount = 0;
    let skippedCount = 0;

    for (const oldUser of oldUsers) {
      try {
        // Check if already migrated
        const existsCheck = await client.query(
          'SELECT user_id FROM user_profiles WHERE user_id = $1',
          [oldUser.id]
        );

        if (existsCheck.rows.length > 0) {
          console.log(`Skipping ${oldUser.email} (already migrated)`);
          skippedCount++;
          continue;
        }

        // Create new profile
        await client.query(`
          INSERT INTO user_profiles (
            user_id, email, full_name, role, is_active,
            primary_language, secondary_languages,
            default_party, budget_level,
            preference_overrides, onboarding, events,
            profile_version, created_at, updated_at, last_login_at
          ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7,
            $8, $9,
            $10, $11, $12,
            $13, $14, $15, $16
          )
        `, [
          oldUser.id,
          oldUser.email,
          `${oldUser.first_name} ${oldUser.last_name}`,
          oldUser.role || 'user',
          oldUser.is_active !== false,
          'en',
          ['si'],
          'unknown',
          'unknown',
          JSON.stringify({
            travelStyle: [],
            activityPreference: 'unknown',
            pacePreference: 'unknown',
            adventureLevel: 'unknown',
            preferredTransport: [],
            foodPreferences: [],
            mustHaveAmenities: [],
            accommodationType: 'any',
            starPreference: 'any',
            cancellationPreference: 'any'
          }),
          JSON.stringify({
            completed: false,
            questionnaireVersion: 1,
            answers: {}
          }),
          JSON.stringify([]),
          1,
          oldUser.created_at,
          oldUser.updated_at,
          oldUser.last_login_at
        ]);

        console.log(`✓ Migrated ${oldUser.email}`);
        migratedCount++;

      } catch (error) {
        console.error(`✗ Failed to migrate ${oldUser.email}:`, error.message);
      }
    }

    console.log(`\n========================================`);
    console.log(`Migration Complete!`);
    console.log(`Migrated: ${migratedCount}`);
    console.log(`Skipped: ${skippedCount}`);
    console.log(`Total: ${oldUsers.length}`);
    console.log(`========================================\n`);

    // Optionally rename old table as backup
    // await client.query('ALTER TABLE users RENAME TO users_backup');
    // console.log('Old table renamed to users_backup');

  } catch (error) {
    console.error('Migration failed:', error);
    throw error;
  } finally {
    client.release();
    await pool.end();
  }
}

migrateUsers().catch(console.error);
