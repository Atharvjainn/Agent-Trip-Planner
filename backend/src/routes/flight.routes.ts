import { Router } from 'express';
import { flightController } from '../controllers/flight.controller';
import { requireAuth } from '../middlewares/auth';
import { asyncHandler } from '../lib/async-handler';

const router = Router({ mergeParams: true });

router.use(requireAuth);

router.post('/search', asyncHandler((req, res, next) =>
  flightController.triggerSearch(req, res, next)
));

router.get('/', asyncHandler((req, res, next) =>
  flightController.getFlightOptions(req, res, next)
));

router.post('/', asyncHandler((req, res, next) =>
  flightController.selectFlight(req, res, next)
));

export default router;

