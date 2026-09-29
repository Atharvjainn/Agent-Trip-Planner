import { Request, Response, NextFunction } from 'express';
import { fromNodeHeaders } from 'better-auth/node';
import { auth } from '../lib/auth';

export interface AuthenticatedRequest extends Request {
  user?: typeof auth.$Infer.Session.user;
  session?: typeof auth.$Infer.Session.session;
}

export const requireAuth = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const session = await auth.api.getSession({
      headers: fromNodeHeaders(req.headers),
    });

    if (!session) {
      return res.status(401).json({
        status: 'error',
        message: 'Unauthorized: Valid session required',
      });
    }

    req.user = session.user;
    req.session = session.session;
    next();
  } catch (error) {
    return res.status(500).json({
      status: 'error',
      message: 'Failed to authenticate request',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};
