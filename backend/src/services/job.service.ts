import { jobRepository } from '../repositories/job.repository';
import { tripQueue } from '../jobs/queue';
import { NotFoundError } from '../lib/errors';

export class JobService {
  async getJobStatus(jobId: string, userId: string) {
    const job = await jobRepository.findByIdAndUser(jobId, userId);
    if (!job) {
      throw new NotFoundError('Job not found');
    }

    let status = job.status;
    let error = job.error;

    // If still marked queued/active in DB, verify with BullMQ directly for instant real-time sync
    if (['queued', 'active'].includes(status)) {
      try {
        const bullJob = await tripQueue.getJob(jobId);
        if (bullJob) {
          const state = await bullJob.getState();
          if (state === 'completed') {
            status = 'completed';
            await jobRepository.updateStatus(jobId, 'completed');
          } else if (state === 'failed') {
            status = 'failed';
            error = bullJob.failedReason || error;
            await jobRepository.updateStatus(jobId, 'failed', error);
          } else if (state === 'active' && status === 'queued') {
            status = 'active';
            await jobRepository.updateStatus(jobId, 'active');
          }
        }
      } catch {
        // Fall back gracefully to database status
      }
    }

    return {
      id: job.id,
      name: job.name,
      status,
      error,
    };
  }
}

export const jobService = new JobService();
