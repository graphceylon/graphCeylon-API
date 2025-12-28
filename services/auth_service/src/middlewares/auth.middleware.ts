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
    // ✅ 0) INTERNAL SERVICE-TO-SERVICE AUTH (Orchestrator → User Service)
    const expectedServiceToken = process.env.SERVICE_TOKEN;
    const serviceToken = req.headers['x-service-token'];

    if (
      expectedServiceToken &&
      typeof serviceToken === 'string' &&
      serviceToken === expectedServiceToken
    ) {
      // Mark internal call (optional)
      (req as any).isInternal = true;

      // Optionally attach a "system" user context (optional)
      req.userId = 'internal-service';
      req.user = {
        userId: 'internal-service',
        email: 'internal@graphceylon',
        role: 'admin' as any, // or 'system' if you have it
      };

      return next();
    }

    // ✅ 1) NORMAL USER JWT AUTH
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

    return next();
  } catch (error) {
    return next(error);
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
