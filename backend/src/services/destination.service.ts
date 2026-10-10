import { TripStatus } from '@prisma/client';
import crypto from 'node:crypto';
import { SelectDestinationInput, DestinationOption } from '../schemas/destination.schema';
import { tripRepository } from '../repositories/trip.repository';
import { jobRepository } from '../repositories/job.repository';
import { enqueueJob } from '../jobs/queue';
import { NotFoundError, ConflictError } from '../lib/errors';

export class DestinationService {
  async selectDestination(tripId: string, userId: string, input: SelectDestinationInput) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    if (trip.status !== TripStatus.DRAFT) {
      throw new ConflictError(`Cannot select destination when trip status is ${trip.status}`);
    }

    if (!trip.destinationOptions || !Array.isArray(trip.destinationOptions)) {
      throw new ConflictError('No destination options available to select from');
    }

    const options = trip.destinationOptions as unknown as DestinationOption[];
    const isValidOption = options.some(
      (opt) =>
        opt.city.toLowerCase() === input.city.toLowerCase() &&
        opt.country.toLowerCase() === input.country.toLowerCase()
    );

    if (!isValidOption) {
      throw new ConflictError('Selected destination is not among recommended options');
    }

    await tripRepository.updateDestination(
      trip.id,
      input.city,
      input.country,
      TripStatus.DESTINATION_SELECTED
    );

    // Enqueue estimate-budget
    const budgetJobId = `job_${crypto.randomUUID()}`;
    await jobRepository.create({
      id: budgetJobId,
      tripId: trip.id,
      userId,
      name: 'estimate-budget',
      status: 'queued',
    });
    await enqueueJob('estimate-budget', { tripId: trip.id, userId }, budgetJobId);

    // Enqueue discover-spots
    const spotsJobId = `job_${crypto.randomUUID()}`;
    await jobRepository.create({
      id: spotsJobId,
      tripId: trip.id,
      userId,
      name: 'discover-spots',
      status: 'queued',
    });
    await enqueueJob('discover-spots', { tripId: trip.id, userId }, spotsJobId);

    return {
      jobId: spotsJobId,
    };
  }
}

export const destinationService = new DestinationService();
