import { z } from 'zod';
import { DateStringSchema, GeoPointSchema, ProviderRefSchema, VibeTagSchema } from './common.schema';

export const spotEventSchema = z.object({
  name: z.string(),
  date: DateStringSchema.nullable().optional(),
  venue: z.string().nullable().optional(),
});

export const spotVibeScoreSchema = z.object({
  vibe: VibeTagSchema,
  score: z.number().min(0).max(1),
});

export const spotOptionSchema = z.object({
  providerRef: ProviderRefSchema,
  name: z.string(),
  location: GeoPointSchema,
  rating: z.number().min(0).max(5).nullable().optional(),
  vibeScores: z.array(spotVibeScoreSchema),
  matchingEvent: spotEventSchema.nullable().optional(),
  tagSource: z.enum(['llm', 'keyword_match']).or(z.string()),
});

export type SpotOption = z.infer<typeof spotOptionSchema>;

export const aiDiscoverSpotsRequestSchema = z.object({
  tripId: z.string(),
  city: z.string().min(1),
  country: z.string().min(1),
  startDate: DateStringSchema,
  endDate: DateStringSchema,
  vibes: z.array(VibeTagSchema),
});

export type AIDiscoverSpotsRequest = z.infer<typeof aiDiscoverSpotsRequestSchema>;

export const aiDiscoverSpotsResponseSchema = z.object({
  tripId: z.string(),
  spots: z.array(spotOptionSchema),
  fallbackUsed: z.boolean().default(false),
});

export type AIDiscoverSpotsResponse = z.infer<typeof aiDiscoverSpotsResponseSchema>;

export const selectSpotsSchema = z.object({
  spotIds: z.array(z.string().min(1)).min(1, 'Select at least one spot'),
});

export type SelectSpotsInput = z.infer<typeof selectSpotsSchema>;

