import { Request, Response, NextFunction } from 'express';
import { AppError } from '../lib/errors';
import { logger } from '../lib/logger';

export function errorHandler(
  err: Error,
  _req: Request,
  res: Response,
  _next: NextFunction
) {
  if (err instanceof AppError) {
    if (!err.isOperational) {
      logger.error('Non-operational AppError:', { error: err.message, stack: err.stack });
    }
    return res.status(err.statusCode).json({
      status: 'error',
      message: err.message,
    });
  }

  // Unhandled internal errors
  logger.error('Unhandled internal error:', { error: err.message, stack: err.stack });
  return res.status(500).json({
    status: 'error',
    message: 'Internal server error',
  });
}
