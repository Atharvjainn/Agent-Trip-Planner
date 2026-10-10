import { Router } from 'express';
import { summaryController } from '../controllers/summary.controller';
import { requireAuth } from '../middlewares/auth';
import { asyncHandler } from '../lib/async-handler';

const router = Router({ mergeParams: true });

router.use(requireAuth);

router.post('/build', asyncHandler((req, res, next) =>
  summaryController.triggerBuildSummary(req, res, next)
));

router.get('/', asyncHandler((req, res, next) =>
  summaryController.getSummary(req, res, next)
));

export default router;
