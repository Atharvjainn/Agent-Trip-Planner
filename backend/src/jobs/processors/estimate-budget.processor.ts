import { Job } from 'bullmq';
import { TripStatus } from '@prisma/client';
import { aiClient } from '../../clients/ai.client';
import { TripJobPayload } from '../queue';
import { tripRepository } from '../../repositories/trip.repository';
import { jobRepository } from '../../repositories/job.repository';
import { logger } from '../../lib/logger';

export async function processEstimateBudget(job: Job<TripJobPayload>) {
  const { tripId, userId } = job.data;
  const jobId = job.id!;

  logger.info(`Processing estimate-budget for trip ${tripId} (Job ${jobId})`);
  await jobRepository.updateStatus(jobId, 'active');

  const trip = await tripRepository.findByIdAndUser(tripId, userId);
  if (!trip) {
    throw new Error(`Trip ${tripId} not found for user ${userId}`);
  }

  const durationMs = trip.endDate.getTime() - trip.startDate.getTime();
  const durationDays = Math.max(1, Math.round(durationMs / (1000 * 60 * 60 * 24)));

  // Determine if trip is international (heuristic: if country is specified and not India for INR, etc.)
  const isInternational = Boolean(
    trip.destinationCountry &&
      !['india', 'in'].includes(trip.destinationCountry.toLowerCase().trim())
  );

  const aiResponse = await aiClient.estimateBudget({
    tripId: trip.id,
    budgetTotal: {
      amountMinor: trip.budgetTotalMinor,
      currency: trip.baseCurrency,
    },
    isInternational,
    durationDays,
    vibes: trip.vibes,
  });

  await tripRepository.updateBudgetAllocation(trip.id, aiResponse);

  // If the status is currently DESTINATION_SELECTED, advance to BUDGET_ESTIMATED
  if (trip.status === TripStatus.DESTINATION_SELECTED) {
    await tripRepository.updateStatus(trip.id, TripStatus.BUDGET_ESTIMATED);
  }

  await jobRepository.updateStatus(jobId, 'completed');
  logger.info(`Completed estimate-budget for trip ${tripId}`);
}
