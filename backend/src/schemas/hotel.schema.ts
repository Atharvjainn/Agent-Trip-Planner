import { z } from 'zod';
import { MoneySchema, ProviderRefSchema, GeoPointSchema } from './common.schema';

export const SelectedSpotInputSchema = z.object({
  id: z.string(),
  name: z.string(),
  location: GeoPointSchema,
});

export const selectedSpotInputSchema = SelectedSpotInputSchema;

export const SpotDistanceSchema = z.object({
  spotId: z.string(),
  spotName: z.string(),
  distanceKm: z.number().nonnegative(),
});

export const HotelOptionSchema = z.object({
  providerRef: ProviderRefSchema,
  name: z.string(),
  location: GeoPointSchema,
  pricePerNight: MoneySchema,
  convertedPricePerNight: MoneySchema.optional(),
  totalPrice: MoneySchema.optional(),
  rating: z.number().min(0).max(5).nullable().optional(),
  reviewSnippet: z.string().nullable().optional(),
  distances: z.array(SpotDistanceSchema),
  score: z.number().min(0).max(1),
  fxRate: z.number().optional(),
  isSelected: z.boolean().optional().default(false),
});

export type SelectedSpotInput = z.infer<typeof SelectedSpotInputSchema>;
export type SpotDistance = z.infer<typeof SpotDistanceSchema>;
export type HotelOption = z.infer<typeof HotelOptionSchema>;

export const AIHotelSearchRequestSchema = z.object({
  tripId: z.string(),
  city: z.string(),
  selectedSpots: z.array(SelectedSpotInputSchema).min(1),
  stayBudget: MoneySchema,
  nights: z.number().int().min(1),
});

export const AIHotelSearchResponseSchema = z.object({
  tripId: z.string(),
  options: z.array(HotelOptionSchema),
  fallbackUsed: z.boolean().default(false),
});

export type AIHotelSearchRequest = z.infer<typeof AIHotelSearchRequestSchema>;
export type AIHotelSearchResponse = z.infer<typeof AIHotelSearchResponseSchema>;

export const SelectHotelRequestSchema = z.object({
  hotel: HotelOptionSchema,
});

export type SelectHotelRequest = z.infer<typeof SelectHotelRequestSchema>;

export const PatchStayBudgetSchema = z.object({
  stayBudgetMinor: z.number().int().positive(),
});

export type PatchStayBudget = z.infer<typeof PatchStayBudgetSchema>;
