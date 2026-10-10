import { tripRepository } from '../repositories/trip.repository';
import { selectionRepository } from '../repositories/selection.repository';
import { tripQueue } from '../jobs/queue';
import { jobRepository } from '../repositories/job.repository';
import { fxService } from './fx.service';
import { NotFoundError, ConflictError } from '../lib/errors';
import { HotelOption } from '../schemas/hotel.schema';
import { TripStatus } from '@prisma/client';

export class HotelService {
  async triggerHotelSearch(tripId: string, userId: string) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    if (!trip.destinationCity) {
      throw new ConflictError('Cannot search hotels without a selected destination');
    }

    const job = await tripQueue.add('search-hotels', {
      tripId: trip.id,
      userId,
    });

    if (job.id) {
      await jobRepository.create({
        id: job.id,
        tripId: trip.id,
        userId,
        name: 'search-hotels',
      });
    }

    return {
      jobId: job.id,
      status: 'queued',
    };
  }

  async getHotelOptions(tripId: string, userId: string) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    const pendingJob = await jobRepository.findLatestByTripAndName(tripId, 'search-hotels');
    const selections = await selectionRepository.findByTripIdAndType(tripId, 'hotel');
    const selectedHotel = selections.length > 0 ? selections[0] : null;

    const startMs = new Date(trip.startDate).getTime();
    const endMs = new Date(trip.endDate).getTime();
    const nights = Math.max(1, Math.round((endMs - startMs) / (1000 * 60 * 60 * 24)));

    let options: HotelOption[] = [];
    if (trip.hotelOptions && Array.isArray(trip.hotelOptions)) {
      options = (trip.hotelOptions as any[]).map((opt) => ({
        ...opt,
        isSelected: selectedHotel ? opt.providerRef.id === selectedHotel.providerId : false,
      }));
    }

    // Extract stay budget
    let stayBudgetMinor = Math.floor(trip.budgetTotalMinor * 0.35);
    const rawAllocation = (trip as any).budgetAllocation;
    if (rawAllocation && typeof rawAllocation === 'object') {
      const allocations = Array.isArray(rawAllocation.allocations)
        ? rawAllocation.allocations
        : Array.isArray(rawAllocation)
        ? rawAllocation
        : [];
      const stayCat = allocations.find((a: any) => a.category === 'stay');
      if (stayCat && stayCat.amount) {
        stayBudgetMinor = stayCat.amount.amountMinor;
      }
    }

    return {
      tripId: trip.id,
      baseCurrency: trip.baseCurrency,
      nights,
      stayBudgetMinor,
      options,
      selectedHotel,
      pendingJob:
        pendingJob && ['queued', 'active'].includes(pendingJob.status)
          ? {
              id: pendingJob.id,
              status: pendingJob.status,
            }
          : null,
    };
  }

  async selectHotel(tripId: string, userId: string, hotel: HotelOption) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    const allowedStatuses: TripStatus[] = [
      TripStatus.FLIGHT_SELECTED,
      TripStatus.HOTEL_SELECTED,
      TripStatus.SUMMARY_READY,
    ];
    if (!allowedStatuses.includes(trip.status)) {
      throw new ConflictError('Cannot select hotel before flight is selected');
    }

    const startMs = new Date(trip.startDate).getTime();
    const endMs = new Date(trip.endDate).getTime();
    const nights = Math.max(1, Math.round((endMs - startMs) / (1000 * 60 * 60 * 24)));

    // Convert price to base currency with FX
    const { converted, rate, fxAt } = await fxService.convert(
      hotel.pricePerNight,
      trip.baseCurrency
    );

    const totalStayMinor = converted.amountMinor * nights;
    const providerId = hotel.providerRef.id || hotel.name;

    const selection = await selectionRepository.replaceHotelSelection(tripId, {
      tripId,
      type: 'hotel',
      providerId,
      providerName: hotel.name,
      originalMoney: {
        amountMinor: hotel.pricePerNight.amountMinor * nights,
        currency: hotel.pricePerNight.currency,
      },
      convertedMoney: {
        amountMinor: totalStayMinor,
        currency: trip.baseCurrency,
      },
      fxRate: rate,
      fxAt,
      deepLink: hotel.providerRef.deepLink || null,
      metadata: {
        pricePerNightOriginal: hotel.pricePerNight,
        pricePerNightConverted: converted,
        nights,
        location: hotel.location,
        rating: hotel.rating,
        reviewSnippet: hotel.reviewSnippet,
        distances: hotel.distances,
        score: hotel.score,
      },
    });

    // Update hotelOptions on trip with isSelected flag
    if (trip.hotelOptions && Array.isArray(trip.hotelOptions)) {
      const updatedOptions = (trip.hotelOptions as any[]).map((opt) => ({
        ...opt,
        isSelected: opt.providerRef.id === hotel.providerRef.id,
      }));
      await tripRepository.updateHotelOptions(tripId, updatedOptions);
    }

    // Advance status to HOTEL_SELECTED if currently FLIGHT_SELECTED
    if (trip.status === TripStatus.FLIGHT_SELECTED) {
      await tripRepository.updateStatus(tripId, TripStatus.HOTEL_SELECTED);
    }

    // Trigger suggest-savings job
    const savingsJob = await tripQueue.add('suggest-savings', { tripId, userId });
    if (savingsJob.id) {
      await jobRepository.create({
        id: savingsJob.id,
        tripId: trip.id,
        userId,
        name: 'suggest-savings',
      });
    }

    // Trigger build-summary job for final itinerary
    const summaryJob = await tripQueue.add('build-summary', { tripId, userId });
    if (summaryJob.id) {
      await jobRepository.create({
        id: summaryJob.id,
        tripId: trip.id,
        userId,
        name: 'build-summary',
      });
    }

    return {
      success: true,
      selection,
      buildSummaryJobId: summaryJob.id,
      nextStep: `/trips/${tripId}/summary?jobId=${summaryJob.id}`,
    };
  }

  async updateStayBudget(tripId: string, userId: string, stayBudgetMinor: number) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    const rawAllocation = (trip as any).budgetAllocation;
    if (!rawAllocation || typeof rawAllocation !== 'object') {
      throw new ConflictError('No budget allocation found for this trip');
    }

    const allocations = Array.isArray(rawAllocation.allocations)
      ? [...rawAllocation.allocations]
      : [];

    const stayIndex = allocations.findIndex((a: any) => a.category === 'stay');
    if (stayIndex === -1) {
      throw new ConflictError('Stay category not found in budget allocation');
    }

    const oldStayMinor = allocations[stayIndex].amount.amountMinor;
    const diff = stayBudgetMinor - oldStayMinor;

    // Update stay allocation
    allocations[stayIndex] = {
      ...allocations[stayIndex],
      amount: {
        amountMinor: stayBudgetMinor,
        currency: trip.baseCurrency,
      },
    };

    // Compensate the difference in the buffer / activities category
    const bufferIndex = allocations.findIndex((a: any) => a.category === 'buffer');
    if (bufferIndex !== -1) {
      const currentBuffer = allocations[bufferIndex].amount.amountMinor;
      const newBuffer = Math.max(0, currentBuffer - diff);
      allocations[bufferIndex] = {
        ...allocations[bufferIndex],
        amount: {
          amountMinor: newBuffer,
          currency: trip.baseCurrency,
        },
      };
    }

    const updatedAllocation = {
      ...rawAllocation,
      allocations,
    };

    await tripRepository.updateBudgetAllocation(tripId, updatedAllocation);

    return {
      tripId: trip.id,
      stayBudgetMinor,
      budgetAllocation: updatedAllocation,
    };
  }
}

export const hotelService = new HotelService();
