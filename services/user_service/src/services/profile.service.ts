import { ProfileRepository } from '../repositories/profile.repository';
import {
  UserProfile,
  ProfilePatch,
  CreateProfileDto,
  ProfileEvent,
  AccommodationPreferencesResponse,
  TravelStylePreferencesResponse,
  PartyType
} from '../types/profile.types';
import { NotFoundError, ConflictError } from '../utils/errors';
import logger from '../utils/logger';

export class ProfileService {
  private profileRepository: ProfileRepository;

  constructor() {
    this.profileRepository = new ProfileRepository();
  }

  /**
   * Upsert complete profile (usually after onboarding)
   */
  async upsertProfile(data: UserProfile): Promise<UserProfile> {
    try {
      const existing = await this.profileRepository.findByUserId(data.identity.userId);
      
      if (existing) {
        // Increment version for updates
        data.profileVersion = existing.profileVersion + 1;
      }
      
      data.updatedAtIso = new Date().toISOString();
      
      const profile = await this.profileRepository.upsert(data);
      
      logger.info(`Profile upserted for user: ${data.identity.userId}`);
      
      return profile;
    } catch (error) {
      logger.error('Error upserting profile', { userId: data.identity.userId, error });
      throw error;
    }
  }

  /**
   * Get profile by user ID
   */
  async getProfile(userId: string): Promise<UserProfile> {
    const profile = await this.profileRepository.findByUserId(userId);
    
    if (!profile) {
      throw new NotFoundError('Profile');
    }
    
    return profile;
  }

  /**
   * Get profile by email
   */
  async getProfileByEmail(email: string): Promise<UserProfile> {
    const profile = await this.profileRepository.findByEmail(email);
    
    if (!profile) {
      throw new NotFoundError('Profile');
    }
    
    return profile;
  }

  /**
   * Patch profile (incremental updates from chat/settings)
   */
  async patchProfile(userId: string, patch: ProfilePatch): Promise<UserProfile> {
    const profile = await this.profileRepository.findByUserId(userId);
    
    if (!profile) {
      throw new NotFoundError('Profile');
    }

    // Merge nested objects intelligently
    if (patch.preferenceOverrides) {
      profile.preferenceOverrides = {
        ...profile.preferenceOverrides,
        ...patch.preferenceOverrides
      };
    }

    if (patch.onboarding) {
      profile.onboarding = {
        ...profile.onboarding,
        ...patch.onboarding
      };
    }

    // Direct field updates
    if (patch.username !== undefined) {
      profile.identity.username = patch.username;
    }
    
    if (patch.fullName !== undefined) {
      profile.identity.fullName = patch.fullName;
    }
    
    if (patch.country !== undefined) {
      profile.demographics.country = patch.country;
    }
    
    if (patch.dateOfBirth !== undefined) {
      profile.demographics.dateOfBirth = patch.dateOfBirth;
    }
    
    if (patch.primaryLanguage !== undefined) {
      profile.languages.primaryLanguage = patch.primaryLanguage;
    }
    
    if (patch.secondaryLanguages !== undefined) {
      profile.languages.secondaryLanguages = patch.secondaryLanguages;
    }
    
    if (patch.homeCity !== undefined) {
      profile.homeCity = patch.homeCity;
    }
    
    if (patch.defaultParty !== undefined) {
      profile.defaultParty = patch.defaultParty;
    }
    
    if (patch.budgetLevel !== undefined) {
      profile.budgetLevel = patch.budgetLevel;
    }
    
    // Increment version and update timestamp
    profile.profileVersion++;
    profile.updatedAtIso = new Date().toISOString();

    const updatedProfile = await this.profileRepository.update(userId, profile);
    
    logger.info(`Profile patched for user: ${userId}`, { source: patch.source });
    
    return updatedProfile;
  }

  /**
   * Complete onboarding (derive preferences from questionnaire)
   */
  async completeOnboarding(userId: string, answers: Record<string, any>): Promise<UserProfile> {
    const preferences = this.derivePreferencesFromAnswers(answers);
    
    const patch: ProfilePatch = {
      source: 'onboarding',
      onboarding: {
        completed: true,
        answers: answers,
        completedAtIso: new Date().toISOString()
      },
      preferenceOverrides: preferences
    };

    return await this.patchProfile(userId, patch);
  }

