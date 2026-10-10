import { z } from 'zod';

export const chatRequestSchema = z.object({
  message: z.string().min(1, 'Message cannot be empty'),
  sessionId: z.string().optional(),
  userLocation: z
    .object({
      lat: z.number(),
      lng: z.number(),
    })
    .optional(),
});

export type ChatRequestInput = z.infer<typeof chatRequestSchema>;

export const turnResponseSchema = z.object({
  reply: z.string(),
  stage: z.string(),
  uiComponent: z.string(),
  options: z.array(z.record(z.string(), z.any())).default([]),
  requiresUserInput: z.boolean(),
  inputType: z.string(),
});

export type TurnResponse = z.infer<typeof turnResponseSchema>;

export const chatMetricsSchema = z
  .object({
    totalMs: z.number(),
    routingMs: z.number().nullable().optional(),
    graphExecMs: z.number(),
  })
  .optional();

export const aiChatResponseSchema = z.object({
  tripId: z.string(),
  sessionId: z.string(),
  conversationStage: z.string(),
  tripStatus: z.string(),
  turnResponse: turnResponseSchema,
  stateSummary: z.record(z.string(), z.any()).default({}),
  metrics: chatMetricsSchema,
});

export type AIChatResponse = z.infer<typeof aiChatResponseSchema>;
