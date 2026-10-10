import { Router } from 'express';
import { selectDestinationHandler } from '../controllers/destination.controller';
import { requireAuth } from '../middlewares/auth';
import { validate } from '../middlewares/validate';
import { selectDestinationSchema } from '../schemas/destination.schema';
import { tripParamsSchema } from '../schemas/trip.schema';
import { asyncHandler } from '../lib/async-handler';

const router = Router({ mergeParams: true });

router.post(
  '/',
  requireAuth,
  validate({
    params: tripParamsSchema,
    body: selectDestinationSchema,
  }),
  asyncHandler(selectDestinationHandler)
);

export default router;
