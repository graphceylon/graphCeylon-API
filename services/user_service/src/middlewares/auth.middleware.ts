import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import config from '../config';
import { AuthenticationError, AuthorizationError } from '../utils/errors';
import { JwtPayload, UserRole } from '../types';

export const authenticate = (req: Request, _res: Response, next: NextFunction): void => {
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

      // Attach a system user context (so authorize() can pass)
      req.userId = 'internal-service';
      req.user = {
        id: 'internal-service',
        email: 'internal@graphceylon',
        role: 'admin' as any, // IMPORTANT: must be allowed by authorize() if used
      };

      return next();
    }

    // ✅ 1) NORMAL USER JWT AUTH
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      throw new AuthenticationError('No token provided');
    }

    const token = authHeader.split(' ')[1];

    const decoded = jwt.verify(token, config.jwt.secret) as JwtPayload;

    req.userId = decoded.userId;
    req.user = {
      id: decoded.userId,
      email: decoded.email,
      role: decoded.role,
    };

    next();
  } catch (error) {
    if (error instanceof jwt.TokenExpiredError) {
      next(new AuthenticationError('Token expired'));
    } else if (error instanceof jwt.JsonWebTokenError) {
      next(new AuthenticationError('Invalid token'));
    } else {
      next(error);
    }
  }
};
export const authorize = (...roles: UserRole[]) => {
  return (req: Request, _res: Response, next: NextFunction): void => {
    try {
      if (!req.user) {
        throw new AuthenticationError('User not authenticated');
      }

      // If route says authorize('admin', 'user') etc.
      if (roles.length > 0 && !roles.includes(req.user.role as UserRole)) {
        throw new AuthorizationError('Insufficient permissions');
      }

      next();
    } catch (error) {
      next(error);
    }
  };
};

export const optionalAuth = (req: Request, _res: Response, next: NextFunction): void => {
  try {
    // allow internal service token
    const expectedServiceToken = process.env.SERVICE_TOKEN;
    const serviceToken = req.headers['x-service-token'];

    if (
      expectedServiceToken &&
      typeof serviceToken === 'string' &&
      serviceToken === expectedServiceToken
    ) {
      (req as any).isInternal = true;
      req.userId = 'internal-service';
      req.user = {
        id: 'internal-service',
        email: 'internal@graphceylon',
        role: 'admin' as any,
      };
      return next();
    }

    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return next(); // optional: skip if no token
    }

    const token = authHeader.split(' ')[1];
    const decoded = jwt.verify(token, config.jwt.secret) as JwtPayload;

    req.userId = decoded.userId;
    req.user = {
      id: decoded.userId,
      email: decoded.email,
      role: decoded.role,
    };

    next();
  } catch {
    // optional: ignore token errors
    next();
  }
};

