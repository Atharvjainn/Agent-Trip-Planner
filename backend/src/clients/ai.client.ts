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

class AIClient {
  private baseUrl: string;
  private internalKey: string;
  private timeoutMs: number;

  constructor() {
    this.baseUrl = env.AI_BASE_URL.replace(/\/$/, '');
    this.internalKey = env.AI_INTERNAL_KEY;
    this.timeoutMs = 45_000;
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
}

export const aiClient = new AIClient();
