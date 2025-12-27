/**
 * Tourism Profile Types
 * Comprehensive user profile for personalized recommendations
 */

// Enum types
export type PartyType = 'solo' | 'couple' | 'family' | 'friends' | 'unknown';
export type BudgetLevel = 'low' | 'mid' | 'high' | 'unknown';
export type ActivityPreference = 'outdoor' | 'indoor' | 'mixed' | 'unknown';
export type PacePreference = 'relaxed' | 'balanced' | 'packed' | 'unknown';
export type AdventureLevel = 'low' | 'medium' | 'high' | 'unknown';

export type AccommodationType = 
  | 'hotel' | 'resort' | 'villa' | 'guesthouse' 
  | 'hostel' | 'eco_lodge' | 'homestay' | 'any';

export type Amenity = 
  | 'wifi' | 'ac' | 'pool' | 'breakfast' 
  | 'parking' | 'gym' | 'spa' | 'family_rooms';

export type StarPreference = 'any' | '3_star_plus' | '4_star_plus' | '5_star_only';
export type CancellationPreference = 'flexible' | 'strict' | 'any';
export type RainPreference = 'avoid_rain' | 'ok_with_rain' | 'prefer_rain' | 'unknown';
export type TempPreference = 'cool' | 'moderate' | 'warm' | 'unknown';
export type SensitivityLevel = 'low' | 'medium' | 'high' | 'unknown';

// Identity
export interface UserIdentity {
  userId: string;
  username?: string;
  fullName?: string;
  email: string;
}

// Demographics
export interface UserDemographics {
  country?: string;
  dateOfBirth?: string; // ISO date YYYY-MM-DD
}

// Languages
export interface UserLanguages {
  primaryLanguage: string;
  secondaryLanguages: string[];
}

// Preference Overrides (Core Intelligence Driver)
export interface PreferenceOverrides {
  // Trip style / scoring
  travelStyle: string[]; // ['nature', 'culture', 'adventure']
  avoidCrowds?: boolean;
  ecoPreference?: number; // 0.0 - 1.0
  
  activityPreference: ActivityPreference;
  pacePreference: PacePreference;
  adventureLevel: AdventureLevel;
  
  // Budget (coarse + actionable numeric)
  budgetLevel?: BudgetLevel;
  budgetPerNightLkr?: number; // Hotel budget per night (LKR)
  budgetFlexibility?: number; // 0=strict, 1=flexible
  
  // Transport / food / accessibility
  preferredTransport: string[]; // ['train', 'car', 'bus']
  foodPreferences: string[]; // ['halal', 'veg', 'vegan']
  accessibilityNeeds?: string[]; // ['wheelchair']
  walkingToleranceMinutes?: number; // 0-600
  
  // Accommodation preferences (HotelAgent-critical)
  accommodationType: AccommodationType;
  starPreference: StarPreference;
  mustHaveAmenities: Amenity[];
  cancellationPreference: CancellationPreference;
  
  // Weather tolerance
  sunSensitivity?: SensitivityLevel;
  rainPreference?: RainPreference;
  temperaturePreference?: TempPreference;
  
  // Optional constraints
  motionSickness?: boolean;
}

// Onboarding Questionnaire
export interface OnboardingQuestionnaire {
  questionnaireVersion: number;
  completed: boolean;
  answers: Record<string, any>; // Flexible for changing questions
  completedAtIso?: string;
}

// Profile Event
export interface ProfileEvent {
  eventType: 'saved_poi' | 'disliked_poi' | 'completed_trip' | 'feedback';
  payload: Record<string, any>;
  tsIso: string;
}

// Complete User Profile
export interface UserProfile {
  // Identity
  identity: UserIdentity;
  demographics: UserDemographics;
  languages: UserLanguages;
  
  // Travel defaults
  homeCity?: string;
  defaultParty: PartyType;
  budgetLevel: BudgetLevel;
  
  // Preferences & onboarding
  onboarding: OnboardingQuestionnaire;
  preferenceOverrides: PreferenceOverrides;
  
  // Activity log
  events: ProfileEvent[];
  
  // RBAC
  role: string;
  isActive: boolean;
  
  // Metadata
  profileVersion: number;
  updatedAtIso: string;
  createdAt: Date;
  updatedAt: Date;
  lastLoginAt?: Date;
}

// Profile Patch (for incremental updates)
export interface ProfilePatch {
  source?: 'user_text' | 'onboarding' | 'explicit_settings' | 'system';
  
  // Identity updates
  username?: string;
  fullName?: string;
  
  // Demographics
  country?: string;
  dateOfBirth?: string;
  
  // Languages
  primaryLanguage?: string;
  secondaryLanguages?: string[];
  
  // Travel defaults
  homeCity?: string;
  defaultParty?: PartyType;
  budgetLevel?: BudgetLevel;
  
  // Nested updates (partial)
  preferenceOverrides?: Partial<PreferenceOverrides>;
  onboarding?: Partial<OnboardingQuestionnaire>;
}

// DTO for creating profile
export interface CreateProfileDto {
  userId: string;
  email: string;
  fullName?: string;
  role?: string;
}

// Response types
export interface ProfileResponse extends UserProfile {}

export interface AccommodationPreferencesResponse {
  accommodationType: AccommodationType;
  starPreference: StarPreference;
  mustHaveAmenities: Amenity[];
  cancellationPreference: CancellationPreference;
  budgetPerNightLkr?: number;
  budgetFlexibility?: number;
  partySize: number;
}

export interface TravelStylePreferencesResponse {
  travelStyle: string[];
  activityPreference: ActivityPreference;
  pacePreference: PacePreference;
  adventureLevel: AdventureLevel;
  avoidCrowds?: boolean;
  ecoPreference?: number;
}
