import { Queue } from 'bullmq';
import { redisConnection } from '../lib/redis';
import { logger } from '../lib/logger';

export interface TripJobPayload {
  tripId: string;
  userId: string;
}

export const TRIP_QUEUE_NAME = 'trip-jobs';

export const tripQueue = new Queue<TripJobPayload>(TRIP_QUEUE_NAME, {
  connection: redisConnection,
  defaultJobOptions: {
    attempts: 2,
    backoff: {
      type: 'exponential',
      delay: 2000,
    },
    removeOnComplete: 100,
    removeOnFail: 100,
  },
});

export async function enqueueJob(
  name: string,
  payload: TripJobPayload,
  customJobId?: string
): Promise<string> {
  const job = await tripQueue.add(name, payload, {
    jobId: customJobId,
  });
  logger.info(`Enqueued job [${name}] with ID ${job.id} for trip ${payload.tripId}`);
  return job.id!;
}
