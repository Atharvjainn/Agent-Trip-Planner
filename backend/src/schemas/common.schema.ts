import { z } from 'zod';
import vibesJson from '../shared/vibes.json';
import tripStatusJson from '../shared/trip_status.json';
import budgetCategoriesJson from '../shared/budget_categories.json';

export const VibeTags = vibesJson.values as [string, ...string[]];
export const TripStatuses = tripStatusJson.values as [string, ...string[]];
export const BudgetCategories = budgetCategoriesJson.values as [string, ...string[]];

export const VibeTagSchema = z.enum(VibeTags);
export const TripStatusSchema = z.enum(TripStatuses);
export const BudgetCategorySchema = z.enum(BudgetCategories);

export const MoneySchema = z.object({
  amountMinor: z.number().int().nonnegative(),
  currency: z.string().length(3).transform((v) => v.toUpperCase()),
});

export type Money = z.infer<typeof MoneySchema>;

export const DateStringSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, 'Date must be in YYYY-MM-DD format');

export const GeoPointSchema = z.object({
  lat: z.number(),
  lng: z.number(),
});

export const ProviderRefSchema = z.object({
  provider: z.string().default('serpapi'),
  id: z.string(),
  deepLink: z.string().nullable().optional(),
});
