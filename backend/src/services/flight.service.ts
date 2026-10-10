import { tripRepository } from '../repositories/trip.repository';
import { selectionRepository } from '../repositories/selection.repository';
import { tripQueue } from '../jobs/queue';
import { jobRepository } from '../repositories/job.repository';
import { fxService } from './fx.service';
import { NotFoundError, ConflictError } from '../lib/errors';
import { FlightOption } from '../schemas/flight.schema';
import { TripStatus } from '@prisma/client';

export class FlightService {
  async triggerFlightSearch(tripId: string, userId: string) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    if (!trip.destinationCity) {
      throw new ConflictError('Cannot search flights without a selected destination');
    }

    const job = await tripQueue.add('search-flights', {
      tripId: trip.id,
      userId,
    });

    if (job.id) {
      await jobRepository.create({
        id: job.id,
        tripId: trip.id,
        userId,
        name: 'search-flights',
      });
    }

    return {
      jobId: job.id,
      status: 'queued',
    };
  }

  async getFlightOptions(tripId: string, userId: string) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    const pendingJob = await jobRepository.findLatestByTripAndName(tripId, 'search-flights');
    const selections = await selectionRepository.findByTripIdAndType(tripId, 'flight');
    const selectedFlight = selections.length > 0 ? selections[0] : null;

    let options: FlightOption[] = [];
    if (trip.flightOptions && Array.isArray(trip.flightOptions)) {
      options = (trip.flightOptions as any[]).map((opt) => ({
        ...opt,
        isSelected: selectedFlight ? opt.providerRef.id === selectedFlight.providerId : false,
      }));
    }

    return {
      tripId: trip.id,
      baseCurrency: trip.baseCurrency,
      options,
      selectedFlight,
      pendingJob:
        pendingJob && ['queued', 'active'].includes(pendingJob.status)
          ? {
              id: pendingJob.id,
              status: pendingJob.status,
            }
          : null,
    };
  }

  async selectFlight(tripId: string, userId: string, flight: FlightOption) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    // Trip must have spots selected or be in flight selection step
    const allowedStatuses: TripStatus[] = [
      TripStatus.SPOTS_SELECTED,
      TripStatus.FLIGHT_SELECTED,
      TripStatus.HOTEL_SELECTED,
      TripStatus.SUMMARY_READY,
    ];
    if (!allowedStatuses.includes(trip.status)) {
      throw new ConflictError('Cannot select flight before spots are selected');
    }

    // Convert money to base currency with FX
    const { converted, rate, fxAt } = await fxService.convert(flight.price, trip.baseCurrency);

    // Save selection in Selection table
    const providerId = flight.providerRef.id || flight.outbound[0]?.flightNumber || 'flight';
    const providerName = flight.outbound[0]?.airline || 'Flight';

    const selection = await selectionRepository.replaceFlightSelection(tripId, {
      tripId,
      type: 'flight',
      providerId,
      providerName,
      originalMoney: flight.price,
      convertedMoney: converted,
      fxRate: rate,
      fxAt,
      deepLink: flight.providerRef.deepLink || null,
      metadata: {
        outbound: flight.outbound,
        inbound: flight.inbound,
        stops: flight.stops,
        totalDurationMinutes: flight.totalDurationMinutes,
      },
    });

    // Update flightOptions on trip with selected flag
    if (trip.flightOptions && Array.isArray(trip.flightOptions)) {
      const updatedOptions = (trip.flightOptions as any[]).map((opt) => ({
        ...opt,
        isSelected: opt.providerRef.id === flight.providerRef.id,
      }));
      await tripRepository.updateFlightOptions(tripId, updatedOptions);
    }

    // Advance status to FLIGHT_SELECTED if currently SPOTS_SELECTED
    if (trip.status === TripStatus.SPOTS_SELECTED) {
      await tripRepository.updateStatus(tripId, TripStatus.FLIGHT_SELECTED);
    }

    // Trigger search-hotels job for the next step
    const hotelJob = await tripQueue.add('search-hotels', {
      tripId: trip.id,
      userId,
    });
    if (hotelJob.id) {
      await jobRepository.create({
        id: hotelJob.id,
        tripId: trip.id,
        userId,
        name: 'search-hotels',
      });
    }

    return {
      success: true,
      selection,
      searchHotelsJobId: hotelJob.id,
      nextStep: `/trips/${tripId}/hotels`,
    };
  }
}

export const flightService = new FlightService();
