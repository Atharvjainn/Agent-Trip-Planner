import { z } from 'zod';
import { MoneySchema, ProviderRefSchema, DateStringSchema } from './common.schema';

export const FlightLegSchema = z.object({
  airline: z.string(),
  flightNumber: z.string(),
  departureAirport: z.string(),
  arrivalAirport: z.string(),
  departsAt: z.string().or(z.date()).transform((v) => (typeof v === 'string' ? v : v.toISOString())),
  arrivesAt: z.string().or(z.date()).transform((v) => (typeof v === 'string' ? v : v.toISOString())),
});

export const FlightOptionSchema = z.object({
  providerRef: ProviderRefSchema,
  outbound: z.array(FlightLegSchema),
  inbound: z.array(FlightLegSchema).default([]),
  price: MoneySchema,
  stops: z.number().int().nonnegative(),
  totalDurationMinutes: z.number().int().nonnegative(),
  convertedPrice: MoneySchema.optional(),
  fxRate: z.number().optional(),
  isSelected: z.boolean().optional().default(false),
});

export type FlightLeg = z.infer<typeof FlightLegSchema>;
export type FlightOption = z.infer<typeof FlightOptionSchema>;

export const AIFlightSearchRequestSchema = z.object({
  tripId: z.string(),
  source: z.string(),
  destination: z.string(),
  startDate: DateStringSchema,
  endDate: DateStringSchema,
  travelers: z.number().int().min(1),
  flightsBudget: MoneySchema,
});

export const AIFlightSearchResponseSchema = z.object({
  tripId: z.string(),
  options: z.array(FlightOptionSchema),
  fallbackUsed: z.boolean().default(false),
});

export type AIFlightSearchRequest = z.infer<typeof AIFlightSearchRequestSchema>;
export type AIFlightSearchResponse = z.infer<typeof AIFlightSearchResponseSchema>;

export const SelectFlightRequestSchema = z.object({
  flight: FlightOptionSchema,
});

export type SelectFlightRequest = z.infer<typeof SelectFlightRequestSchema>;
