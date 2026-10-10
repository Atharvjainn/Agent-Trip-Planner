import { z } from 'zod';
import { moneySchema, geoPointSchema } from './common.schema';
import { selectedSpotInputSchema } from './hotel.schema';

export const commuteEstimateSchema = z.object({
  dailyDistanceKm: z.number(),
  dailyCost: moneySchema,
  tripTotalCost: moneySchema,
  mode: z.string(), // auto | cab | metro | walk
});

export type CommuteEstimate = z.infer<typeof commuteEstimateSchema>;

export const summaryBuildRequestSchema = z.object({
  tripId: z.string(),
  city: z.string(),
  hotelLocation: geoPointSchema,
  selectedSpots: z.array(selectedSpotInputSchema),
  flightPrice: moneySchema,
  hotelTotalPrice: moneySchema,
  nights: z.number(),
});

export type SummaryBuildRequest = z.infer<typeof summaryBuildRequestSchema>;

export const summaryBuildResponseSchema = z.object({
  tripId: z.string(),
  narrative: z.string(),
  commute: commuteEstimateSchema,
  fallbackUsed: z.boolean().default(false),
});

export type SummaryBuildResponse = z.infer<typeof summaryBuildResponseSchema>;
