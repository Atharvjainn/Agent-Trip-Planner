import { z } from 'zod';
import { MoneySchema } from './common.schema';

export const SelectionTypeEnum = z.enum(['spot', 'flight', 'hotel']);
export type SelectionType = z.infer<typeof SelectionTypeEnum>;

export const SelectionSchema = z.object({
  id: z.string(),
  tripId: z.string(),
  type: SelectionTypeEnum,
  providerId: z.string(),
  providerName: z.string().nullable().optional(),
  originalMoney: MoneySchema,
  convertedMoney: MoneySchema,
  fxRate: z.number(),
  fxAt: z.string().or(z.date()),
  deepLink: z.string().nullable().optional(),
  metadata: z.record(z.string(), z.unknown()).nullable().optional(),
  createdAt: z.string().or(z.date()),
  updatedAt: z.string().or(z.date()),
});

export type Selection = z.infer<typeof SelectionSchema>;
