import jwt, { SignOptions } from 'jsonwebtoken';
import { v4 as uuidv4 } from 'uuid';
import config from '../config';
import { JwtPayload, DecodedToken, UserRole } from '../types/auth.types';
import redisClient from '../config/redis';
import { AppError } from './errors';

export class TokenService {
  /**
   * Generate access token
   */
  static generateAccessToken(userId: string, email: string, role: UserRole): string {
    const payload: JwtPayload = {
      userId,
      email,
      role,
      type: 'access',
    };

    return jwt.sign(payload, config.jwt.secret, {
      expiresIn: config.jwt.expiresIn,
    } as SignOptions);
  }

  /**
   * Generate refresh token
   */
  static generateRefreshToken(userId: string, email: string, role: UserRole): string {
    const payload: JwtPayload = {
      userId,
      email,
      role,
      type: 'refresh',
    };

    return jwt.sign(payload, config.jwt.refreshSecret, {
      expiresIn: config.jwt.refreshExpiresIn,
    } as SignOptions);
  }

  /**
   * Generate both access and refresh tokens
   */
  static generateTokenPair(userId: string, email: string, role: UserRole) {
    return {
      accessToken: this.generateAccessToken(userId, email, role),
      refreshToken: this.generateRefreshToken(userId, email, role),
      expiresIn: config.jwt.expiresIn,
    };
  }

  /**
   * Verify access token
   */
  static verifyAccessToken(token: string): DecodedToken {
    try {
      const decoded = jwt.verify(token, config.jwt.secret) as DecodedToken;

      if (decoded.type !== 'access') {
        throw new AppError('Invalid token type', 401, 'INVALID_TOKEN_TYPE');
      }

      return decoded;
    } catch (error) {
      if (error instanceof jwt.TokenExpiredError) {
        throw new AppError('Token expired', 401, 'TOKEN_EXPIRED');
      }
      if (error instanceof jwt.JsonWebTokenError) {
        throw new AppError('Invalid token', 401, 'INVALID_TOKEN');
      }
      throw error;
    }
  }

  /**
   * Verify refresh token
   */
  static verifyRefreshToken(token: string): DecodedToken {
    try {
      const decoded = jwt.verify(token, config.jwt.refreshSecret) as DecodedToken;

      if (decoded.type !== 'refresh') {
        throw new AppError('Invalid token type', 401, 'INVALID_TOKEN_TYPE');
      }

      return decoded;
    } catch (error) {
      if (error instanceof jwt.TokenExpiredError) {
        throw new AppError('Refresh token expired', 401, 'REFRESH_TOKEN_EXPIRED');
      }
      if (error instanceof jwt.JsonWebTokenError) {
        throw new AppError('Invalid refresh token', 401, 'INVALID_REFRESH_TOKEN');
      }
      throw error;
    }
  }

  /**
   * Store refresh token in Redis
   */
  static async storeRefreshToken(userId: string, refreshToken: string): Promise<void> {
    const key = `refresh_token:${userId}`;
    const expiresIn = this.getRefreshTokenExpirySeconds();
    await redisClient.set(key, refreshToken, expiresIn);
  }

  /**
   * Validate refresh token from Redis
   */
  static async validateRefreshToken(userId: string, refreshToken: string): Promise<boolean> {
    const key = `refresh_token:${userId}`;
    const storedToken = await redisClient.get(key);
    return storedToken === refreshToken;
  }

  /**
   * Revoke refresh token
   */
  static async revokeRefreshToken(userId: string): Promise<void> {
    const key = `refresh_token:${userId}`;
    await redisClient.del(key);
  }

  /**
   * Blacklist access token
   */
  static async blacklistToken(token: string): Promise<void> {
    const decoded = jwt.decode(token) as DecodedToken;
    if (!decoded || !decoded.exp) return;

    const expiresIn = decoded.exp - Math.floor(Date.now() / 1000);
    if (expiresIn > 0) {
      const key = `blacklist:${token}`;
      await redisClient.set(key, 'true', expiresIn);
    }
  }

  /**
   * Check if token is blacklisted
   */
  static async isTokenBlacklisted(token: string): Promise<boolean> {
    const key = `blacklist:${token}`;
    return await redisClient.exists(key);
  }

  /**
   * Generate email verification token
   */
  static generateEmailVerificationToken(): string {
    return uuidv4();
  }

  /**
   * Generate password reset token
   */
  static generatePasswordResetToken(): string {
    return uuidv4();
  }

  /**
   * Store email verification token
   */
  static async storeEmailVerificationToken(userId: string, token: string): Promise<void> {
    const key = `email_verification:${token}`;
    await redisClient.set(key, userId, 24 * 60 * 60); // 24 hours
  }

  /**
   * Verify email verification token
   */
  static async verifyEmailVerificationToken(token: string): Promise<string | null> {
    const key = `email_verification:${token}`;
    const userId = await redisClient.get(key);
    if (userId) {
      await redisClient.del(key);
    }
    return userId;
  }

  /**
   * Store password reset token
   */
  static async storePasswordResetToken(userId: string, token: string): Promise<void> {
    const key = `password_reset:${token}`;
    await redisClient.set(key, userId, 60 * 60); // 1 hour
  }

  /**
   * Verify password reset token
   */
  static async verifyPasswordResetToken(token: string): Promise<string | null> {
    const key = `password_reset:${token}`;
    const userId = await redisClient.get(key);
    if (userId) {
      await redisClient.del(key);
    }
    return userId;
  }

  /**
   * Get refresh token expiry in seconds
   */
  private static getRefreshTokenExpirySeconds(): number {
    const match = config.jwt.refreshExpiresIn.match(/(\d+)([dhms])/);
    if (!match) return 7 * 24 * 60 * 60; // Default 7 days

    const value = parseInt(match[1]);
    const unit = match[2];

    switch (unit) {
      case 'd':
        return value * 24 * 60 * 60;
      case 'h':
        return value * 60 * 60;
      case 'm':
        return value * 60;
      case 's':
        return value;
      default:
        return 7 * 24 * 60 * 60;
    }
  }
}
