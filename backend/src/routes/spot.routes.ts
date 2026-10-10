import { Router } from 'express';
import { selectSpotsHandler } from '../controllers/spot.controller';
import { requireAuth } from '../middlewares/auth';
import { validate } from '../middlewares/validate';
import { selectSpotsSchema } from '../schemas/spot.schema';
import { tripParamsSchema } from '../schemas/trip.schema';
import { asyncHandler } from '../lib/async-handler';

const router = Router({ mergeParams: true });

router.post(
  '/',
  requireAuth,
  validate({
    params: tripParamsSchema,
    body: selectSpotsSchema,
  }),
  asyncHandler(selectSpotsHandler)
);

export default router;
