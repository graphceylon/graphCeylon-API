import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import {
  User,
  UserRole,
  RegisterRequest,
  LoginRequest,
  AuthResponse,
  UserResponse,
} from '../types/auth.types';
import { PasswordUtil } from '../utils/password.util';
import { TokenService } from '../utils/token.util';
import { AppError, ConflictError, AuthenticationError } from '../utils/errors';
import { sanitizeEmail } from '../utils/helpers';
import emailService from '../utils/email.util';
import redisClient from '../config/redis';
import config from '../config';
import logger from '../utils/logger';

// In-memory store (replace with database in production)
const users: Map<string, User> = new Map();

export class AuthService {
  /**
   * Register new user
   */
  async register(data: RegisterRequest): Promise<AuthResponse> {
    const email = sanitizeEmail(data.email);

    // Check if user already exists
    const existingUser = Array.from(users.values()).find((u) => u.email === email);
    if (existingUser) {
      throw new ConflictError('User with this email already exists');
    }

    // Validate password strength
    const passwordValidation = PasswordUtil.validateStrength(data.password);
    if (!passwordValidation.isValid) {
      throw new AppError(passwordValidation.errors.join(', '), 400, 'WEAK_PASSWORD');
    }

    // Hash password
    const hashedPassword = await PasswordUtil.hash(data.password);

    // Create user (allow role override for admin setup, default to USER)
    const user: User = {
      id: uuidv4(),
      email,
      password: hashedPassword,
      firstName: data.firstName,
      lastName: data.lastName,
      isEmailVerified: false,
      isActive: true,
      role: (data as any).role || UserRole.USER, // Allow role to be passed for admin setup
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    users.set(user.id, user);

    // Sync with user service (create profile)
    try {
      await this.syncUserProfile(user);
    } catch (error: any) {
      logger.error('Failed to sync user profile with user service', { userId: user.id, error: error.message });
      // Don't fail registration if user service is down
    }

    // Generate email verification token
    const verificationToken = TokenService.generateEmailVerificationToken();
    await TokenService.storeEmailVerificationToken(user.id, verificationToken);

    // Log verification URL for development
    const verificationUrl = `${config.frontendUrl}/verify-email?token=${verificationToken}`;
    console.log('\n' + '='.repeat(80));
    console.log('📧 EMAIL VERIFICATION TOKEN');
    console.log('='.repeat(80));
    console.log(`User: ${user.email}`);
    console.log(`Token: ${verificationToken}`);
    console.log(`Verification URL: ${verificationUrl}`);
    console.log('='.repeat(80) + '\n');

    // Send verification email
    try {
      await emailService.sendVerificationEmail(
        user.email,
        verificationToken,
        `${user.firstName} ${user.lastName}`
      );
      logger.info(`Verification email sent to: ${user.email}`);
    } catch (error: any) {
      logger.warn(`Email sending failed (using console token instead): ${error.message}`);
      // Don't fail registration if email fails
    }

    // Generate tokens
    const tokens = TokenService.generateTokenPair(user.id, user.email, user.role);
    await TokenService.storeRefreshToken(user.id, tokens.refreshToken);

    logger.info(`User registered: ${user.email}`);

    return {
      user: this.toUserResponse(user),
      tokens,
    };
  }

  /**
   * Login user
   */
  async login(data: LoginRequest): Promise<AuthResponse> {
    const email = sanitizeEmail(data.email);

    // Check login attempts
    await this.checkLoginAttempts(email);

    // Find user
    const user = Array.from(users.values()).find((u) => u.email === email);
    if (!user) {
      await this.incrementLoginAttempts(email);
      throw new AuthenticationError('Invalid email or password');
    }

    // Check if user is active
    if (!user.isActive) {
      throw new AuthenticationError('Account is deactivated');
    }

    // Verify password
    const isPasswordValid = await PasswordUtil.compare(data.password, user.password);
    if (!isPasswordValid) {
      await this.incrementLoginAttempts(email);
      throw new AuthenticationError('Invalid email or password');
    }

    // Reset login attempts
    await this.resetLoginAttempts(email);

    // Update last login
    user.lastLoginAt = new Date();
    users.set(user.id, user);

    // Generate tokens
    const tokens = TokenService.generateTokenPair(user.id, user.email, user.role);
    await TokenService.storeRefreshToken(user.id, tokens.refreshToken);

    logger.info(`User logged in: ${user.email}`);

    return {
      user: this.toUserResponse(user),
      tokens,
    };
  }

  /**
   * Logout user
   */
  async logout(userId: string, accessToken: string): Promise<void> {
    await TokenService.revokeRefreshToken(userId);
    await TokenService.blacklistToken(accessToken);
    logger.info(`User logged out: ${userId}`);
  }

  /**
   * Refresh access token
   */
  async refreshToken(refreshToken: string): Promise<AuthResponse> {
    // Verify refresh token
    const decoded = TokenService.verifyRefreshToken(refreshToken);

    // Validate refresh token from Redis
    const isValid = await TokenService.validateRefreshToken(decoded.userId, refreshToken);
    if (!isValid) {
      throw new AuthenticationError('Invalid refresh token');
    }

    // Get user
    const user = users.get(decoded.userId);
    if (!user || !user.isActive) {
      throw new AuthenticationError('User not found or inactive');
    }

    // Generate new tokens
    const tokens = TokenService.generateTokenPair(user.id, user.email, user.role);
    await TokenService.storeRefreshToken(user.id, tokens.refreshToken);

    logger.info(`Token refreshed for user: ${user.email}`);

    return {
      user: this.toUserResponse(user),
      tokens,
    };
  }

  /**
   * Verify email
   */
  async verifyEmail(token: string): Promise<void> {
    const userId = await TokenService.verifyEmailVerificationToken(token);
    if (!userId) {
      throw new AppError('Invalid or expired verification token', 400, 'INVALID_TOKEN');
    }

    const user = users.get(userId);
    if (!user) {
      throw new AppError('User not found', 404, 'USER_NOT_FOUND');
    }

    user.isEmailVerified = true;
    user.updatedAt = new Date();
    users.set(user.id, user);

    // Send welcome email
    try {
      await emailService.sendWelcomeEmail(user.email, `${user.firstName} ${user.lastName}`);
    } catch (error) {
      logger.error('Failed to send welcome email', error);
    }

    logger.info(`Email verified for user: ${user.email}`);
  }

  /**
   * Resend verification email
   */
  async resendVerificationEmail(userId: string): Promise<void> {
    const user = users.get(userId);
    if (!user) {
      throw new AppError('User not found', 404, 'USER_NOT_FOUND');
    }

    if (user.isEmailVerified) {
      throw new AppError('Email is already verified', 400, 'ALREADY_VERIFIED');
    }

    // Generate new verification token
    const verificationToken = TokenService.generateEmailVerificationToken();
    await TokenService.storeEmailVerificationToken(user.id, verificationToken);

    // Log verification URL for development
    const verificationUrl = `${config.frontendUrl}/verify-email?token=${verificationToken}`;
    console.log('\n' + '='.repeat(80));
    console.log('📧 EMAIL VERIFICATION TOKEN (RESEND)');
    console.log('='.repeat(80));
    console.log(`User: ${user.email}`);
    console.log(`Token: ${verificationToken}`);
    console.log(`Verification URL: ${verificationUrl}`);
    console.log('='.repeat(80) + '\n');

    // Send verification email (fail gracefully in development)
    try {
      await emailService.sendVerificationEmail(
        user.email,
        verificationToken,
        `${user.firstName} ${user.lastName}`
      );
      logger.info(`Verification email sent to: ${user.email}`);
    } catch (error: any) {
      logger.warn(`Email sending failed (using console token instead): ${error.message}`);
      // Don't throw - token is logged to console for development
    }

    logger.info(`Verification email resent for user: ${user.email}`);
  }

  /**
   * Request password reset
   */
  async forgotPassword(email: string): Promise<void> {
    const sanitizedEmail = sanitizeEmail(email);
    const user = Array.from(users.values()).find((u) => u.email === sanitizedEmail);

    // Don't reveal if user exists
    if (!user) {
      logger.warn(`Password reset requested for non-existent email: ${sanitizedEmail}`);
      return;
    }

    // Generate reset token
    const resetToken = TokenService.generatePasswordResetToken();
    await TokenService.storePasswordResetToken(user.id, resetToken);

    // Send reset email
    try {
      await emailService.sendPasswordResetEmail(
        user.email,
        resetToken,
        `${user.firstName} ${user.lastName}`
      );
    } catch (error) {
      logger.error('Failed to send password reset email', error);
      throw new AppError('Failed to send password reset email', 500);
    }

    logger.info(`Password reset requested for user: ${user.email}`);
  }

  /**
   * Reset password
   */
  async resetPassword(token: string, newPassword: string): Promise<void> {
    const userId = await TokenService.verifyPasswordResetToken(token);
    if (!userId) {
      throw new AppError('Invalid or expired reset token', 400, 'INVALID_TOKEN');
    }

    const user = users.get(userId);
    if (!user) {
      throw new AppError('User not found', 404, 'USER_NOT_FOUND');
    }

    // Validate password strength
    const passwordValidation = PasswordUtil.validateStrength(newPassword);
    if (!passwordValidation.isValid) {
      throw new AppError(passwordValidation.errors.join(', '), 400, 'WEAK_PASSWORD');
    }

    // Hash new password
    user.password = await PasswordUtil.hash(newPassword);
    user.updatedAt = new Date();
    users.set(user.id, user);

    // Revoke all refresh tokens
    await TokenService.revokeRefreshToken(user.id);

    logger.info(`Password reset for user: ${user.email}`);
  }

  /**
   * Get current user
   */
  async getCurrentUser(userId: string): Promise<UserResponse> {
    const user = users.get(userId);
    if (!user) {
      throw new AppError('User not found', 404, 'USER_NOT_FOUND');
    }

    return this.toUserResponse(user);
  }

  /**
   * Check login attempts
   */
  private async checkLoginAttempts(email: string): Promise<void> {
    const key = `login_attempts:${email}`;
    const attempts = await redisClient.get(key);

    if (attempts && parseInt(attempts) >= config.security.maxLoginAttempts) {
      const ttl = await redisClient.ttl(key);
      const remainingTime = Math.ceil(ttl / 60);
      throw new AppError(
        `Too many login attempts. Try again in ${remainingTime} minutes`,
        429,
        'TOO_MANY_ATTEMPTS'
      );
    }
  }

  /**
   * Increment login attempts
   */
  private async incrementLoginAttempts(email: string): Promise<void> {
    const key = `login_attempts:${email}`;
    const attempts = await redisClient.incr(key);

    if (attempts === 1) {
      await redisClient.expire(key, Math.floor(config.security.lockTime / 1000));
    }
  }

  /**
   * Reset login attempts
   */
  private async resetLoginAttempts(email: string): Promise<void> {
    const key = `login_attempts:${email}`;
    await redisClient.del(key);
  }

  /**
   * Sync user profile with user service
   */
  private async syncUserProfile(user: User): Promise<void> {
    try {
      await axios.post(
        `${config.userServiceUrl}/api/users/profile/create-minimal`,
        {
          userId: user.id,
          email: user.email,
          fullName: `${user.firstName} ${user.lastName}`,
          role: user.role
        },
        {
          headers: {
            'X-Service-Token': config.serviceToken,
            'Content-Type': 'application/json'
          },
          timeout: 5000 // 5 second timeout
        }
      );
      
      logger.info(`User profile synced with user service: ${user.email}`);
    } catch (error: any) {
      if (error.response) {
        logger.error(`User service responded with error: ${error.response.status}`, {
          data: error.response.data
        });
      } else if (error.request) {
        logger.error('User service did not respond', { url: config.userServiceUrl });
      } else {
        logger.error('Error setting up profile sync request', { message: error.message });
      }
      throw error;
    }
  }

  /**
   * Convert User to UserResponse
   */
  private toUserResponse(user: User): UserResponse {
    return {
      id: user.id,
      email: user.email,
      firstName: user.firstName,
      lastName: user.lastName,
      role: user.role,
      isEmailVerified: user.isEmailVerified,
      createdAt: user.createdAt,
    };
  }
}
