import { TripStatus } from '@prisma/client';
import { prisma } from '../lib/prisma';

export interface CreateTripDto {
  userId: string;
  source: string;
  destinationCity?: string;
  destinationCountry?: string;
  startDate: Date;
  endDate: Date;
  travelers: number;
  vibes: string[];
  budgetTotalMinor: number;
  baseCurrency: string;
  status: TripStatus;
}

export class TripRepository {
  async create(data: CreateTripDto) {
    return prisma.trip.create({
      data: {
        userId: data.userId,
        source: data.source,
        destinationCity: data.destinationCity,
        destinationCountry: data.destinationCountry,
        startDate: data.startDate,
        endDate: data.endDate,
        travelers: data.travelers,
        vibes: data.vibes,
        budgetTotalMinor: data.budgetTotalMinor,
        baseCurrency: data.baseCurrency,
        status: data.status,
      },
    });
  }

  async findByIdAndUser(id: string, userId: string) {
    return prisma.trip.findFirst({
      where: {
        id,
        userId,
      },
    });
  }

  async updateDestination(
    id: string,
    city: string,
    country: string,
    status: TripStatus = TripStatus.DESTINATION_SELECTED
  ) {
    return prisma.trip.update({
      where: { id },
      data: {
        destinationCity: city,
        destinationCountry: country,
        status,
      },
    });
  }

  async updateDestinationOptions(id: string, destinationOptions: any) {
    return prisma.trip.update({
      where: { id },
      data: {
        destinationOptions,
      },
    });
  }

  async updateSpotOptions(id: string, spotOptions: any) {
    return prisma.trip.update({
      where: { id },
      data: {
        spotOptions,
      },
    });
  }

  async updateStatus(id: string, status: TripStatus) {
    return prisma.trip.update({
      where: { id },
      data: {
        status,
      },
    });
  }
}

export const tripRepository = new TripRepository();
