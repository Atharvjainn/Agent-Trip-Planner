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
    totalSpent?: { amountMinor: number; currency: string };
    totalRemaining?: { amountMinor: number; currency: string };
    isOverBudget?: boolean;
    allocations: Array<{ category: string; amount: { amountMinor: number; currency: string } }>;
    tracker?: Array<{
      category: string;
      allocatedMinor: number;
      spentMinor: number;
      remainingMinor: number;
      isOverBudget: boolean;
    }>;
    explanation?: string;
  }>(`/trips/${tripId}/budget`);
}

export async function selectSpots(
  tripId: string,
  spotIds: string[]
): Promise<{ tripId: string; status: string; selectedCount: number; searchFlightsJobId?: string }> {
  return apiFetch<{ tripId: string; status: string; selectedCount: number; searchFlightsJobId?: string }>(
    `/trips/${tripId}/spots`,
    {
      method: 'POST',
      body: JSON.stringify({ spotIds }),
    }
  );
}

export async function searchFlights(tripId: string): Promise<{ jobId: string; status: string }> {
  return apiFetch<{ jobId: string; status: string }>(`/trips/${tripId}/flights/search`, {
    method: 'POST',
  });
}

export async function getFlightOptions(tripId: string) {
  return apiFetch<{
    tripId: string;
    baseCurrency: string;
    options: any[];
    selectedFlight?: any;
    pendingJob?: { id: string; status: string } | null;
  }>(`/trips/${tripId}/flights`);
}

export async function selectFlight(tripId: string, flight: any) {
  return apiFetch<{ success: boolean; selection: any; searchHotelsJobId?: string; nextStep: string }>(
    `/trips/${tripId}/flight`,
    {
      method: 'POST',
      body: JSON.stringify({ flight }),
    }
  );
}

export async function searchHotels(tripId: string): Promise<{ jobId: string; status: string }> {
  return apiFetch<{ jobId: string; status: string }>(`/trips/${tripId}/hotels/search`, {
    method: 'POST',
  });
}

export async function getHotelOptions(tripId: string) {
  return apiFetch<{
    tripId: string;
    baseCurrency: string;
    nights: number;
    stayBudgetMinor: number;
    options: any[];
    selectedHotel?: any;
    pendingJob?: { id: string; status: string } | null;
  }>(`/trips/${tripId}/hotels`);
}

export async function selectHotel(tripId: string, hotel: any) {
  return apiFetch<{ success: boolean; selection: any; buildSummaryJobId?: string; nextStep: string }>(
    `/trips/${tripId}/hotel`,
    {
      method: 'POST',
      body: JSON.stringify({ hotel }),
    }
  );
}

export async function updateStayBudget(tripId: string, stayBudgetMinor: number) {
  return apiFetch<{ tripId: string; stayBudgetMinor: number; budgetAllocation: any }>(
    `/trips/${tripId}/budget`,
    {
      method: 'PATCH',
      body: JSON.stringify({ stayBudgetMinor }),
    }
  );
}

export async function getTripSummary(tripId: string) {
  return apiFetch<any>(`/trips/${tripId}/summary`);
}

export async function buildTripSummary(tripId: string): Promise<{ jobId: string; status: string }> {
  return apiFetch<{ jobId: string; status: string }>(`/trips/${tripId}/summary/build`, {
    method: 'POST',
  });
}



