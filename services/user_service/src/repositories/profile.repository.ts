import { Pool } from 'pg';
import { UserProfile, CreateProfileDto } from '../types/profile.types';
import logger from '../utils/logger';

// Create a direct PostgreSQL pool for JSONB operations
const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432'),
  user: process.env.DB_USERNAME || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  database: process.env.DB_DATABASE || 'graphceylon_users',
});

export class ProfileRepository {
  /**
   * Find profile by user ID
   */
  async findByUserId(userId: string): Promise<UserProfile | null> {
    try {
      const result = await pool.query(
        `SELECT 
          user_id, email, username, full_name,
          country, date_of_birth,
          primary_language, secondary_languages,
          home_city, default_party, budget_level,
          preference_overrides, onboarding, events,
          role, is_active,
          profile_version,
          created_at, updated_at, last_login_at
        FROM user_profiles 
        WHERE user_id = $1`,
        [userId]
      );

      if (result.rows.length === 0) {
        return null;
      }

      return this.mapRowToProfile(result.rows[0]);
    } catch (error) {
      logger.error('Error finding profile by userId', { userId, error });
      throw error;
    }
  }

  /**
   * Find profile by email
   */
  async findByEmail(email: string): Promise<UserProfile | null> {
    try {
      const result = await pool.query(
        `SELECT 
          user_id, email, username, full_name,
          country, date_of_birth,
          primary_language, secondary_languages,
          home_city, default_party, budget_level,
          preference_overrides, onboarding, events,
          role, is_active,
          profile_version,
          created_at, updated_at, last_login_at
        FROM user_profiles 
        WHERE email = $1`,
        [email]
      );

      if (result.rows.length === 0) {
        return null;
      }

      return this.mapRowToProfile(result.rows[0]);
    } catch (error) {
      logger.error('Error finding profile by email', { email, error });
      throw error;
    }
  }

  /**
   * Create or update profile (upsert)
   */
  async upsert(profile: UserProfile): Promise<UserProfile> {
    try {
      const result = await pool.query(
        `INSERT INTO user_profiles (
          user_id, email, username, full_name,
          country, date_of_birth,
          primary_language, secondary_languages,
          home_city, default_party, budget_level,
          preference_overrides, onboarding, events,
          role, is_active,
          profile_version,
          created_at, updated_at, last_login_at
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
        )
        ON CONFLICT (user_id) DO UPDATE SET
          username = EXCLUDED.username,
          full_name = EXCLUDED.full_name,
          country = EXCLUDED.country,
          date_of_birth = EXCLUDED.date_of_birth,
          primary_language = EXCLUDED.primary_language,
          secondary_languages = EXCLUDED.secondary_languages,
          home_city = EXCLUDED.home_city,
          default_party = EXCLUDED.default_party,
          budget_level = EXCLUDED.budget_level,
          preference_overrides = EXCLUDED.preference_overrides,
          onboarding = EXCLUDED.onboarding,
          events = EXCLUDED.events,
          role = EXCLUDED.role,
          is_active = EXCLUDED.is_active,
          profile_version = EXCLUDED.profile_version,
          updated_at = NOW(),
          last_login_at = EXCLUDED.last_login_at
        RETURNING *`,
        [
          profile.identity.userId,
          profile.identity.email,
          profile.identity.username || null,
          profile.identity.fullName || null,
          profile.demographics.country || null,
          profile.demographics.dateOfBirth || null,
          profile.languages.primaryLanguage,
          profile.languages.secondaryLanguages,
          profile.homeCity || null,
          profile.defaultParty,
          profile.budgetLevel,
          JSON.stringify(profile.preferenceOverrides),
          JSON.stringify(profile.onboarding),
          JSON.stringify(profile.events),
          profile.role,
          profile.isActive,
          profile.profileVersion,
          profile.createdAt,
          new Date(),
          profile.lastLoginAt || null
        ]
      );

      return this.mapRowToProfile(result.rows[0]);
    } catch (error) {
      logger.error('Error upserting profile', { userId: profile.identity.userId, error });
      throw error;
    }
  }

