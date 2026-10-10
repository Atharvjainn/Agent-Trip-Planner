import { z } from 'zod';
import { DateStringSchema, MoneySchema, VibeTagSchema, TripStatusSchema } from './common.schema';

export const createTripSchema = z
  .object({
    source: z.string().min(1, 'Source is required'),
    destinationCity: z.string().optional(),
    destinationCountry: z.string().optional(),
    startDate: DateStringSchema,
    endDate: DateStringSchema,
    travelers: z.number().int().min(1).max(20).default(1),
    budget: MoneySchema,
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
      message: 'destinationCity and destinationCountry must both be provided or both omitted',
      path: ['destinationCity'],
    }
  )
  .refine(
    (data) => {
      return data.endDate >= data.startDate;
    },
    {
      message: 'endDate must be on or after startDate',
      path: ['endDate'],
    }
  );

export type CreateTripInput = z.infer<typeof createTripSchema>;

export const tripParamsSchema = z.object({
  id: z.string().min(1),
});

export type TripParams = z.infer<typeof tripParamsSchema>;
