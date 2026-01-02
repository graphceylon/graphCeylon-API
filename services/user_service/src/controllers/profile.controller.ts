import { Request, Response, NextFunction } from 'express';
import { ProfileService } from '../services/profile.service';
import { ApiResponse } from '../types';
import { UserProfile, ProfilePatch, CreateProfileDto, ProfileEvent } from '../types/profile.types';

const profileService = new ProfileService();

export class ProfileController {
  /**
   * Upsert complete profile
   * POST /api/users/profile/upsert
   */
  async upsertProfile(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const profileData: UserProfile = req.body;
      const profile = await profileService.upsertProfile(profileData);

      const response: ApiResponse = {
        success: true,
        message: 'Profile saved successfully',
        data: profile,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get profile by user ID
   * GET /api/users/profile/:userId
   */
  async getProfile(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { userId } = req.params;
      const profile = await profileService.getProfile(userId);

      const response: ApiResponse = {
        success: true,
        message: 'Profile retrieved successfully',
        data: profile,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get current user's profile
   * GET /api/users/profile/me
   */
  async getCurrentUserProfile(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const userEmail = req.user?.email;
      
      if (!userEmail) {
        res.status(401).json({
          success: false,
          message: 'User not authenticated',
          timestamp: new Date().toISOString(),
          requestId: req.requestId,
        });
        return;
      }

      const profile = await profileService.getProfileByEmail(userEmail);

      const response: ApiResponse = {
        success: true,
        message: 'Profile retrieved successfully',
        data: profile,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Patch profile (incremental updates)
   * PATCH /api/users/profile/:userId
   */
  async patchProfile(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { userId } = req.params;
      const patchData: ProfilePatch = req.body;
      
      const profile = await profileService.patchProfile(userId, patchData);

      const response: ApiResponse = {
        success: true,
        message: 'Profile updated successfully',
        data: profile,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Complete onboarding
   * POST /api/users/profile/:userId/onboarding
   */
  async completeOnboarding(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { userId } = req.params;
      const { answers } = req.body;

      const profile = await profileService.completeOnboarding(userId, answers);

      const response: ApiResponse = {
        success: true,
        message: 'Onboarding completed successfully',
        data: profile,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Log event
   * POST /api/users/profile/:userId/events
   */
  async logEvent(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { userId } = req.params;
      const eventData: Omit<ProfileEvent, 'tsIso'> = req.body;

      await profileService.logEvent(userId, eventData);

      const response: ApiResponse = {
        success: true,
        message: 'Event logged successfully',
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get accommodation preferences
   * GET /api/users/profile/:userId/preferences/accommodation
   */
  async getAccommodationPreferences(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { userId } = req.params;
      const preferences = await profileService.getAccommodationPreferences(userId);

      const response: ApiResponse = {
        success: true,
        message: 'Accommodation preferences retrieved',
        data: preferences,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get travel style preferences
   * GET /api/users/profile/:userId/preferences/travel-style
   */
  async getTravelStylePreferences(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { userId } = req.params;
      const preferences = await profileService.getTravelStylePreferences(userId);

      const response: ApiResponse = {
        success: true,
        message: 'Travel style preferences retrieved',
        data: preferences,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Create minimal profile (internal - for auth service)
   * POST /api/users/profile/create-minimal
   */
  async createMinimalProfile(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const dto: CreateProfileDto = req.body;
      const profile = await profileService.createMinimalProfile(dto);

      const response: ApiResponse = {
        success: true,
        message: 'Minimal profile created',
        data: profile,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(201).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get all profiles (admin)
   * GET /api/users/profiles
   */
  async getAllProfiles(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;

      const result = await profileService.getAllProfiles(page, limit);

      const response: ApiResponse = {
        success: true,
        message: 'Profiles retrieved successfully',
        data: result,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Delete profile
   * DELETE /api/users/profile/:userId
   */
  async deleteProfile(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { userId } = req.params;
      await profileService.deleteProfile(userId);

      const response: ApiResponse = {
        success: true,
        message: 'Profile deleted successfully',
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }
}
