import { Request, Response, NextFunction } from 'express';
import { generateRequestId } from '../utils/helpers';

export const requestLogger = (req: Request, res: Response, next: NextFunction): void => {
  // Generate and attach request ID
  req.requestId = generateRequestId();

  // Attach request ID to response headers
  res.setHeader('X-Request-ID', req.requestId);

  next();
};
