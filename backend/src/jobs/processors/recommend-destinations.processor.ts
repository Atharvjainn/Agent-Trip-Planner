import { Job } from 'bullmq';
import { aiClient } from '../../clients/ai.client';
import { TripJobPayload } from '../queue';
import { tripRepository } from '../../repositories/trip.repository';
import { jobRepository } from '../../repositories/job.repository';
import { logger } from '../../lib/logger';
import { fxService } from '../../services/fx.service';

export async function processRecommendDestinations(job: Job<TripJobPayload>) {
  const { tripId, userId } = job.data;
  const jobId = job.id!;

  logger.info(`Processing recommend-destinations for trip ${tripId} (Job ${jobId})`);
  await jobRepository.updateStatus(jobId, 'active');

  const trip = await tripRepository.findByIdAndUser(tripId, userId);
  if (!trip) {
    throw new Error(`Trip ${tripId} not found for user ${userId}`);
  }

  const startDate = trip.startDate.toISOString().slice(0, 10);
  const endDate = trip.endDate.toISOString().slice(0, 10);

  const aiResponse = await aiClient.recommendDestinations({
    tripId: trip.id,
    source: trip.source,
    startDate,
    endDate,
    travelers: trip.travelers,
    budgetTotal: {
      amountMinor: trip.budgetTotalMinor,
      currency: trip.baseCurrency,
    },
    vibes: trip.vibes,
  });

  const convertedOptions = await Promise.all(
    aiResponse.options.map(async (opt) => {
      try {
        const { converted } = await fxService.convert(opt.estimatedFlightPrice, trip.baseCurrency);
        return { ...opt, estimatedFlightPrice: converted };
      } catch {
        return opt;
      }
    })
  );

  await tripRepository.updateDestinationOptions(trip.id, convertedOptions);
  await jobRepository.updateStatus(jobId, 'completed');
  logger.info(`Completed recommend-destinations for trip ${tripId}`);
}
