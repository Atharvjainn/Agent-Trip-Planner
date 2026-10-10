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

// Budget Allocation & Tracker
export const categoryAllocationSchema = z.object({
  category: BudgetCategorySchema,
  amount: MoneySchema,
});

export type CategoryAllocation = z.infer<typeof categoryAllocationSchema>;

export const categoryTrackerSchema = z.object({
  category: z.string(),
  allocatedMinor: z.number(),
  spentMinor: z.number(),
  remainingMinor: z.number(),
  isOverBudget: z.boolean(),
});

export type CategoryTracker = z.infer<typeof categoryTrackerSchema>;

export const tripBudgetResponseSchema = z.object({
  tripId: z.string(),
  currency: z.string(),
  totalBudget: MoneySchema,
  totalSpent: MoneySchema.optional(),
  totalRemaining: MoneySchema.optional(),
  isOverBudget: z.boolean().optional(),
  allocations: z.array(categoryAllocationSchema),
  tracker: z.array(categoryTrackerSchema).optional(),
  explanation: z.string().optional(),
});

export type TripBudgetResponse = z.infer<typeof tripBudgetResponseSchema>;


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
  isSelected: z.boolean().optional(),
});

export type SpotOption = z.infer<typeof spotOptionSchema>;

export const selectSpotsSchema = z.object({
  spotIds: z.array(z.string().min(1)).min(1, 'Select at least one spot'),
});

export type SelectSpotsInput = z.infer<typeof selectSpotsSchema>;

// Flight Options
export const flightLegSchema = z.object({
  airline: z.string(),
  flightNumber: z.string(),
  departureAirport: z.string(),
  arrivalAirport: z.string(),
  departsAt: z.string(),
  arrivesAt: z.string(),
});

export const flightOptionSchema = z.object({
  providerRef: ProviderRefSchema,
  outbound: z.array(flightLegSchema),
  inbound: z.array(flightLegSchema).default([]),
  price: MoneySchema,
  stops: z.number().int().nonnegative(),
  totalDurationMinutes: z.number().int().nonnegative(),
  convertedPrice: MoneySchema.optional(),
  fxRate: z.number().optional(),
  isSelected: z.boolean().optional(),
});

export type FlightLeg = z.infer<typeof flightLegSchema>;
export type FlightOption = z.infer<typeof flightOptionSchema>;

export const selectFlightSchema = z.object({
  flight: flightOptionSchema,
});

export type SelectFlightInput = z.infer<typeof selectFlightSchema>;

// Hotel Options
export const spotDistanceSchema = z.object({
  spotId: z.string(),
  spotName: z.string(),
  distanceKm: z.number().nonnegative(),
});

export const hotelOptionSchema = z.object({
  providerRef: ProviderRefSchema,
  name: z.string(),
  location: GeoPointSchema,
  pricePerNight: MoneySchema,
  convertedPricePerNight: MoneySchema.optional(),
  totalPrice: MoneySchema.optional(),
  rating: z.number().min(0).max(5).nullable().optional(),
  reviewSnippet: z.string().nullable().optional(),
  distances: z.array(spotDistanceSchema),
  score: z.number().min(0).max(1),
  fxRate: z.number().optional(),
  isSelected: z.boolean().optional(),
});

export type SpotDistance = z.infer<typeof spotDistanceSchema>;
export type HotelOption = z.infer<typeof hotelOptionSchema>;

export const selectHotelSchema = z.object({
  hotel: hotelOptionSchema,
});

export type SelectHotelInput = z.infer<typeof selectHotelSchema>;

// Selections
export const selectionSchema = z.object({
  id: z.string(),
  tripId: z.string(),
  type: z.enum(['spot', 'flight', 'hotel']),
  providerId: z.string(),
  providerName: z.string().nullable().optional(),
  originalMoney: MoneySchema,
  convertedMoney: MoneySchema,
  fxRate: z.number(),
  fxAt: z.string(),
  deepLink: z.string().nullable().optional(),
  metadata: z.record(z.string(), z.unknown()).nullable().optional(),
});

export type Selection = z.infer<typeof selectionSchema>;

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
  flightOptions: z.array(flightOptionSchema).nullable().optional(),
  hotelOptions: z.array(hotelOptionSchema).nullable().optional(),
  selections: z.array(selectionSchema).nullable().optional(),
  budgetAllocation: z
    .object({
      tripId: z.string().optional(),
      currency: z.string().optional(),
      allocations: z.array(categoryAllocationSchema),
      explanation: z.string().optional(),
      fallbackUsed: z.boolean().optional(),
    })
    .passthrough()
    .nullable()
    .optional(),
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