  /**
   * Update profile (for patching)
   */
  async update(userId: string, profile: UserProfile): Promise<UserProfile> {
    try {
      const result = await pool.query(
        `UPDATE user_profiles SET
          username = $2,
          full_name = $3,
          country = $4,
          date_of_birth = $5,
          primary_language = $6,
          secondary_languages = $7,
          home_city = $8,
          default_party = $9,
          budget_level = $10,
          preference_overrides = $11,
          onboarding = $12,
          events = $13,
          profile_version = $14,
          updated_at = NOW()
        WHERE user_id = $1
        RETURNING *`,
        [
          userId,
          profile.identity.username || null,
          profile.identity.fullName || null,
          profile.demographics.country || null,
          profile.demographics.dateOfBirth || null,
          profile.languages.primaryLanguage,
          profile.languages.secondaryLanguages,
          profile.homeCity || null,
          profile.defaultParty,
          profile.budgetLevel,
          JSON.stringify(profile.preferenceOverrides),
          JSON.stringify(profile.onboarding),
          JSON.stringify(profile.events),
          profile.profileVersion
        ]
      );

      if (result.rows.length === 0) {
        throw new Error('Profile not found for update');
      }

      return this.mapRowToProfile(result.rows[0]);
    } catch (error) {
      logger.error('Error updating profile', { userId, error });
      throw error;
    }
  }

  /**
   * Create minimal profile (for auth service sync)
   */
  async createMinimal(dto: CreateProfileDto): Promise<UserProfile> {
    try {
      const result = await pool.query(
        `INSERT INTO user_profiles (
          user_id, email, full_name, role,
          primary_language, secondary_languages,
          default_party, budget_level,
          preference_overrides, onboarding, events,
          profile_version, is_active
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
        )
        RETURNING *`,
        [
          dto.userId,
          dto.email,
          dto.fullName || null,
          dto.role || 'user',
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
          true
        ]
      );

      return this.mapRowToProfile(result.rows[0]);
    } catch (error) {
      logger.error('Error creating minimal profile', { dto, error });
      throw error;
    }
  }

  /**
   * Delete profile
   */
  async delete(userId: string): Promise<void> {
    try {
      await pool.query('DELETE FROM user_profiles WHERE user_id = $1', [userId]);
    } catch (error) {
      logger.error('Error deleting profile', { userId, error });
      throw error;
    }
  }

  /**
   * Get all profiles (paginated)
   */
  async findAll(page: number, limit: number): Promise<[UserProfile[], number]> {
    try {
      const offset = (page - 1) * limit;

      const [dataResult, countResult] = await Promise.all([
        pool.query(
          `SELECT * FROM user_profiles 
           ORDER BY created_at DESC 
           LIMIT $1 OFFSET $2`,
          [limit, offset]
        ),
        pool.query('SELECT COUNT(*) FROM user_profiles')
      ]);

      const profiles = dataResult.rows.map((row: any) => this.mapRowToProfile(row));
      const total = parseInt(countResult.rows[0].count);

      return [profiles, total];
    } catch (error) {
      logger.error('Error finding all profiles', { page, limit, error });
      throw error;
    }
  }

  /**
   * Map database row to UserProfile
   */
  private mapRowToProfile(row: any): UserProfile {
    return {
      identity: {
        userId: row.user_id,
        email: row.email,
        username: row.username,
        fullName: row.full_name
      },
      demographics: {
        country: row.country,
        dateOfBirth: row.date_of_birth
      },
      languages: {
        primaryLanguage: row.primary_language,
        secondaryLanguages: row.secondary_languages || []
      },
      homeCity: row.home_city,
      defaultParty: row.default_party,
      budgetLevel: row.budget_level,
      preferenceOverrides: row.preference_overrides,
      onboarding: row.onboarding,
      events: row.events || [],
      role: row.role,
      isActive: row.is_active,
      profileVersion: row.profile_version,
      updatedAtIso: row.updated_at?.toISOString(),
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      lastLoginAt: row.last_login_at
    };
  }
}
