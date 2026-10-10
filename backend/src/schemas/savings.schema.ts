import { z } from 'zod';
import { moneySchema } from './common.schema';

export const selectionSnapshotSchema = z.object({
  flightPrice: moneySchema.optional(),
  hotelPricePerNight: moneySchema.optional(),
  nights: z.number().optional(),
  stayBudget: moneySchema.optional(),
});

export type SelectionSnapshot = z.infer<typeof selectionSnapshotSchema>;

export const savingsSuggestRequestSchema = z.object({
  tripId: z.string(),
  selections: selectionSnapshotSchema,
});

export type SavingsSuggestRequest = z.infer<typeof savingsSuggestRequestSchema>;

export const savingSuggestionSchema = z.object({
  strategyId: z.string(),
  title: z.string(),
  description: z.string(),
  estimatedSavings: moneySchema,
});

export type SavingSuggestion = z.infer<typeof savingSuggestionSchema>;

export const savingsSuggestResponseSchema = z.object({
  tripId: z.string(),
  suggestions: z.array(savingSuggestionSchema),
  fallbackUsed: z.boolean().default(false),
});

export type SavingsSuggestResponse = z.infer<typeof savingsSuggestResponseSchema>;
