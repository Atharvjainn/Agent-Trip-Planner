import { tripRepository } from '../repositories/trip.repository';
import { selectionRepository } from '../repositories/selection.repository';
import { tripQueue } from '../jobs/queue';
import { jobRepository } from '../repositories/job.repository';
import { NotFoundError } from '../lib/errors';
import { TripStatus } from '@prisma/client';

export class SummaryService {
  async triggerBuildSummary(tripId: string, userId: string) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    // Trigger suggest-savings job in parallel if not already present
    if (!trip.savingSuggestions) {
      const savingsJob = await tripQueue.add('suggest-savings', { tripId, userId });
      if (savingsJob.id) {
        await jobRepository.create({
          id: savingsJob.id,
          tripId: trip.id,
          userId,
          name: 'suggest-savings',
        });
      }
    }

    const job = await tripQueue.add('build-summary', { tripId, userId });
    if (job.id) {
      await jobRepository.create({
        id: job.id,
        tripId: trip.id,
        userId,
        name: 'build-summary',
      });
    }

    return {
      jobId: job.id,
      status: 'queued',
    };
  }

  async getSummary(tripId: string, userId: string) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    const pendingJob = await jobRepository.findLatestByTripAndName(tripId, 'build-summary');

    // Get all user selections
    const allSelections = await selectionRepository.findByTripId(tripId);
    const flightSelection = allSelections.find((s) => s.type === 'flight') || null;
    const hotelSelection = allSelections.find((s) => s.type === 'hotel') || null;
    const spotSelections = allSelections.filter((s) => s.type === 'spot');

    const startMs = new Date(trip.startDate).getTime();
    const endMs = new Date(trip.endDate).getTime();
    const nights = Math.max(1, Math.round((endMs - startMs) / (1000 * 60 * 60 * 24)));

    // Calculate totals spent
    let flightSpentMinor = flightSelection ? (flightSelection.convertedMoney as any).amountMinor : 0;
    let hotelSpentMinor = hotelSelection ? (hotelSelection.convertedMoney as any).amountMinor : 0;

    const summaryData = (trip.summary as any) || null;
    const commuteSpentMinor = summaryData?.commute?.tripTotalCost?.amountMinor || 0;

    const totalEstimatedMinor = flightSpentMinor + hotelSpentMinor + commuteSpentMinor;
    const remainingMinor = trip.budgetTotalMinor - totalEstimatedMinor;

    return {
      trip: {
        id: trip.id,
        status: trip.status,
        source: trip.source,
        destinationCity: trip.destinationCity,
        destinationCountry: trip.destinationCountry,
        startDate: trip.startDate,
        endDate: trip.endDate,
        travelers: trip.travelers,
        vibes: trip.vibes,
        baseCurrency: trip.baseCurrency,
        budgetTotalMinor: trip.budgetTotalMinor,
      },
      nights,
      selections: {
        flight: flightSelection,
        hotel: hotelSelection,
        spots: spotSelections,
      },
      costs: {
        flightSpentMinor,
        hotelSpentMinor,
        commuteSpentMinor,
        totalEstimatedMinor,
        remainingMinor,
        currency: trip.baseCurrency,
      },
      summary: summaryData,
      savingSuggestions: (trip.savingSuggestions as any[]) || [],
      pendingJob:
        pendingJob && ['queued', 'active'].includes(pendingJob.status)
          ? {
              id: pendingJob.id,
              status: pendingJob.status,
            }
          : null,
    };
  }
}

export const summaryService = new SummaryService();
