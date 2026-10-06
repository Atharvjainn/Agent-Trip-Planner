import { apiFetch } from './client';
import {
  CreateTripFormData,
  TripResponse,
  SelectDestinationInput,
  JobResponse,
  tripResponseSchema,
  jobResponseSchema,
} from './schemas';

export interface CreateTripResult {
  tripId: string;
  jobId: string;
  status: string;
}

export interface SelectDestinationResult {
  jobId: string;
}

export async function createTrip(data: CreateTripFormData): Promise<CreateTripResult> {
  const payload = {
    source: data.source,
    destinationCity: data.destinationCity || undefined,
    destinationCountry: data.destinationCountry || undefined,
    startDate: data.startDate,
    endDate: data.endDate,
    travelers: data.travelers,
    budget: {
      amountMinor: Math.round(data.budgetAmount * 100),
      currency: data.currency,
    },
    vibes: data.vibes,
  };

  return apiFetch<CreateTripResult>('/trips', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTrip(tripId: string): Promise<TripResponse> {
  const data = await apiFetch<unknown>(`/trips/${tripId}`);
  return tripResponseSchema.parse(data);
}

export async function selectDestination(
  tripId: string,
  input: SelectDestinationInput
): Promise<SelectDestinationResult> {
  return apiFetch<SelectDestinationResult>(`/trips/${tripId}/destination`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const data = await apiFetch<unknown>(`/jobs/${jobId}`);
  return jobResponseSchema.parse(data);
}

export async function getTripBudget(tripId: string) {
  return apiFetch<{
    tripId: string;
    currency: string;
    totalBudget: { amountMinor: number; currency: string };
    allocations: Array<{ category: string; amount: { amountMinor: number; currency: string } }>;
    explanation?: string;
  }>(`/trips/${tripId}/budget`);
}

export async function selectSpots(
  tripId: string,
  spotIds: string[]
): Promise<{ tripId: string; status: string; selectedCount: number }> {
  return apiFetch<{ tripId: string; status: string; selectedCount: number }>(
    `/trips/${tripId}/spots`,
    {
      method: 'POST',
      body: JSON.stringify({ spotIds }),
    }
  );
}
