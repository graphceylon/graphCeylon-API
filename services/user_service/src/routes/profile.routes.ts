import { Router } from 'express';
import { ProfileController } from '../controllers/profile.controller';
import { authenticate, authorize } from '../middlewares/auth.middleware';
import { UserRole } from '../types';

const router = Router();
const profileController = new ProfileController();

// Upsert complete profile
router.post(
  '/profile/upsert',
  authenticate,
  profileController.upsertProfile.bind(profileController)
);

// Create minimal profile (internal - auth service sync)
router.post(
  '/profile/create-minimal',
  profileController.createMinimalProfile.bind(profileController)
);

// Get all profiles (admin only)
router.get(
  '/profiles',
  authenticate,
  authorize(UserRole.ADMIN),
  profileController.getAllProfiles.bind(profileController)
);

// Get current user's profile (must come before /:userId)
router.get(
  '/profile/me',
  authenticate,
  profileController.getCurrentUserProfile.bind(profileController)
);

// Get accommodation preferences
router.get(
  '/profile/:userId/preferences/accommodation',
  authenticate,
  profileController.getAccommodationPreferences.bind(profileController)
);

// Get travel style preferences
router.get(
  '/profile/:userId/preferences/travel-style',
  authenticate,
  profileController.getTravelStylePreferences.bind(profileController)
);

// Get profile by user ID
router.get(
  '/profile/:userId',
  authenticate,
  profileController.getProfile.bind(profileController)
);

// Patch profile (incremental updates)
router.patch(
  '/profile/:userId',
  authenticate,
  profileController.patchProfile.bind(profileController)
);

// Delete profile (Admin only)
router.delete(
  '/profile/:userId',
  authenticate,
  authorize(UserRole.ADMIN),
  profileController.deleteProfile.bind(profileController)
);

// Complete onboarding questionnaire
router.post(
  '/profile/:userId/onboarding',
  authenticate,
  profileController.completeOnboarding.bind(profileController)
);

// Log user event
router.post(
  '/profile/:userId/events',
  authenticate,
  profileController.logEvent.bind(profileController)
);

export default router;
