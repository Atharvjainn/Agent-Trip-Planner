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

// Trip Creation
export const createTripSchema = z
  .object({
    source: z.string().min(1, 'Source is required (city or airport code)'),
    destinationCity: z.string().optional(),
    destinationCountry: z.string().optional(),
    startDate: DateStringSchema,
    endDate: DateStringSchema,
    travelers: z.number().int().min(1).max(20).default(1),
    budgetAmount: z.number().positive('Budget must be positive'),
    currency: z.string().default('INR'),
    vibes: z.array(VibeTagSchema).min(1, 'Select at least one vibe tag'),
  })
  .refine(
    (data) => {
      return (
        (!data.destinationCity && !data.destinationCountry) ||
        (Boolean(data.destinationCity) && Boolean(data.destinationCountry))
      );
    },
    {
      message: 'Destination city and country must both be filled or both omitted',
      path: ['destinationCity'],
    }
  )
  .refine(
    (data) => {
      return data.endDate >= data.startDate;
    },
    {
      message: 'End date must be on or after start date',
      path: ['endDate'],
    }
  );

export type CreateTripFormData = z.infer<typeof createTripSchema>;

// Destination options
export const destinationOptionSchema = z.object({
  city: z.string(),
  country: z.string(),
  estimatedFlightPrice: MoneySchema,
  vibeMatchScore: z.number().min(0).max(1),
  reason: z.string(),
  source: z.string(),
});

export type DestinationOption = z.infer<typeof destinationOptionSchema>;

export const selectDestinationSchema = z.object({
  city: z.string().min(1),
  country: z.string().min(1),
});

export type SelectDestinationInput = z.infer<typeof selectDestinationSchema>;

// Spot options
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
  rating: z.number().nullable().optional(),
  vibeScores: z.array(spotVibeScoreSchema),
  matchingEvent: spotEventSchema.nullable().optional(),
  tagSource: z.string(),
});

export type SpotOption = z.infer<typeof spotOptionSchema>;

// Job response
export const jobResponseSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.enum(['queued', 'active', 'completed', 'failed']),
  error: z.string().nullable().optional(),
});

export type JobResponse = z.infer<typeof jobResponseSchema>;

// Full Trip Model
export const tripResponseSchema = z.object({
  id: z.string(),
  userId: z.string(),
  status: TripStatusSchema,
  source: z.string(),
  destinationCity: z.string().nullable().optional(),
  destinationCountry: z.string().nullable().optional(),
  startDate: z.string(),
  endDate: z.string(),
  travelers: z.number(),
  vibes: z.array(z.string()),
  budgetTotalMinor: z.number(),
  baseCurrency: z.string(),
  destinationOptions: z.array(destinationOptionSchema).nullable().optional(),
  spotOptions: z.array(spotOptionSchema).nullable().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
  pendingJob: z
    .object({
      id: z.string(),
      name: z.string(),
      status: z.string(),
    })
    .nullable()
    .optional(),
});

export type TripResponse = z.infer<typeof tripResponseSchema>;
