import { redisClient } from '../lib/redis';
import { logger } from '../lib/logger';
import { Money } from '../schemas/common.schema';

const FX_CACHE_TTL_SECONDS = 12 * 60 * 60; // 12 hours

// Static fallback rates (against USD) in case network is down during demo/offline
const FALLBACK_RATES_TO_USD: Record<string, number> = {
  USD: 1.0,
  INR: 0.012, // 1 INR = 0.012 USD (~83 INR/USD)
  EUR: 1.08,
  GBP: 1.28,
  JPY: 0.0067,
  AUD: 0.65,
  CAD: 0.73,
  SGD: 0.76,
  AED: 0.27,
  THB: 0.028,
};

export interface ConversionResult {
  converted: Money;
  rate: number;
  fxAt: Date;
}

export class FXService {
  /**
   * Fetches exchange rates for a given base currency.
   * Checks Redis cache first (TTL 12h).
   */
  async getRates(baseCurrency: string): Promise<{ rates: Record<string, number>; timestamp: Date }> {
    const base = baseCurrency.toUpperCase().trim();
    const cacheKey = `fx:${base}`;

    try {
      const cached = await redisClient.get(cacheKey);
      if (cached) {
        const parsed = JSON.parse(cached);
        return {
          rates: parsed.rates,
          timestamp: new Date(parsed.timestamp),
        };
      }
    } catch (err: any) {
      logger.warn(`Redis FX cache read failed for ${cacheKey}:`, { error: err.message });
    }

    let rates: Record<string, number> | null = null;
    let timestamp = new Date();

    // Try free Open Exchange Rate API (no API key required)
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);
      const res = await fetch(`https://open.er-api.com/v6/latest/${base}`, {
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json();
        if (data && data.rates && typeof data.rates === 'object') {
          rates = data.rates;
          timestamp = new Date(data.time_last_update_utc || Date.now());
        }
      }
    } catch (err: any) {
      logger.warn(`External FX fetch failed for ${base}, falling back to static rates:`, {
        error: err.message,
      });
    }

    // Fallback calculation if external API fails
    if (!rates) {
      const baseInUsd = FALLBACK_RATES_TO_USD[base] || 1.0;
      rates = {};
      for (const [curr, currInUsd] of Object.entries(FALLBACK_RATES_TO_USD)) {
        rates[curr] = baseInUsd / currInUsd;
      }
      rates[base] = 1.0;
    }

    try {
      await redisClient.set(
        cacheKey,
        JSON.stringify({ rates, timestamp: timestamp.toISOString() }),
        'EX',
        FX_CACHE_TTL_SECONDS
      );
    } catch (err: any) {
      logger.warn(`Redis FX cache write failed for ${cacheKey}:`, { error: err.message });
    }

    return { rates, timestamp };
  }

  /**
   * Converts money from one currency to another using exact minor integer units.
   */
  async convert(money: Money, toCurrency: string): Promise<ConversionResult> {
    const fromCurr = money.currency.toUpperCase().trim();
    const toCurr = toCurrency.toUpperCase().trim();

    if (fromCurr === toCurr) {
      return {
        converted: {
          amountMinor: money.amountMinor,
          currency: toCurr,
        },
        rate: 1.0,
        fxAt: new Date(),
      };
    }

    const { rates, timestamp } = await this.getRates(fromCurr);
    const rate = rates[toCurr];

    if (typeof rate !== 'number' || isNaN(rate) || rate <= 0) {
      throw new Error(`FX rate not available for conversion from ${fromCurr} to ${toCurr}`);
    }

    const convertedAmountMinor = Math.round(money.amountMinor * rate);

    return {
      converted: {
        amountMinor: convertedAmountMinor,
        currency: toCurr,
      },
      rate,
      fxAt: timestamp,
    };
  }
}

export const fxService = new FXService();
