import { TripStatus } from '@prisma/client';
import { tripRepository } from '../repositories/trip.repository';
import { NotFoundError, ConflictError } from '../lib/errors';
import { SelectSpotsInput, SpotOption } from '../schemas/spot.schema';

export class SpotService {
  async selectSpots(tripId: string, userId: string, input: SelectSpotsInput) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    // Require BUDGET_ESTIMATED or DESTINATION_SELECTED
    const allowedStatuses: TripStatus[] = [
      TripStatus.DESTINATION_SELECTED,
      TripStatus.BUDGET_ESTIMATED,
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
    const updatedSpotOptions = availableSpots.map((s) => {
      const id = s.providerRef.id || s.name;
      return {
        ...s,
        isSelected: input.spotIds.includes(id),
      };
    });

    await tripRepository.updateSpotOptions(trip.id, updatedSpotOptions);
    await tripRepository.updateStatus(trip.id, TripStatus.SPOTS_SELECTED);

    return {
      tripId: trip.id,
      status: TripStatus.SPOTS_SELECTED,
      selectedCount: input.spotIds.length,
    };
  }
}

export const spotService = new SpotService();
