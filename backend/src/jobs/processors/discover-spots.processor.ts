import { Job } from 'bullmq';
import { aiClient } from '../../clients/ai.client';
import { TripJobPayload } from '../queue';
import { tripRepository } from '../../repositories/trip.repository';
import { jobRepository } from '../../repositories/job.repository';
import { logger } from '../../lib/logger';

export async function processDiscoverSpots(job: Job<TripJobPayload>) {
  const { tripId, userId } = job.data;
  const jobId = job.id!;

  logger.info(`Processing discover-spots for trip ${tripId} (Job ${jobId})`);
  await jobRepository.updateStatus(jobId, 'active');

  const trip = await tripRepository.findByIdAndUser(tripId, userId);
  if (!trip) {
    throw new Error(`Trip ${tripId} not found for user ${userId}`);
  }

  if (!trip.destinationCity || !trip.destinationCountry) {
    throw new Error(`Trip ${tripId} missing destination city or country`);
  }

  const startDate = trip.startDate.toISOString().slice(0, 10);
  const endDate = trip.endDate.toISOString().slice(0, 10);

  const aiResponse = await aiClient.discoverSpots({
    tripId: trip.id,
    city: trip.destinationCity,
    country: trip.destinationCountry,
    startDate,
    endDate,
    vibes: trip.vibes,
  });

  await tripRepository.updateSpotOptions(trip.id, aiResponse.spots);
  await jobRepository.updateStatus(jobId, 'completed');
  logger.info(`Completed discover-spots for trip ${tripId}`);
}
