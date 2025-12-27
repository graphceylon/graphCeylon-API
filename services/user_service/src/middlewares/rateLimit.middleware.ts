import { Request, Response } from 'express';
import rateLimit from 'express-rate-limit';
import config from '../config';
import { TooManyRequestsError } from '../utils/errors';

export const generalLimiter = rateLimit({
  windowMs: config.rateLimit.windowMs,
  max: config.rateLimit.maxRequests,
  message: 'Too many requests from this IP, please try again later',
  standardHeaders: true,
  legacyHeaders: false,
  handler: (_req: Request, _res: Response) => {
    throw new TooManyRequestsError('Too many requests, please try again later');
  },
});
