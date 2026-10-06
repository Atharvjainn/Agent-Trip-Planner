import { Router } from 'express';
import { getJobHandler } from '../controllers/job.controller';
import { requireAuth } from '../middlewares/auth';
import { validate } from '../middlewares/validate';
import { jobParamsSchema } from '../schemas/job.schema';
import { asyncHandler } from '../lib/async-handler';

const router = Router();

router.get(
  '/:jobId',
  requireAuth,
  validate({ params: jobParamsSchema }),
  asyncHandler(getJobHandler)
);

export default router;
