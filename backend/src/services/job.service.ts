import { jobRepository } from '../repositories/job.repository';
import { NotFoundError } from '../lib/errors';

export class JobService {
  async getJobStatus(jobId: string, userId: string) {
    const job = await jobRepository.findByIdAndUser(jobId, userId);
    if (!job) {
      throw new NotFoundError('Job not found');
    }
    return {
      id: job.id,
      name: job.name,
      status: job.status,
      error: job.error,
    };
  }
}

export const jobService = new JobService();
