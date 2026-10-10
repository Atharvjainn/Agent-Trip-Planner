'use client';

import React, { useEffect, useState, useCallback, use } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { getTrip, getFlightOptions, selectFlight, searchFlights } from '../../../lib/api/trips';
import { TripResponse, FlightOption } from '../../../lib/api/schemas';
import { useJob } from '../../../hooks/useJob';
import { FlightCard } from '../../../components/trips/FlightCard';
import { BudgetTracker } from '../../../components/trips/BudgetTracker';
import { JobState } from '../../../components/trips/JobState';
import { Button } from '../../../components/ui/Button';

export default function FlightsPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const resolvedParams = use(params);
  const tripId = resolvedParams.tripId;
  const router = useRouter();
  const searchParams = useSearchParams();

  const [trip, setTrip] = useState<TripResponse | null>(null);
  const [flightOptions, setFlightOptions] = useState<FlightOption[]>([]);
  const [selectedFlight, setSelectedFlight] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const [selectingFlightId, setSelectingFlightId] = useState<string | null>(null);
  const [trackerRefreshKey, setTrackerRefreshKey] = useState(0);

  // Filter & Sort state
  const [filterNonStop, setFilterNonStop] = useState(false);
  const [sortBy, setSortBy] = useState<'price' | 'duration'>('price');

  const queryJobId = searchParams.get('jobId');
  const [activeJobId, setActiveJobId] = useState<string | null>(queryJobId);

  const fetchFlightData = useCallback(async () => {
    try {
      setPageError(null);
      const tripData = await getTrip(tripId);
      setTrip(tripData);

      // Route guard: if no destination, redirect to destination selection
      if (tripData.status === 'DRAFT') {
        router.replace(`/trips/${tripId}/destinations`);
        return;
      }

      const flightsData = await getFlightOptions(tripId);
      setFlightOptions(flightsData.options || []);
      setSelectedFlight(flightsData.selectedFlight || null);

      if ((!flightsData.options || flightsData.options.length === 0) && flightsData.pendingJob) {
        setActiveJobId(flightsData.pendingJob.id);
      } else if (!flightsData.options || flightsData.options.length === 0) {
        // Automatically enqueue flight search if not yet run
        if (!activeJobId) {
          try {
            const res = await searchFlights(tripId);
            setActiveJobId(res.jobId);
          } catch (e: any) {
            console.error('Failed to trigger flight search:', e);
          }
        }
      }
    } catch (err: any) {
      console.error('Failed to load flight page data:', err);
      setPageError(err.message || 'Failed to load flight options');
    } finally {
      setLoading(false);
    }
  }, [tripId, router, activeJobId]);

  useEffect(() => {
    fetchFlightData();
  }, [fetchFlightData]);

  // Hook for polling active search-flights job
  const {
    status: jobStatus,
    error: jobError,
    retry: retryJob,
  } = useJob(activeJobId, {
    onCompleted: () => {
      fetchFlightData();
    },
  });

  const handleSelectFlight = async (flight: FlightOption) => {
    const flightId = flight.providerRef.id || flight.outbound[0]?.flightNumber || 'flight';
    setSelectingFlightId(flightId);
    try {
      const res = await selectFlight(tripId, flight);
      setSelectedFlight({
        providerId: flightId,
        providerName: flight.outbound[0]?.airline,
      });
      setTrackerRefreshKey((prev) => prev + 1);
      // Advance to Hotels step
      const nextUrl = res.searchHotelsJobId
        ? `/trips/${tripId}/hotels?jobId=${res.searchHotelsJobId}`
        : `/trips/${tripId}/hotels`;
      router.push(nextUrl);
    } catch (err: any) {
      alert(err.message || 'Failed to save flight selection');
    } finally {
      setSelectingFlightId(null);
    }
  };

  if (loading) {
    return (
      <JobState
        status="loading"
        loadingMessage="Checking flight routes and live prices..."
      />
    );
  }

  if (pageError) {
    return (
      <JobState
        status="error"
        errorMessage={pageError}
        onRetry={fetchFlightData}
      />
    );
  }

  // Active Job state
  if (flightOptions.length === 0 && (jobStatus === 'active' || jobStatus === 'queued')) {
    return (
      <div className="py-4">
        <BudgetTracker tripId={tripId} refreshKey={trackerRefreshKey} className="mb-6 sticky top-4 z-20" />
        <JobState
          status="loading"
          loadingMessage={`Searching real-time flights from ${trip?.source || 'origin'} to ${
            trip?.destinationCity || 'destination'
          }...`}
        />
      </div>
    );
  }

  if (flightOptions.length === 0 && jobStatus === 'failed') {
    return (
      <div className="py-4">
        <BudgetTracker tripId={tripId} refreshKey={trackerRefreshKey} className="mb-6 sticky top-4 z-20" />
        <JobState
          status="error"
          errorMessage={jobError || "We couldn't fetch live flight prices. Please try again."}
          onRetry={retryJob}
        />
      </div>
    );
  }

  // Filter and Sort
  let displayOptions = [...flightOptions];
  if (filterNonStop) {
    displayOptions = displayOptions.filter((f) => f.stops === 0);
  }

  displayOptions.sort((a, b) => {
    if (sortBy === 'price') {
      const priceA = a.convertedPrice?.amountMinor ?? a.price.amountMinor;
      const priceB = b.convertedPrice?.amountMinor ?? b.price.amountMinor;
      return priceA - priceB;
    }
    return a.totalDurationMinutes - b.totalDurationMinutes;
  });

  const baseCurrency = trip?.baseCurrency || 'INR';

  return (
    <div className="py-4 pb-28">
      {/* Pinned Live Budget Tracker */}
      <BudgetTracker tripId={tripId} refreshKey={trackerRefreshKey} className="mb-6 sticky top-4 z-20" />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full">
            Step 3 • Select Flight
          </span>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight mt-3">
            Flights to {trip?.destinationCity || 'Destination'}
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Prices are converted to {baseCurrency} with live exchange rates. Select a flight to lock in your travel.
          </p>
        </div>

        {/* Filter and Sort Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setFilterNonStop(!filterNonStop)}
            className={`text-xs font-semibold px-3 py-2 rounded-xl border transition-all ${
              filterNonStop
                ? 'bg-indigo-600 text-white border-indigo-600'
                : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
            }`}
          >
            {filterNonStop ? '✓ Non-stop only' : 'Filter: Non-stop'}
          </button>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="text-xs font-semibold bg-white text-slate-700 border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="price">Sort: Lowest Price</option>
            <option value="duration">Sort: Shortest Duration</option>
          </select>
        </div>
      </div>

      {/* Empty State */}
      {displayOptions.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center max-w-lg mx-auto">
          <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl mx-auto mb-3">
            ✈️
          </div>
          <h3 className="text-base font-bold text-slate-900 mb-1">No flights found matching criteria</h3>
          <p className="text-xs text-slate-500 mb-6">
            Try turning off filters or searching for alternative departure dates.
          </p>
          {filterNonStop && (
            <Button variant="secondary" size="sm" onClick={() => setFilterNonStop(false)}>
              Show all flights
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {displayOptions.map((flight, idx) => {
            const flightId = flight.providerRef.id || flight.outbound[0]?.flightNumber || `flight-${idx}`;
            const isSelected = selectedFlight
              ? flightId === selectedFlight.providerId || flight.isSelected
              : false;

            return (
              <FlightCard
                key={flightId}
                flight={flight}
                baseCurrency={baseCurrency}
                selected={isSelected}
                isSelecting={selectingFlightId === flightId}
                onSelect={() => handleSelectFlight(flight)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
