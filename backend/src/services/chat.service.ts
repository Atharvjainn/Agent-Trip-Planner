import { TripStatus, Trip, Selection } from '@prisma/client';
import { aiClient } from '../clients/ai.client';
import { tripRepository } from '../repositories/trip.repository';
import { selectionRepository } from '../repositories/selection.repository';
import { NotFoundError } from '../lib/errors';
import { logger } from '../lib/logger';
import { AIChatResponse } from '../schemas/chat.schema';
import { prisma } from '../lib/prisma';

type TripWithSelections = Trip & { selections: Selection[] };

export class ChatService {
  async handleMessage(
    userId: string,
    message: string,
    tripId?: string,
    sessionId?: string,
    userLocation?: { lat: number; lng: number }
  ): Promise<{
    tripId: string;
    sessionId: string;
    conversationStage: string;
    tripStatus: string;
    turnResponse: AIChatResponse['turnResponse'];
    stateSummary: Record<string, any>;
    metrics?: AIChatResponse['metrics'];
  }> {
    let trip: TripWithSelections | null = tripId
      ? await tripRepository.findByIdAndUser(tripId, userId)
      : null;

    if (tripId && !trip) {
      throw new NotFoundError('Trip not found');
    }

    if (!trip) {
      const now = new Date();
      const in7Days = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
      const in10Days = new Date(now.getTime() + 10 * 24 * 60 * 60 * 1000);

      const created = await tripRepository.create({
        userId,
        source: 'Unknown',
        startDate: in7Days,
        endDate: in10Days,
        travelers: 1,
        vibes: [],
        budgetTotalMinor: 0,
        baseCurrency: 'INR',
        status: TripStatus.DRAFT,
      });

      trip = {
        ...created,
        selections: [],
      };
    }

    const currentTrip = trip;

    // Build existing state from trip
    const confirmedSpots =
      currentTrip.selections
        ?.filter((s) => s.type === 'spot')
        .map((s) => ({
          place_id: s.providerId,
          name: s.providerName || '',
          ...((s.metadata as Record<string, any>) || {}),
        })) || [];

    const hotelSel = currentTrip.selections?.find((s) => s.type === 'hotel');
    const confirmedHotel = hotelSel
      ? {
          place_id: hotelSel.providerId,
          name: hotelSel.providerName,
          ...((hotelSel.metadata as Record<string, any>) || {}),
        }
      : null;

    const flightSel = currentTrip.selections?.find((s) => s.type === 'flight');
    const confirmedFlight = flightSel
      ? {
          ...((flightSel.metadata as Record<string, any>) || {}),
        }
      : null;

    const existingState: Record<string, any> = {
      destinationCity: currentTrip.destinationCity || null,
      departureCity: currentTrip.source !== 'Unknown' ? currentTrip.source : null,
      vibe: currentTrip.vibes?.[0] || null,
      budgetTotal:
        currentTrip.budgetTotalMinor > 0
          ? { amountMinor: currentTrip.budgetTotalMinor, currency: currentTrip.baseCurrency }
          : null,
      currency: currentTrip.baseCurrency || 'INR',
      durationDays: Math.max(
        1,
        Math.round((currentTrip.endDate.getTime() - currentTrip.startDate.getTime()) / (1000 * 60 * 60 * 24))
      ),
      confirmedAttractions: confirmedSpots,
      confirmedHotel: confirmedHotel,
      confirmedFlight: confirmedFlight,
      budgetAllocation: currentTrip.budgetAllocation || null,
      itinerary: (currentTrip.summary as any)?.itinerary || [],
    };

    const aiRes = await aiClient.chat({
      tripId: currentTrip.id,
      message,
      sessionId: sessionId || currentTrip.id,
      userId,
      userLocation,
      existingState,
    });

    // Synchronize AI state back to Postgres
    try {
      await this.syncAiStateToTrip(currentTrip.id, aiRes, currentTrip);
    } catch (err: any) {
      logger.error('Failed to sync AI chat state to Trip in DB:', { error: err.message });
    }

    return {
      tripId: currentTrip.id,
      sessionId: aiRes.sessionId,
      conversationStage: aiRes.conversationStage,
      tripStatus: aiRes.tripStatus,
      turnResponse: aiRes.turnResponse,
      stateSummary: aiRes.stateSummary,
      metrics: aiRes.metrics,
    };
  }

