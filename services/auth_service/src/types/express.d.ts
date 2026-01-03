import { UserRole } from './auth.types';

declare global {
  namespace Express {
    export interface Request {
      userId?: string;
      user?: {
        userId: string;
        email: string;
        role: UserRole;
      };
      requestId?: string;
    }
  }
}
