import { prisma } from '../lib/prisma';
import { SelectionType } from '@prisma/client';
import { Money } from '../schemas/common.schema';

export interface CreateSelectionParams {
  tripId: string;
  type: SelectionType;
  providerId: string;
  providerName?: string | null;
  originalMoney: Money;
  convertedMoney: Money;
  fxRate?: number;
  fxAt?: Date;
  deepLink?: string | null;
  metadata?: any;
}

export class SelectionRepository {
  async create(data: CreateSelectionParams) {
    return prisma.selection.create({
      data: {
        tripId: data.tripId,
        type: data.type,
        providerId: data.providerId,
        providerName: data.providerName || null,
        originalMoney: data.originalMoney as any,
        convertedMoney: data.convertedMoney as any,
        fxRate: data.fxRate ?? 1.0,
        fxAt: data.fxAt ?? new Date(),
        deepLink: data.deepLink || null,
        metadata: data.metadata || null,
      },
    });
  }

  async findByTripId(tripId: string) {
    return prisma.selection.findMany({
      where: { tripId },
      orderBy: { createdAt: 'asc' },
    });
  }

  async findByTripIdAndType(tripId: string, type: SelectionType) {
    return prisma.selection.findMany({
      where: { tripId, type },
      orderBy: { createdAt: 'asc' },
    });
  }

  async deleteByTripIdAndType(tripId: string, type: SelectionType) {
    return prisma.selection.deleteMany({
      where: { tripId, type },
    });
  }

  /**
   * Replaces the flight selection for a trip atomically.
   */
  async replaceFlightSelection(tripId: string, data: CreateSelectionParams) {
    return prisma.$transaction(async (tx) => {
      await tx.selection.deleteMany({
        where: { tripId, type: 'flight' },
      });
      return tx.selection.create({
        data: {
          tripId: data.tripId,
          type: 'flight',
          providerId: data.providerId,
          providerName: data.providerName || null,
          originalMoney: data.originalMoney as any,
          convertedMoney: data.convertedMoney as any,
          fxRate: data.fxRate ?? 1.0,
          fxAt: data.fxAt ?? new Date(),
          deepLink: data.deepLink || null,
          metadata: data.metadata || null,
        },
      });
    });
  }

  /**
   * Replaces spot selections for a trip atomically.
   */
  async replaceSpotSelections(tripId: string, items: CreateSelectionParams[]) {
    return prisma.$transaction(async (tx) => {
      await tx.selection.deleteMany({
        where: { tripId, type: 'spot' },
      });
      if (items.length === 0) return [];
      return Promise.all(
        items.map((item) =>
          tx.selection.create({
            data: {
              tripId: item.tripId,
              type: 'spot',
              providerId: item.providerId,
              providerName: item.providerName || null,
              originalMoney: item.originalMoney as any,
              convertedMoney: item.convertedMoney as any,
              fxRate: item.fxRate ?? 1.0,
              fxAt: item.fxAt ?? new Date(),
              deepLink: item.deepLink || null,
              metadata: item.metadata || null,
            },
          })
        )
      );
    });
  }

  /**
   * Replaces the hotel selection for a trip atomically.
   */
  async replaceHotelSelection(tripId: string, data: CreateSelectionParams) {
    return prisma.$transaction(async (tx) => {
      await tx.selection.deleteMany({
        where: { tripId, type: 'hotel' },
      });
      return tx.selection.create({
        data: {
          tripId: data.tripId,
          type: 'hotel',
          providerId: data.providerId,
          providerName: data.providerName || null,
          originalMoney: data.originalMoney as any,
          convertedMoney: data.convertedMoney as any,
          fxRate: data.fxRate ?? 1.0,
          fxAt: data.fxAt ?? new Date(),
          deepLink: data.deepLink || null,
          metadata: data.metadata || null,
        },
      });
    });
  }
}

export const selectionRepository = new SelectionRepository();

