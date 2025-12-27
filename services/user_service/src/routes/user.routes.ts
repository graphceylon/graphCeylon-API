import { Router } from 'express';
import { UserController } from '../controllers/user.controller';
import { authenticate, authorize } from '../middlewares/auth.middleware';
import {
  validate,
  createUserSchema,
  updateUserSchema,
  userIdSchema,
} from '../middlewares/validation.middleware';
import { UserRole } from '../types';

const router = Router();
const userController = new UserController();

// Get current user's profile
router.get(
  '/me',
  authenticate,
  userController.getCurrentUser.bind(userController)
);

// Get all users (paginated)
router.get(
  '/',
  authenticate,
  authorize(UserRole.ADMIN, UserRole.MODERATOR),
  userController.getAllUsers.bind(userController)
);

// Search users
router.get(
  '/search',
  authenticate,
  authorize(UserRole.ADMIN, UserRole.MODERATOR),
  userController.searchUsers.bind(userController)
);

// Get user statistics
router.get(
  '/statistics',
  authenticate,
  authorize(UserRole.ADMIN),
  userController.getUserStatistics.bind(userController)
);

// Get users by role
router.get(
  '/role/:role',
  authenticate,
  authorize(UserRole.ADMIN, UserRole.MODERATOR),
  userController.getUsersByRole.bind(userController)
);

// Get user by ID
router.get(
  '/:id',
  authenticate,
  validate(userIdSchema),
  userController.getUserById.bind(userController)
);

// Create new user (Admin only)
router.post(
  '/',
  authenticate,
  authorize(UserRole.ADMIN),
  validate(createUserSchema),
  userController.createUser.bind(userController)
);

// Update user (Admin only)
router.put(
  '/:id',
  authenticate,
  authorize(UserRole.ADMIN),
  validate(updateUserSchema),
  userController.updateUser.bind(userController)
);

// Delete user (Admin only)
router.delete(
  '/:id',
  authenticate,
  authorize(UserRole.ADMIN),
  validate(userIdSchema),
  userController.deleteUser.bind(userController)
);

export default router;
