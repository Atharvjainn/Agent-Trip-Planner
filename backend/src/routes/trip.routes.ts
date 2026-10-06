import { Router } from 'express';
import { createTripHandler, getTripHandler } from '../controllers/trip.controller';
import { requireAuth } from '../middlewares/auth';
import { validate } from '../middlewares/validate';
import { createTripSchema, tripParamsSchema } from '../schemas/trip.schema';
import { asyncHandler } from '../lib/async-handler';
import destinationRouter from './destination.routes';
import spotRouter from './spot.routes';
import budgetRouter from './budget.routes';

const router = Router();

router.post(
  '/',
  requireAuth,
  validate({ body: createTripSchema }),
  asyncHandler(createTripHandler)
);

router.get(
  '/:id',
  requireAuth,
  validate({ params: tripParamsSchema }),
  asyncHandler(getTripHandler)
);

// Mount nested sub-routers
router.use('/:id/destination', destinationRouter);
router.use('/:id/spots', spotRouter);
router.use('/:id/budget', budgetRouter);

export default router;
