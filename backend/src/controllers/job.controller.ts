import { Request, Response } from 'express';
import { jobService } from '../services/job.service';
import { JobParams } from '../schemas/job.schema';

export async function getJobHandler(req: Request, res: Response) {
  const userId = req.user!.id;
  const { jobId } = req.params as JobParams;
  const job = await jobService.getJobStatus(jobId, userId);

  return res.status(200).json({
    status: 'success',
    data: job,
  });
}
