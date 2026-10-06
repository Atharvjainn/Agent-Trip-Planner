import { TripStatus } from '@prisma/client';
import crypto from 'node:crypto';
import { CreateTripInput } from '../schemas/trip.schema';
import { tripRepository } from '../repositories/trip.repository';
import { jobRepository } from '../repositories/job.repository';
import { enqueueJob } from '../jobs/queue';
import { NotFoundError } from '../lib/errors';

export class TripService {
  async createTrip(userId: string, input: CreateTripInput) {
    const hasDestination = Boolean(input.destinationCity && input.destinationCountry);
    const initialStatus = hasDestination
      ? TripStatus.DESTINATION_SELECTED
      : TripStatus.DRAFT;
    const initialJobName = hasDestination
      ? 'discover-spots'
      : 'recommend-destinations';

    const trip = await tripRepository.create({
      userId,
      source: input.source,
      destinationCity: input.destinationCity,
      destinationCountry: input.destinationCountry,
      startDate: new Date(input.startDate),
      endDate: new Date(input.endDate),
      travelers: input.travelers,
      vibes: input.vibes,
      budgetTotalMinor: input.budget.amountMinor,
      baseCurrency: input.budget.currency,
      status: initialStatus,
    });

    const jobId = `job_${crypto.randomUUID()}`;

    await jobRepository.create({
      id: jobId,
      tripId: trip.id,
      userId,
      name: initialJobName,
      status: 'queued',
    });

    await enqueueJob(initialJobName, { tripId: trip.id, userId }, jobId);

    return {
      tripId: trip.id,
      jobId,
      status: trip.status,
    };
  }

  async getTripById(id: string, userId: string) {
    const trip = await tripRepository.findByIdAndUser(id, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    const pendingJob = await jobRepository.findLatestPendingByTripId(id, userId);

    return {
      ...trip,
      pendingJob: pendingJob || null,
    };
  }
}

export const tripService = new TripService();
