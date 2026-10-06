import { z } from 'zod';
import { BudgetCategorySchema, MoneySchema, VibeTagSchema } from './common.schema';

export const categoryAllocationSchema = z.object({
  category: BudgetCategorySchema,
  amount: MoneySchema,
});

export type CategoryAllocation = z.infer<typeof categoryAllocationSchema>;

export const aiBudgetEstimateRequestSchema = z.object({
  tripId: z.string(),
  budgetTotal: MoneySchema,
  isInternational: z.boolean(),
  durationDays: z.number().int().min(1),
  vibes: z.array(VibeTagSchema).default([]),
});

export type AIBudgetEstimateRequest = z.infer<typeof aiBudgetEstimateRequestSchema>;

export const aiBudgetEstimateResponseSchema = z.object({
  tripId: z.string(),
  currency: z.string(),
  allocations: z.array(categoryAllocationSchema),
  explanation: z.string(),
  fallbackUsed: z.boolean().default(false),
});

export type AIBudgetEstimateResponse = z.infer<typeof aiBudgetEstimateResponseSchema>;

export const tripBudgetResponseSchema = z.object({
  tripId: z.string(),
  currency: z.string(),
  totalBudget: MoneySchema,
  allocations: z.array(categoryAllocationSchema),
  explanation: z.string().optional(),
});

export type TripBudgetResponse = z.infer<typeof tripBudgetResponseSchema>;
