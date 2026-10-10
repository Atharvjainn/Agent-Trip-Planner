import { Worker, Job } from 'bullmq';
import { redisConnection } from './lib/redis';
import { TRIP_QUEUE_NAME, TripJobPayload } from './jobs/queue';
import { processRecommendDestinations } from './jobs/processors/recommend-destinations.processor';
import { processDiscoverSpots } from './jobs/processors/discover-spots.processor';
import { processEstimateBudget } from './jobs/processors/estimate-budget.processor';
import { processSearchFlights } from './jobs/processors/search-flights.processor';
import { processSearchHotels } from './jobs/processors/search-hotels.processor';
import { processSuggestSavings } from './jobs/processors/suggest-savings.processor';
import { processBuildSummary } from './jobs/processors/build-summary.processor';
import { jobRepository } from './repositories/job.repository';
import { logger } from './lib/logger';

export const worker = new Worker<TripJobPayload>(
  TRIP_QUEUE_NAME,
  async (job: Job<TripJobPayload>) => {
    switch (job.name) {
      case 'recommend-destinations':
        return await processRecommendDestinations(job);
      case 'discover-spots':
        return await processDiscoverSpots(job);
      case 'estimate-budget':
        return await processEstimateBudget(job);
      case 'search-flights':
        return await processSearchFlights(job);
      case 'search-hotels':
        return await processSearchHotels(job);
      case 'suggest-savings':
        return await processSuggestSavings(job);
      case 'build-summary':
        return await processBuildSummary(job);
      default:
        logger.warn(`Unknown job name: ${job.name}`);
        throw new Error(`Unknown job name: ${job.name}`);
    }
  },
  {
    connection: redisConnection,
    concurrency: 5,
  }
);

worker.on('ready', () => {
  logger.info(`BullMQ Worker ready on queue: ${TRIP_QUEUE_NAME}`);
});

worker.on('failed', async (job: Job<TripJobPayload> | undefined, err: Error) => {
  if (job?.id) {
    logger.error(`Job ${job.id} [${job.name}] failed: ${err.message}`);
    // If it reached max attempts or permanently failed
    if (job.attemptsMade >= (job.opts.attempts || 1)) {
      await jobRepository.updateStatus(
        job.id,
        'failed',
        "We couldn't fetch results. Try again."
      );
    }
  }
});

worker.on('error', (err: Error) => {
  logger.error('BullMQ Worker error:', { error: err.message });
});

async function shutdown() {
  logger.info('Shutting down worker...');
  await worker.close();
  await redisConnection.quit();
  process.exit(0);
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