  /**
   * Derive structured preferences from onboarding answers
   */
  private derivePreferencesFromAnswers(answers: Record<string, any>): Partial<UserProfile['preferenceOverrides']> {
    const preferences: any = {};

    // Travel style
    if (answers.preferred_activities && Array.isArray(answers.preferred_activities)) {
      preferences.travelStyle = answers.preferred_activities;
    }

    // Activity preference
    if (answers.likes_nature) {
      preferences.activityPreference = 'outdoor';
    } else if (answers.likes_museums || answers.likes_shopping) {
      preferences.activityPreference = 'indoor';
    }

    // Adventure level
    if (answers.adventure_seeker) {
      preferences.adventureLevel = 'high';
    } else if (answers.prefers_relaxation) {
      preferences.adventureLevel = 'low';
    } else {
      preferences.adventureLevel = 'medium';
    }

    // Pace
    if (answers.pace === 'relaxed' || answers.prefers_relaxation) {
      preferences.pacePreference = 'relaxed';
    } else if (answers.pace === 'packed') {
      preferences.pacePreference = 'packed';
    } else {
      preferences.pacePreference = 'balanced';
    }

    // Accommodation
    if (answers.accommodation_type) {
      preferences.accommodationType = answers.accommodation_type;
    }

    if (answers.star_rating) {
      preferences.starPreference = answers.star_rating;
    }

    // Budget
    if (answers.max_budget_per_night) {
      preferences.budgetPerNightLkr = parseInt(answers.max_budget_per_night);
      preferences.budgetLevel = this.deriveBudgetLevel(preferences.budgetPerNightLkr);
    }

    if (answers.budget_flexibility !== undefined) {
      preferences.budgetFlexibility = parseFloat(answers.budget_flexibility);
    }

    // Food & dietary
    if (answers.dietary_restrictions && Array.isArray(answers.dietary_restrictions)) {
      preferences.foodPreferences = answers.dietary_restrictions;
    }

    // Family-specific amenities
    if (answers.travels_with_kids) {
      preferences.mustHaveAmenities = ['wifi', 'ac', 'family_rooms', 'breakfast'];
    } else if (answers.business_traveler) {
      preferences.mustHaveAmenities = ['wifi', 'gym'];
    } else {
      preferences.mustHaveAmenities = ['wifi', 'ac'];
    }

    // Transport
    if (answers.preferred_transport && Array.isArray(answers.preferred_transport)) {
      preferences.preferredTransport = answers.preferred_transport;
    }

    // Weather
    if (answers.sun_sensitive) {
      preferences.sunSensitivity = 'high';
    }

    if (answers.rain_tolerance) {
      preferences.rainPreference = answers.rain_tolerance;
    }

    // Crowds
    if (answers.avoid_crowds) {
      preferences.avoidCrowds = true;
    }

    // Eco
    if (answers.eco_conscious) {
      preferences.ecoPreference = 0.8;
    }

    return preferences;
  }

  /**
   * Derive budget level from numeric value
   */
  private deriveBudgetLevel(budgetPerNight: number): 'low' | 'mid' | 'high' {
    if (budgetPerNight < 10000) return 'low';
    if (budgetPerNight < 25000) return 'mid';
    return 'high';
  }

  /**
   * Log user event (saved POI, completed trip, feedback)
   */
  async logEvent(userId: string, event: Omit<ProfileEvent, 'tsIso'>): Promise<void> {
    const profile = await this.profileRepository.findByUserId(userId);
    
    if (!profile) {
      throw new NotFoundError('Profile');
    }
    
    const fullEvent: ProfileEvent = {
      ...event,
      tsIso: new Date().toISOString()
    };
    
    profile.events.push(fullEvent);
    
    // Keep only last 100 events
    if (profile.events.length > 100) {
      profile.events = profile.events.slice(-100);
    }

    await this.profileRepository.update(userId, profile);
    
    logger.info(`Event logged for user: ${userId}`, { eventType: event.eventType });
  }

  /**
   * Get accommodation preferences (for HotelAgent)
   */
  async getAccommodationPreferences(userId: string): Promise<AccommodationPreferencesResponse> {
    const profile = await this.profileRepository.findByUserId(userId);
    
    if (!profile) {
      throw new NotFoundError('Profile');
    }
    
    return {
      accommodationType: profile.preferenceOverrides.accommodationType,
      starPreference: profile.preferenceOverrides.starPreference,
      mustHaveAmenities: profile.preferenceOverrides.mustHaveAmenities,
      cancellationPreference: profile.preferenceOverrides.cancellationPreference,
      budgetPerNightLkr: profile.preferenceOverrides.budgetPerNightLkr,
      budgetFlexibility: profile.preferenceOverrides.budgetFlexibility,
      partySize: this.estimatePartySize(profile.defaultParty)
    };
  }

  /**
   * Get travel style preferences (for Recommender/Itinerary)
   */
  async getTravelStylePreferences(userId: string): Promise<TravelStylePreferencesResponse> {
    const profile = await this.profileRepository.findByUserId(userId);
    
    if (!profile) {
      throw new NotFoundError('Profile');
    }
    
    return {
      travelStyle: profile.preferenceOverrides.travelStyle,
      activityPreference: profile.preferenceOverrides.activityPreference,
      pacePreference: profile.preferenceOverrides.pacePreference,
      adventureLevel: profile.preferenceOverrides.adventureLevel,
      avoidCrowds: profile.preferenceOverrides.avoidCrowds,
      ecoPreference: profile.preferenceOverrides.ecoPreference
    };
  }

  /**
   * Estimate party size from party type
   */
  private estimatePartySize(partyType: PartyType): number {
    const sizeMap: Record<PartyType, number> = {
      solo: 1,
      couple: 2,
      family: 4,
      friends: 3,
      unknown: 2
    };
    return sizeMap[partyType];
  }

  /**
   * Create minimal profile (for auth service sync)
   */
  async createMinimalProfile(dto: CreateProfileDto): Promise<UserProfile> {
    // Check if already exists
    const existing = await this.profileRepository.findByEmail(dto.email);
    
    if (existing) {
      throw new ConflictError('Profile already exists');
    }

    const profile = await this.profileRepository.createMinimal(dto);
    
    logger.info(`Minimal profile created for user: ${dto.userId}`);
    
    return profile;
  }

  /**
   * Get all profiles (admin)
   */
  async getAllProfiles(page: number, limit: number): Promise<{ profiles: UserProfile[]; total: number }> {
    const [profiles, total] = await this.profileRepository.findAll(page, limit);
    
    return { profiles, total };
  }

  /**
   * Delete profile
   */
  async deleteProfile(userId: string): Promise<void> {
    const profile = await this.profileRepository.findByUserId(userId);
    
    if (!profile) {
      throw new NotFoundError('Profile');
    }

    await this.profileRepository.delete(userId);
    
    logger.info(`Profile deleted for user: ${userId}`);
  }
}
