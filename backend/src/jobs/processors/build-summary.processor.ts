import { Job } from 'bullmq';
import { TripJobPayload } from '../queue';
import { tripRepository } from '../../repositories/trip.repository';
import { selectionRepository } from '../../repositories/selection.repository';
import { jobRepository } from '../../repositories/job.repository';
import { aiClient } from '../../clients/ai.client';
import { fxService } from '../../services/fx.service';
import { logger } from '../../lib/logger';
import { TripStatus } from '@prisma/client';
import { Money, GeoPoint } from '../../schemas/common.schema';
import { SelectedSpotInput } from '../../schemas/hotel.schema';

export async function processBuildSummary(job: Job<TripJobPayload>) {
  const { tripId, userId } = job.data;
  const jobId = job.id!;
  logger.info(`Starting build-summary job ${jobId} for trip ${tripId}`);
  await jobRepository.updateStatus(jobId, 'active');

  const trip = await tripRepository.findByIdAndUser(tripId, userId);
  if (!trip) {
    throw new Error(`Trip ${tripId} not found`);
  }

  const city = trip.destinationCity || 'Destination';

  // Calculate nights
  const startMs = new Date(trip.startDate).getTime();
  const endMs = new Date(trip.endDate).getTime();
  const nights = Math.max(1, Math.round((endMs - startMs) / (1000 * 60 * 60 * 24)));

  // 1. Gather Hotel Selection
  const hotelSelections = await selectionRepository.findByTripIdAndType(tripId, 'hotel');
  let hotelLocation: GeoPoint = { lat: 28.6139, lng: 77.2090 };
  let hotelTotalPrice: Money = {
    amountMinor: Math.floor(trip.budgetTotalMinor * 0.35),
    currency: trip.baseCurrency,
  };

  if (hotelSelections.length > 0) {
    const sel = hotelSelections[0];
    hotelTotalPrice = sel.convertedMoney as any;
    const meta = sel.metadata as any;
    if (meta?.location?.lat && meta?.location?.lng) {
      hotelLocation = {
        lat: Number(meta.location.lat),
        lng: Number(meta.location.lng),
      };
    }
  } else if (trip.hotelOptions && Array.isArray(trip.hotelOptions) && (trip.hotelOptions as any[]).length > 0) {
    const firstHotel = (trip.hotelOptions as any[])[0];
    hotelLocation = {
      lat: Number(firstHotel.location?.lat || 28.6139),
      lng: Number(firstHotel.location?.lng || 77.2090),
    };
    hotelTotalPrice = firstHotel.totalPrice || {
      amountMinor: Math.floor(trip.budgetTotalMinor * 0.35),
      currency: trip.baseCurrency,
    };
  }

  // 2. Gather Flight Selection
  const flightSelections = await selectionRepository.findByTripIdAndType(tripId, 'flight');
  let flightPrice: Money = {
    amountMinor: Math.floor(trip.budgetTotalMinor * 0.35),
    currency: trip.baseCurrency,
  };

  if (flightSelections.length > 0) {
    flightPrice = flightSelections[0].convertedMoney as any;
  } else if (trip.flightOptions && Array.isArray(trip.flightOptions) && (trip.flightOptions as any[]).length > 0) {
    const firstFlight = (trip.flightOptions as any[])[0];
    flightPrice = firstFlight.convertedPrice || firstFlight.price;
  }

  // 3. Gather Spot Selections
  const spotSelections = await selectionRepository.findByTripIdAndType(tripId, 'spot');
  let selectedSpots: SelectedSpotInput[] = [];

  if (spotSelections.length > 0) {
    selectedSpots = spotSelections.map((sel) => {
      const meta = sel.metadata as any;
      return {
        id: sel.providerId,
        name: sel.providerName || sel.providerId,
        location: meta?.location || { lat: hotelLocation.lat + 0.02, lng: hotelLocation.lng + 0.02 },
      };
    });
  } else if (trip.spotOptions && Array.isArray(trip.spotOptions)) {
    const spots = trip.spotOptions as any[];
    const chosen = spots.filter((s) => s.isSelected);
    const pool = chosen.length > 0 ? chosen : spots.slice(0, 5);
    selectedSpots = pool.map((s) => ({
      id: s.providerRef?.id || s.name,
      name: s.name,
      location: s.location || { lat: hotelLocation.lat + 0.02, lng: hotelLocation.lng + 0.02 },
    }));
  }

  if (selectedSpots.length === 0) {
    selectedSpots = [
      {
        id: 'spot-center',
        name: `${city} Central`,
        location: hotelLocation,
      },
    ];
  }

  // 4. Request summary & commute from AI service
  const aiResponse = await aiClient.buildSummary({
    tripId: trip.id,
    city,
    hotelLocation,
    selectedSpots,
    flightPrice,
    hotelTotalPrice,
    nights,
  });

  // 5. Convert Commute estimate costs to baseCurrency if needed
  let convertedCommute = aiResponse.commute;
  try {
    if (aiResponse.commute.tripTotalCost.currency.toUpperCase() !== trip.baseCurrency.toUpperCase()) {
      const { converted: totalConv } = await fxService.convert(aiResponse.commute.tripTotalCost, trip.baseCurrency);
      const { converted: dailyConv } = await fxService.convert(aiResponse.commute.dailyCost, trip.baseCurrency);
      convertedCommute = {
        ...aiResponse.commute,
        dailyCost: dailyConv,
        tripTotalCost: totalConv,
      };
    }
  } catch (err: any) {
    logger.warn(`Could not convert commute currency to ${trip.baseCurrency}:`, { error: err.message });
  }

  const summaryData = {
    narrative: aiResponse.narrative,
    commute: convertedCommute,
    fallbackUsed: aiResponse.fallbackUsed,
    hotelLocation,
    spotsCount: selectedSpots.length,
    nights,
    generatedAt: new Date().toISOString(),
  };

  await tripRepository.updateSummary(trip.id, summaryData, TripStatus.SUMMARY_READY);
  await jobRepository.updateStatus(jobId, 'completed');
  logger.info(`build-summary completed successfully for trip ${trip.id}`);

  return {
    tripId: trip.id,
    success: true,
    summary: summaryData,
  };
}
