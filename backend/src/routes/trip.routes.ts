import { Router } from 'express';
import { createTripHandler, getTripHandler } from '../controllers/trip.controller';
import { requireAuth } from '../middlewares/auth';
import { validate } from '../middlewares/validate';
import { createTripSchema, tripParamsSchema } from '../schemas/trip.schema';
import { asyncHandler } from '../lib/async-handler';
import destinationRouter from './destination.routes';
import spotRouter from './spot.routes';
import budgetRouter from './budget.routes';
import flightRouter from './flight.routes';
import hotelRouter from './hotel.routes';
import summaryRouter from './summary.routes';
import chatRouter from './chat.routes';
import { createTripChatHandler } from '../controllers/chat.controller';
import { chatRequestSchema } from '../schemas/chat.schema';

const router = Router();

router.post(
  '/',
  requireAuth,
  validate({ body: createTripSchema }),
  asyncHandler(createTripHandler)
);

router.post(
  '/chat',
  requireAuth,
  validate({ body: chatRequestSchema }),
  asyncHandler(createTripChatHandler)
);

router.get(
  '/:id',
  requireAuth,
  validate({ params: tripParamsSchema }),
  asyncHandler(getTripHandler)
);

// Mount nested sub-routers
router.use('/:id/chat', chatRouter);
router.use('/:id/destination', destinationRouter);
router.use('/:id/spots', spotRouter);
router.use('/:id/budget', budgetRouter);
router.use('/:id/flights', flightRouter);
router.use('/:id/flight', flightRouter);
router.use('/:id/hotels', hotelRouter);
router.use('/:id/hotel', hotelRouter);
router.use('/:id/summary', summaryRouter);

export default router;


