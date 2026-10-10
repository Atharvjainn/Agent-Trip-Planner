import { env } from '../config/env';
import { BadGatewayError } from '../lib/errors';
import { logger } from '../lib/logger';
import {
  AIRecommendDestinationsRequest,
  AIRecommendDestinationsResponse,
  aiRecommendDestinationsResponseSchema,
} from '../schemas/destination.schema';
import {
  AIDiscoverSpotsRequest,
  AIDiscoverSpotsResponse,
  aiDiscoverSpotsResponseSchema,
} from '../schemas/spot.schema';
import {
  AIBudgetEstimateRequest,
  AIBudgetEstimateResponse,
  aiBudgetEstimateResponseSchema,
} from '../schemas/budget.schema';

import {
  AIFlightSearchRequest,
  AIFlightSearchResponse,
  AIFlightSearchResponseSchema,
} from '../schemas/flight.schema';

import {
  AIHotelSearchRequest,
  AIHotelSearchResponse,
  AIHotelSearchResponseSchema,
} from '../schemas/hotel.schema';

import {
  SavingsSuggestRequest,
  SavingsSuggestResponse,
  savingsSuggestResponseSchema,
} from '../schemas/savings.schema';

import {
  SummaryBuildRequest,
  SummaryBuildResponse,
  summaryBuildResponseSchema,
} from '../schemas/summary.schema';
import {
  AIChatResponse,
  aiChatResponseSchema,
} from '../schemas/chat.schema';

export interface AIChatRequest {
  tripId: string;
  message: string;
  sessionId?: string;
  userId?: string;
  userLocation?: { lat: number; lng: number };
  existingState?: Record<string, any>;
}

class AIClient {
  private baseUrl: string;
  private internalKey: string;
  private timeoutMs: number;

  constructor() {
    this.baseUrl = env.AI_BASE_URL.replace(/\/$/, '');
    this.internalKey = env.AI_INTERNAL_KEY;
    this.timeoutMs = 90_000;
  }

  private async post<T>(endpoint: string, body: unknown): Promise<unknown> {
    const url = `${this.baseUrl}${endpoint}`;
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Internal-Key': this.internalKey,
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(this.timeoutMs),
      });

      if (!res.ok) {
        const errorText = await res.text().catch(() => '');
        logger.error(`AI service error [${res.status}] ${endpoint}: ${errorText}`);
        throw new BadGatewayError(`AI service request failed with status ${res.status}`);
      }

      return await res.json();
    } catch (err: any) {
      if (err instanceof BadGatewayError) throw err;
      logger.error(`Failed to reach AI service at ${url}:`, { error: err.message });
      throw new BadGatewayError(`AI service unreachable: ${err.message}`);
    }
  }

  async recommendDestinations(
    req: AIRecommendDestinationsRequest
  ): Promise<AIRecommendDestinationsResponse> {
    const data = await this.post('/internal/destinations/recommend', req);
    const parsed = aiRecommendDestinationsResponseSchema.safeParse(data);
    if (!parsed.success) {
      logger.error('Invalid schema from /internal/destinations/recommend:', {
        errors: parsed.error.issues,
      });
      throw new BadGatewayError('Invalid response schema from destination recommendation service');
    }
    return parsed.data;
  }

  async discoverSpots(req: AIDiscoverSpotsRequest): Promise<AIDiscoverSpotsResponse> {
    const data = await this.post('/internal/spots/discover', req);
    const parsed = aiDiscoverSpotsResponseSchema.safeParse(data);
    if (!parsed.success) {
      logger.error('Invalid schema from /internal/spots/discover:', {
        errors: parsed.error.issues,
      });
      throw new BadGatewayError('Invalid response schema from spot discovery service');
    }
    return parsed.data;
  }

  async estimateBudget(req: AIBudgetEstimateRequest): Promise<AIBudgetEstimateResponse> {
    const data = await this.post('/internal/budget/estimate', req);
    const parsed = aiBudgetEstimateResponseSchema.safeParse(data);
    if (!parsed.success) {
      logger.error('Invalid schema from /internal/budget/estimate:', {
        errors: parsed.error.issues,
      });
      throw new BadGatewayError('Invalid response schema from budget estimation service');
    }
    return parsed.data;
  }

  async searchFlights(req: AIFlightSearchRequest): Promise<AIFlightSearchResponse> {
    const data = await this.post('/internal/flights/search', req);
    const parsed = AIFlightSearchResponseSchema.safeParse(data);
    if (!parsed.success) {
      logger.error('Invalid schema from /internal/flights/search:', {
        errors: parsed.error.issues,
      });
      throw new BadGatewayError('Invalid response schema from flight search service');
    }
    return parsed.data;
  }

  async searchHotels(req: AIHotelSearchRequest): Promise<AIHotelSearchResponse> {
    const data = await this.post('/internal/hotels/search', req);
    const parsed = AIHotelSearchResponseSchema.safeParse(data);
    if (!parsed.success) {
      logger.error('Invalid schema from /internal/hotels/search:', {
        errors: parsed.error.issues,
      });
      throw new BadGatewayError('Invalid response schema from hotel search service');
    }
    return parsed.data;
  }

  async suggestSavings(req: SavingsSuggestRequest): Promise<SavingsSuggestResponse> {
    const data = await this.post('/internal/savings/suggest', req);
    const parsed = savingsSuggestResponseSchema.safeParse(data);
    if (!parsed.success) {
      logger.error('Invalid schema from /internal/savings/suggest:', {
        errors: parsed.error.issues,
      });
      throw new BadGatewayError('Invalid response schema from savings suggestion service');
    }
    return parsed.data;
  }

  async buildSummary(req: SummaryBuildRequest): Promise<SummaryBuildResponse> {
    const data = await this.post('/internal/summary/build', req);
    const parsed = summaryBuildResponseSchema.safeParse(data);
    if (!parsed.success) {
      logger.error('Invalid schema from /internal/summary/build:', {
        errors: parsed.error.issues,
      });
      throw new BadGatewayError('Invalid response schema from summary build service');
    }
    return parsed.data;
  }

  async chat(req: AIChatRequest): Promise<AIChatResponse> {
    const data = await this.post('/internal/chat', req);
    const parsed = aiChatResponseSchema.safeParse(data);
    if (!parsed.success) {
      logger.error('Invalid schema from /internal/chat:', {
        errors: parsed.error.issues,
      });
      throw new BadGatewayError('Invalid response schema from chat service');
    }
    return parsed.data;
  }
}

export const aiClient = new AIClient();