  private async syncAiStateToTrip(tripId: string, aiRes: AIChatResponse, currentTrip: Trip) {
    const summary = aiRes.stateSummary || {};
    const updates: Record<string, any> = {};

    if (summary.destinationCity && summary.destinationCity !== currentTrip.destinationCity) {
      updates.destinationCity = summary.destinationCity;
    }

    if (summary.departureCity && currentTrip.source === 'Unknown') {
      updates.source = summary.departureCity;
    }

    if (summary.vibe && (!currentTrip.vibes || currentTrip.vibes.length === 0)) {
      updates.vibes = [summary.vibe];
    }

    if (summary.budgetTotal && typeof summary.budgetTotal === 'object') {
      const budgetObj = summary.budgetTotal as Record<string, any>;
      const amt = budgetObj.amountMinor;
      const curr = budgetObj.currency;
      if (typeof amt === 'number' && amt > 0) {
        updates.budgetTotalMinor = amt;
      }
      if (typeof curr === 'string' && curr) {
        updates.baseCurrency = curr;
      }
    }

    if (typeof summary.durationDays === 'number' && summary.durationDays > 0) {
      const start = currentTrip.startDate ? new Date(currentTrip.startDate) : new Date();
      updates.endDate = new Date(start.getTime() + summary.durationDays * 24 * 60 * 60 * 1000);
    }

    if (summary.budgetAllocation) {
      updates.budgetAllocation = summary.budgetAllocation;
    }

    if (summary.itinerary && Array.isArray(summary.itinerary) && summary.itinerary.length > 0) {
      updates.summary = {
        ...(typeof currentTrip.summary === 'object' && currentTrip.summary ? currentTrip.summary : {}),
        itinerary: summary.itinerary,
      };
    }

    // Save options to trip if returned
    if (aiRes.turnResponse.uiComponent === 'destination_options' && aiRes.turnResponse.options.length > 0) {
      updates.destinationOptions = aiRes.turnResponse.options;
    } else if (
      aiRes.turnResponse.uiComponent === 'attraction_options' &&
      aiRes.turnResponse.options.length > 0
    ) {
      updates.spotOptions = aiRes.turnResponse.options;
    } else if (aiRes.turnResponse.uiComponent === 'hotel_options' && aiRes.turnResponse.options.length > 0) {
      updates.hotelOptions = aiRes.turnResponse.options;
    } else if (aiRes.turnResponse.uiComponent === 'flight_options' && aiRes.turnResponse.options.length > 0) {
      updates.flightOptions = aiRes.turnResponse.options;
    }

    // Map canonical tripStatus
    const validStatuses: Record<string, TripStatus> = {
      DRAFT: TripStatus.DRAFT,
      DESTINATION_SELECTED: TripStatus.DESTINATION_SELECTED,
      BUDGET_ESTIMATED: TripStatus.BUDGET_ESTIMATED,
      SPOTS_SELECTED: TripStatus.SPOTS_SELECTED,
      FLIGHT_SELECTED: TripStatus.FLIGHT_SELECTED,
      HOTEL_SELECTED: TripStatus.HOTEL_SELECTED,
      SUMMARY_READY: TripStatus.SUMMARY_READY,
    };

    if (aiRes.tripStatus && validStatuses[aiRes.tripStatus]) {
      updates.status = validStatuses[aiRes.tripStatus];
    }

    if (Object.keys(updates).length > 0) {
      await prisma.trip.update({
        where: { id: tripId },
        data: updates,
      });
    }

    // Handle selections
    const currency = updates.baseCurrency || currentTrip.baseCurrency || 'INR';

    // Attractions
    if (Array.isArray(summary.confirmedAttractions) && summary.confirmedAttractions.length > 0) {
      const spotSelections = summary.confirmedAttractions.map((spot: any) => ({
        tripId,
        type: 'spot' as const,
        providerId: spot.place_id || spot.placeId || spot.name || 'spot',
        providerName: spot.name || null,
        originalMoney: { amountMinor: 0, currency },
        convertedMoney: { amountMinor: 0, currency },
        metadata: spot,
      }));
      await selectionRepository.replaceSpotSelections(tripId, spotSelections);
    }

    // Hotel
    if (summary.confirmedHotel && typeof summary.confirmedHotel === 'object') {
      const hotel = summary.confirmedHotel as Record<string, any>;
      const hotelPrice =
        hotel.price ||
        hotel.totalPrice ||
        hotel.rate_per_night ||
        { amountMinor: 0, currency };
      await selectionRepository.replaceHotelSelection(tripId, {
        tripId,
        type: 'hotel',
        providerId: hotel.place_id || hotel.name || 'hotel',
        providerName: hotel.name || null,
        originalMoney: hotelPrice,
        convertedMoney: hotelPrice,
        metadata: hotel,
      });
    }

    // Flight
    if (summary.confirmedFlight && typeof summary.confirmedFlight === 'object') {
      const flight = summary.confirmedFlight as Record<string, any>;
      const flightPrice = flight.price || { amountMinor: 0, currency };
      await selectionRepository.replaceFlightSelection(tripId, {
        tripId,
        type: 'flight',
        providerId: flight.flight_number || flight.airline || 'flight',
        providerName: flight.airline || null,
        originalMoney: flightPrice,
        convertedMoney: flightPrice,
        metadata: flight,
      });
    }
  }
}

export const chatService = new ChatService();
