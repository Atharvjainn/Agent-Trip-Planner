import { z } from 'zod';
import { DateStringSchema, MoneySchema, VibeTagSchema } from './common.schema';

export const selectDestinationSchema = z.object({
  city: z.string().min(1, 'City is required'),
  country: z.string().min(1, 'Country is required'),
});

export type SelectDestinationInput = z.infer<typeof selectDestinationSchema>;

export const destinationOptionSchema = z.object({
  city: z.string(),
  country: z.string(),
  estimatedFlightPrice: MoneySchema,
  vibeMatchScore: z.number().min(0).max(1),
  reason: z.string(),
  source: z.enum(['llm', 'knowledge_graph']).or(z.string()),
});

export type DestinationOption = z.infer<typeof destinationOptionSchema>;

export const aiRecommendDestinationsRequestSchema = z.object({
  tripId: z.string(),
  source: z.string(),
  startDate: DateStringSchema,
  endDate: DateStringSchema,
  travelers: z.number().int().min(1),
  budgetTotal: MoneySchema,
  vibes: z.array(VibeTagSchema),
});

export type AIRecommendDestinationsRequest = z.infer<typeof aiRecommendDestinationsRequestSchema>;

export const aiRecommendDestinationsResponseSchema = z.object({
  tripId: z.string(),
  options: z.array(destinationOptionSchema).max(5),
  fallbackUsed: z.boolean().default(false),
});

export type AIRecommendDestinationsResponse = z.infer<typeof aiRecommendDestinationsResponseSchema>;
