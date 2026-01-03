import { Router } from 'express';
import { AuthController } from '../controllers/auth.controller';
import { authenticate } from '../middlewares/auth.middleware';
import {
  validate,
  registerSchema,
  loginSchema,
  refreshTokenSchema,
  verifyEmailSchema,
  forgotPasswordSchema,
  resetPasswordSchema,
} from '../middlewares/validation.middleware';
import {
  authLimiter,
  passwordResetLimiter,
} from '../middlewares/rateLimit.middleware';

const router = Router();
const authController = new AuthController();

/**
 * @route   POST /api/auth/register
 * @desc    Register a new user
 * @access  Public
 */
router.post(
  '/register',
  authLimiter,
  validate(registerSchema),
  authController.register.bind(authController)
);

/**
 * @route   POST /api/auth/login
 * @desc    Login user
 * @access  Public
 */
router.post(
  '/login',
  authLimiter,
  validate(loginSchema),
  authController.login.bind(authController)
);

/**
 * @route   POST /api/auth/logout
 * @desc    Logout user
 * @access  Private
 */
router.post('/logout', authenticate, authController.logout.bind(authController));

/**
 * @route   POST /api/auth/refresh
 * @desc    Refresh access token
 * @access  Public
 */
router.post(
  '/refresh',
  validate(refreshTokenSchema),
  authController.refreshToken.bind(authController)
);

/**
 * @route   POST /api/auth/verify-email
 * @desc    Verify email address
 * @access  Public
 */
router.post(
  '/verify-email',
  validate(verifyEmailSchema),
  authController.verifyEmail.bind(authController)
);

/**
 * @route   POST /api/auth/resend-verification
 * @desc    Resend verification email
 * @access  Private
 */
router.post(
  '/resend-verification',
  authenticate,
  authLimiter,
  authController.resendVerificationEmail.bind(authController)
);

// Request password reset
router.post(
  '/forgot-password',
  passwordResetLimiter,
  validate(forgotPasswordSchema),
  authController.forgotPassword.bind(authController)
);

// Reset password with token
router.post(
  '/reset-password',
  validate(resetPasswordSchema),
  authController.resetPassword.bind(authController)
);

// Get current user
router.get('/me', authenticate, authController.getCurrentUser.bind(authController));

export default router;
