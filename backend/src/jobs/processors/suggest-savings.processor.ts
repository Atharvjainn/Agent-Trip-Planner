import { Job } from 'bullmq';
import { TripJobPayload } from '../queue';
import { tripRepository } from '../../repositories/trip.repository';
import { selectionRepository } from '../../repositories/selection.repository';
import { jobRepository } from '../../repositories/job.repository';
import { aiClient } from '../../clients/ai.client';
import { logger } from '../../lib/logger';

export async function processSuggestSavings(job: Job<TripJobPayload>) {
  const { tripId, userId } = job.data;
  const jobId = job.id!;
  logger.info(`Starting suggest-savings job ${jobId} for trip ${tripId}`);
  await jobRepository.updateStatus(jobId, 'active');

  const trip = await tripRepository.findByIdAndUser(tripId, userId);
  if (!trip) {
    throw new Error(`Trip ${tripId} not found`);
  }

  // Calculate nights
  const startMs = new Date(trip.startDate).getTime();
  const endMs = new Date(trip.endDate).getTime();
  const nights = Math.max(1, Math.round((endMs - startMs) / (1000 * 60 * 60 * 24)));

  // Extract selected flight & hotel from Selection table
  const flightSelections = await selectionRepository.findByTripIdAndType(tripId, 'flight');
  const hotelSelections = await selectionRepository.findByTripIdAndType(tripId, 'hotel');

  const flightPrice = flightSelections.length > 0 ? (flightSelections[0].convertedMoney as any) : undefined;
  const hotelPricePerNight = hotelSelections.length > 0 && (hotelSelections[0].metadata as any)?.pricePerNightConverted
    ? ((hotelSelections[0].metadata as any).pricePerNightConverted)
    : undefined;

  let stayBudget = undefined;
  const rawAllocation = (trip as any).budgetAllocation;
  if (rawAllocation && typeof rawAllocation === 'object') {
    const allocations = Array.isArray(rawAllocation.allocations)
      ? rawAllocation.allocations
      : Array.isArray(rawAllocation)
      ? rawAllocation
      : [];
    const stayCat = allocations.find((a: any) => a.category === 'stay');
    if (stayCat && stayCat.amount) {
      stayBudget = stayCat.amount;
    }
  }

  const response = await aiClient.suggestSavings({
    tripId: trip.id,
    selections: {
      flightPrice,
      hotelPricePerNight,
      nights,
      stayBudget,
    },
  });

  await tripRepository.updateSavingSuggestions(trip.id, response.suggestions || []);
  await jobRepository.updateStatus(jobId, 'completed');
  logger.info(`suggest-savings completed with ${response.suggestions?.length || 0} suggestions for trip ${trip.id}`);

  return {
    tripId: trip.id,
    suggestionsCount: response.suggestions?.length || 0,
    fallbackUsed: response.fallbackUsed,
  };
}
