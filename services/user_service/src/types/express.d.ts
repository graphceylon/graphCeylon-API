declare global {
  namespace Express {
    export interface Request {
      userId?: string;
      userRole?: string;
      user?: {
        id: string;
        email: string;
        role: string;
      };
      requestId?: string;
    }
  }
}

export {};
