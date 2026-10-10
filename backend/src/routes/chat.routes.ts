import { Router } from 'express';
import { sendMessageHandler } from '../controllers/chat.controller';
import { requireAuth } from '../middlewares/auth';
import { validate } from '../middlewares/validate';
import { chatRequestSchema } from '../schemas/chat.schema';
import { tripParamsSchema } from '../schemas/trip.schema';
import { asyncHandler } from '../lib/async-handler';

const router = Router({ mergeParams: true });

router.post(
  '/',
  requireAuth,
  validate({
    params: tripParamsSchema,
    body: chatRequestSchema,
  }),
  asyncHandler(sendMessageHandler)
);

export default router;
