import { TripStatus } from '@prisma/client';
import { tripRepository } from '../repositories/trip.repository';
import { selectionRepository } from '../repositories/selection.repository';
import { tripQueue } from '../jobs/queue';
import { jobRepository } from '../repositories/job.repository';
import { NotFoundError, ConflictError } from '../lib/errors';
import { SelectSpotsInput, SpotOption } from '../schemas/spot.schema';

export class SpotService {
  async selectSpots(tripId: string, userId: string, input: SelectSpotsInput) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    // Require BUDGET_ESTIMATED or DESTINATION_SELECTED or SPOTS_SELECTED
    const allowedStatuses: TripStatus[] = [
      TripStatus.DESTINATION_SELECTED,
      TripStatus.BUDGET_ESTIMATED,
      TripStatus.SPOTS_SELECTED,
      TripStatus.FLIGHT_SELECTED,
      TripStatus.HOTEL_SELECTED,
    ];

    if (!allowedStatuses.includes(trip.status)) {
      throw new ConflictError(
        `Cannot select spots when trip status is ${trip.status}. Expected BUDGET_ESTIMATED.`
      );
    }

    if (!trip.spotOptions || !Array.isArray(trip.spotOptions)) {
      throw new ConflictError('No spot options available for selection');
    }

    const availableSpots = trip.spotOptions as unknown as SpotOption[];
    const availableSpotIds = new Set(
      availableSpots.map((s) => s.providerRef.id || s.name)
    );

    const invalidSpotIds = input.spotIds.filter((id) => !availableSpotIds.has(id));
    if (invalidSpotIds.length > 0) {
      throw new ConflictError(
        `Invalid spot selections: ${invalidSpotIds.join(', ')} not in discovered spots`
      );
    }

    // Update spotOptions with isSelected flag
    const selectedSpots: SpotOption[] = [];
    const updatedSpotOptions = availableSpots.map((s) => {
      const id = s.providerRef.id || s.name;
      const isSelected = input.spotIds.includes(id);
      if (isSelected) {
        selectedSpots.push(s);
      }
      return {
        ...s,
        isSelected,
      };
    });

    await tripRepository.updateSpotOptions(trip.id, updatedSpotOptions);
    if (trip.status === TripStatus.DESTINATION_SELECTED || trip.status === TripStatus.BUDGET_ESTIMATED) {
      await tripRepository.updateStatus(trip.id, TripStatus.SPOTS_SELECTED);
    }

    // Persist spot selections into Selection table
    await selectionRepository.replaceSpotSelections(
      trip.id,
      selectedSpots.map((s) => ({
        tripId: trip.id,
        type: 'spot',
        providerId: s.providerRef.id || s.name,
        providerName: s.name,
        originalMoney: { amountMinor: 0, currency: trip.baseCurrency },
        convertedMoney: { amountMinor: 0, currency: trip.baseCurrency },
        fxRate: 1.0,
        fxAt: new Date(),
        deepLink: s.providerRef.deepLink || null,
        metadata: {
          location: s.location,
          rating: s.rating,
          vibeScores: s.vibeScores,
          matchingEvent: s.matchingEvent,
        },
      }))
    );

    // Trigger flight search job for the next step
    const flightJob = await tripQueue.add('search-flights', {
      tripId: trip.id,
      userId,
    });
    if (flightJob.id) {
      await jobRepository.create({
        id: flightJob.id,
        tripId: trip.id,
        userId,
        name: 'search-flights',
      });
    }

    return {
      tripId: trip.id,
      status: TripStatus.SPOTS_SELECTED,
      selectedCount: input.spotIds.length,
      searchFlightsJobId: flightJob.id,
    };
  }
}

export const spotService = new SpotService();

