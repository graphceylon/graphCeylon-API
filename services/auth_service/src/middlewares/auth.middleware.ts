import { Request, Response, NextFunction } from 'express';
import { TokenService } from '../utils/token.util';
import { AppError, AuthenticationError } from '../utils/errors';
import { UserRole } from '../types/auth.types';

export const authenticate = async (
  req: Request,
  _res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      throw new AuthenticationError('No token provided');
    }

    const token = authHeader.split(' ')[1];

    // Check if token is blacklisted
    const isBlacklisted = await TokenService.isTokenBlacklisted(token);
    if (isBlacklisted) {
      throw new AuthenticationError('Token has been revoked');
    }

    // Verify token
    const decoded = TokenService.verifyAccessToken(token);

    // Attach user info to request
    req.userId = decoded.userId;
    req.user = {
      userId: decoded.userId,
      email: decoded.email,
      role: decoded.role,
    };

    next();
  } catch (error) {
    next(error);
  }
};

export const authorize = (...roles: UserRole[]) => {
  return (req: Request, _res: Response, next: NextFunction): void => {
    try {
      if (!req.user) {
        throw new AuthenticationError('User not authenticated');
      }

      if (!roles.includes(req.user.role)) {
        throw new AppError('Insufficient permissions', 403, 'FORBIDDEN');
      }

      next();
    } catch (error) {
      next(error);
    }
  };
};
