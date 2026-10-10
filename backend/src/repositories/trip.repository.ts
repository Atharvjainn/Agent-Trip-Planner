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
      include: {
        selections: true,
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

  async updateBudgetAllocation(id: string, budgetAllocation: any) {
    return prisma.trip.update({
      where: { id },
      data: {
        budgetAllocation,
      } as any,
    });
  }

  async updateFlightOptions(id: string, flightOptions: any) {
    return prisma.trip.update({
      where: { id },
      data: {
        flightOptions,
      } as any,
    });
  }

  async updateHotelOptions(id: string, hotelOptions: any) {
    return prisma.trip.update({
      where: { id },
      data: {
        hotelOptions,
      } as any,
    });
  }

  async updateSavingSuggestions(id: string, savingSuggestions: any) {
    return prisma.trip.update({
      where: { id },
      data: {
        savingSuggestions,
      } as any,
    });
  }

  async updateSummary(id: string, summary: any, status: TripStatus = TripStatus.SUMMARY_READY) {
    return prisma.trip.update({
      where: { id },
      data: {
        summary,
        status,
      } as any,
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
