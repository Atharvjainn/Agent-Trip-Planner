import { Job } from 'bullmq';
import { TripJobPayload } from '../queue';
import { tripRepository } from '../../repositories/trip.repository';
import { jobRepository } from '../../repositories/job.repository';
import { aiClient } from '../../clients/ai.client';
import { fxService } from '../../services/fx.service';
import { budgetService } from '../../services/budget.service';
import { logger } from '../../lib/logger';
import { Money } from '../../schemas/common.schema';

export async function processSearchFlights(job: Job<TripJobPayload>) {
  const { tripId, userId } = job.data;
  const jobId = job.id!;
  logger.info(`Starting search-flights job ${jobId} for trip ${tripId}`);
  await jobRepository.updateStatus(jobId, 'active');

  const trip = await tripRepository.findByIdAndUser(tripId, userId);
  if (!trip) {
    throw new Error(`Trip ${tripId} not found`);
  }

  if (!trip.destinationCity) {
    throw new Error(`Trip ${tripId} has no destination selected`);
  }

  // Determine flight budget in baseCurrency
  let flightsBudget: Money = {
    amountMinor: Math.floor(trip.budgetTotalMinor * 0.35),
    currency: trip.baseCurrency,
  };

  const rawAllocation = (trip as any).budgetAllocation;
  if (rawAllocation && typeof rawAllocation === 'object') {
    const allocations = Array.isArray(rawAllocation.allocations)
      ? rawAllocation.allocations
      : Array.isArray(rawAllocation)
      ? rawAllocation
      : [];
    const flightCat = allocations.find((a: any) => a.category === 'flights');
    if (flightCat && flightCat.amount) {
      flightsBudget = {
        amountMinor: flightCat.amount.amountMinor,
        currency: flightCat.amount.currency || trip.baseCurrency,
      };
    }
  } else {
    const isInternational = Boolean(
      trip.destinationCountry &&
        !['india', 'in'].includes(trip.destinationCountry.toLowerCase().trim())
    );
    const fallback = budgetService.calculateDefaultSplit(
      trip.budgetTotalMinor,
      trip.baseCurrency,
      isInternational
    );
    const flightCat = fallback.allocations.find((a) => a.category === 'flights');
    if (flightCat) {
      flightsBudget = flightCat.amount;
    }
  }

  const startDateStr = trip.startDate.toISOString().split('T')[0];
  const endDateStr = trip.endDate.toISOString().split('T')[0];

  const response = await aiClient.searchFlights({
    tripId: trip.id,
    source: trip.source,
    destination: trip.destinationCity,
    startDate: startDateStr,
    endDate: endDateStr,
    travelers: trip.travelers,
    flightsBudget,
  });

  // Enrich each flight option with converted price in trip.baseCurrency
  const enrichedOptions = await Promise.all(
    response.options.map(async (opt) => {
      try {
        const { converted, rate } = await fxService.convert(opt.price, trip.baseCurrency);
        return {
          ...opt,
          convertedPrice: converted,
          fxRate: rate,
          isSelected: false,
        };
      } catch (err: any) {
        logger.warn(`Failed to convert flight price for option ${opt.providerRef.id}:`, {
          error: err.message,
        });
        return {
          ...opt,
          convertedPrice: opt.price,
          fxRate: 1.0,
          isSelected: false,
        };
      }
    })
  );

  await tripRepository.updateFlightOptions(trip.id, enrichedOptions);
  await jobRepository.updateStatus(jobId, 'completed');
  logger.info(`search-flights completed with ${enrichedOptions.length} options for trip ${trip.id}`);

  return {
    tripId: trip.id,
    optionsCount: enrichedOptions.length,
    fallbackUsed: response.fallbackUsed,
  };
}
