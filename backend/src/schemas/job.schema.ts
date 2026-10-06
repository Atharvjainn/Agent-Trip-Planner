import { z } from 'zod';

export const jobParamsSchema = z.object({
  jobId: z.string().min(1),
});

export type JobParams = z.infer<typeof jobParamsSchema>;

export const jobResponseSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.enum(['queued', 'active', 'completed', 'failed']),
  error: z.string().nullable().optional(),
});

export type JobResponse = z.infer<typeof jobResponseSchema>;
