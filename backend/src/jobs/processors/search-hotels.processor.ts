import { Job } from 'bullmq';
import { TripJobPayload } from '../queue';
import { tripRepository } from '../../repositories/trip.repository';
import { selectionRepository } from '../../repositories/selection.repository';
import { jobRepository } from '../../repositories/job.repository';
import { aiClient } from '../../clients/ai.client';
import { fxService } from '../../services/fx.service';
import { budgetService } from '../../services/budget.service';
import { logger } from '../../lib/logger';
import { Money } from '../../schemas/common.schema';
import { SelectedSpotInput } from '../../schemas/hotel.schema';

export async function processSearchHotels(job: Job<TripJobPayload>) {
  const { tripId, userId } = job.data;
  const jobId = job.id!;
  logger.info(`Starting search-hotels job ${jobId} for trip ${tripId}`);
  await jobRepository.updateStatus(jobId, 'active');

  const trip = await tripRepository.findByIdAndUser(tripId, userId);
  if (!trip) {
    throw new Error(`Trip ${tripId} not found`);
  }

  if (!trip.destinationCity) {
    throw new Error(`Trip ${tripId} has no destination selected`);
  }

  // Calculate nights
  const startMs = new Date(trip.startDate).getTime();
  const endMs = new Date(trip.endDate).getTime();
  const nights = Math.max(1, Math.round((endMs - startMs) / (1000 * 60 * 60 * 24)));

  // Extract selected spots from Spot selections or spotOptions
  let selectedSpots: SelectedSpotInput[] = [];
  const spotSelections = await selectionRepository.findByTripIdAndType(tripId, 'spot');

  if (spotSelections.length > 0) {
    selectedSpots = spotSelections.map((sel) => {
      const meta = sel.metadata as any;
      return {
        id: sel.providerId,
        name: sel.providerName || sel.providerId,
        location: meta?.location || { lat: 0, lng: 0 },
      };
    });
  } else if (trip.spotOptions && Array.isArray(trip.spotOptions)) {
    const spots = trip.spotOptions as any[];
    const chosen = spots.filter((s) => s.isSelected);
    const pool = chosen.length > 0 ? chosen : spots.slice(0, 5);
    selectedSpots = pool.map((s) => ({
      id: s.providerRef.id || s.name,
      name: s.name,
      location: s.location,
    }));
  }

  if (selectedSpots.length === 0) {
    // Fallback default center point if no spots
    selectedSpots = [
      {
        id: 'city_center',
        name: trip.destinationCity,
        location: { lat: 0, lng: 0 },
      },
    ];
  }

  // Determine stay budget in baseCurrency
  let stayBudget: Money = {
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
    const stayCat = allocations.find((a: any) => a.category === 'stay');
    if (stayCat && stayCat.amount) {
      stayBudget = {
        amountMinor: stayCat.amount.amountMinor,
        currency: stayCat.amount.currency || trip.baseCurrency,
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
    const stayCat = fallback.allocations.find((a) => a.category === 'stay');
    if (stayCat) {
      stayBudget = stayCat.amount;
    }
  }

  const response = await aiClient.searchHotels({
    tripId: trip.id,
    city: trip.destinationCity,
    selectedSpots,
    stayBudget,
    nights,
  });

  // Enrich each hotel option with converted prices in trip.baseCurrency
  const enrichedOptions = await Promise.all(
    response.options.map(async (hotel) => {
      try {
        const { converted, rate } = await fxService.convert(
          hotel.pricePerNight,
          trip.baseCurrency
        );
        const totalPriceMinor = converted.amountMinor * nights;
        return {
          ...hotel,
          convertedPricePerNight: converted,
          totalPrice: {
            amountMinor: totalPriceMinor,
            currency: trip.baseCurrency,
          },
          fxRate: rate,
          isSelected: false,
        };
      } catch (err: any) {
        logger.warn(`Failed to convert hotel price for option ${hotel.providerRef.id}:`, {
          error: err.message,
        });
        const totalPriceMinor = hotel.pricePerNight.amountMinor * nights;
        return {
          ...hotel,
          convertedPricePerNight: hotel.pricePerNight,
          totalPrice: {
            amountMinor: totalPriceMinor,
            currency: hotel.pricePerNight.currency,
          },
          fxRate: 1.0,
          isSelected: false,
        };
      }
    })
  );

  await tripRepository.updateHotelOptions(trip.id, enrichedOptions);
  await jobRepository.updateStatus(jobId, 'completed');
  logger.info(`search-hotels completed with ${enrichedOptions.length} options for trip ${trip.id}`);

  return {
    tripId: trip.id,
    optionsCount: enrichedOptions.length,
    fallbackUsed: response.fallbackUsed,
  };
}
