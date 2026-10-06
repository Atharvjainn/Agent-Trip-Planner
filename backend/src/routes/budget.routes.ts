import { Router } from 'express';
import { getTripBudgetHandler } from '../controllers/budget.controller';
import { requireAuth } from '../middlewares/auth';
import { validate } from '../middlewares/validate';
import { tripParamsSchema } from '../schemas/trip.schema';
import { asyncHandler } from '../lib/async-handler';

const router = Router({ mergeParams: true });

router.get(
  '/',
  requireAuth,
  validate({ params: tripParamsSchema }),
  asyncHandler(getTripBudgetHandler)
);

export default router;
