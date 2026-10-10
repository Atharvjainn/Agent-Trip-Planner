export type TripStatus =
  | 'DRAFT'
  | 'DESTINATION_SELECTED'
  | 'BUDGET_ESTIMATED'
  | 'SPOTS_SELECTED'
  | 'FLIGHT_SELECTED'
  | 'HOTEL_SELECTED'
  | 'SUMMARY_READY';

export const STATUS_ROUTES: Record<TripStatus, (tripId: string) => string> = {
  DRAFT: (id) => `/trips/${id}/destinations`,
  DESTINATION_SELECTED: (id) => `/trips/${id}/spots`,
  BUDGET_ESTIMATED: (id) => `/trips/${id}/spots`,
  SPOTS_SELECTED: (id) => `/trips/${id}/flight`,
  FLIGHT_SELECTED: (id) => `/trips/${id}/hotel`,
  HOTEL_SELECTED: (id) => `/trips/${id}/savings`,
  SUMMARY_READY: (id) => `/trips/${id}/summary`,
};

export function getExpectedRouteForStatus(tripId: string, status: string): string {
  const handler = STATUS_ROUTES[status as TripStatus];
  if (handler) {
    return handler(tripId);
  }
  return `/trips/${tripId}/destinations`;
}
