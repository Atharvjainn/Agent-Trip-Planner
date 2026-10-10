import { Router, Request, Response } from 'express';
import { requireAuth } from '../middlewares/auth';
import tripRouter from './trip.routes';
import jobRouter from './job.routes';

const router = Router();

// Public health checks
router.get('/', (_req: Request, res: Response) => {
  res.json({
    status: 'success',
    message: 'Travel Planner Backend API is running!',
  });
});

router.get('/health', (_req: Request, res: Response) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
  });
});

// Protected auth test endpoint
router.get('/api/me', requireAuth, (req: Request, res: Response) => {
  res.json({
    status: 'success',
    user: req.user,
    session: req.session,
  });
});

// Mount domain routes
router.use('/trips', tripRouter);
router.use('/jobs', jobRouter);

export default router;
