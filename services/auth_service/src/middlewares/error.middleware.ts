import { Request, Response, NextFunction } from 'express';
import { AppError } from '../utils/errors';
import { ApiResponse } from '../types/express.types';
import logger from '../utils/logger';
import { isProduction } from '../utils/helpers';

export const errorHandler = (
  error: Error | AppError,
  req: Request,
  res: Response,
  _next: NextFunction
): void => {
  // Log error
  logger.error('Error occurred:', {
    error: error.message,
    stack: error.stack,
    path: req.path,
    method: req.method,
    requestId: req.requestId,
  });

  // Default error values
  let statusCode = 500;
  let code = 'INTERNAL_ERROR';
  let message = 'An unexpected error occurred';

  // Handle operational errors
  if (error instanceof AppError && error.isOperational) {
    statusCode = error.statusCode;
    code = error.code;
    message = error.message;
  }

  // Handle specific error types
  if (error.name === 'ValidationError') {
    statusCode = 400;
    code = 'VALIDATION_ERROR';
  }

  if (error.name === 'JsonWebTokenError') {
    statusCode = 401;
    code = 'INVALID_TOKEN';
    message = 'Invalid authentication token';
  }

  if (error.name === 'TokenExpiredError') {
    statusCode = 401;
    code = 'TOKEN_EXPIRED';
    message = 'Authentication token has expired';
  }

  // Build error response
  const response: ApiResponse = {
    success: false,
    message,
    error: {
      code,
      ...(isProduction() ? {} : { details: error.message, stack: error.stack }),
    },
    timestamp: new Date().toISOString(),
    requestId: req.requestId,
  };

  res.status(statusCode).json(response);
};

export const notFoundHandler = (req: Request, res: Response): void => {
  const response: ApiResponse = {
    success: false,
    message: `Route ${req.originalUrl} not found`,
    error: {
      code: 'NOT_FOUND',
    },
    timestamp: new Date().toISOString(),
  };

  res.status(404).json(response);
};
