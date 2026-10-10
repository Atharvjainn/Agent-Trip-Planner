'use client';

import React, { useEffect, useState, useCallback, use } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { getTrip, selectSpots } from '../../../lib/api/trips';
import { TripResponse, CategoryAllocation } from '../../../lib/api/schemas';
import { useJob } from '../../../hooks/useJob';
import { SpotCard } from '../../../components/trips/SpotCard';
import { BudgetBreakdown } from '../../../components/trips/BudgetBreakdown';
import { JobState } from '../../../components/trips/JobState';
import { Button } from '../../../components/ui/Button';

export default function SpotsPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const resolvedParams = use(params);
  const tripId = resolvedParams.tripId;
  const router = useRouter();
  const searchParams = useSearchParams();

  const [trip, setTrip] = useState<TripResponse | null>(null);
  const [loadingTrip, setLoadingTrip] = useState(true);
  const [tripError, setTripError] = useState<string | null>(null);

  // Spot selection state
  const [selectedSpotIds, setSelectedSpotIds] = useState<Set<string>>(new Set());
  const [isSubmittingSelection, setIsSubmittingSelection] = useState(false);
  const [selectionSuccess, setSelectionSuccess] = useState(false);

  const queryJobId = searchParams.get('jobId');
  const [activeJobId, setActiveJobId] = useState<string | null>(queryJobId);

  const fetchTrip = useCallback(async () => {
    try {
      setTripError(null);
      const data = await getTrip(tripId);
      setTrip(data);

      // Route guard: if no destination selected, redirect back to destinations
      if (data.status === 'DRAFT') {
        router.replace(`/trips/${tripId}/destinations`);
        return;
      }

      // Initialize selected spots if already saved
      if (data.spotOptions) {
        const initialSelected = new Set(
          data.spotOptions
            .filter((s) => s.isSelected)
            .map((s) => s.providerRef.id || s.name)
        );
        if (initialSelected.size > 0) {
          setSelectedSpotIds(initialSelected);
        }
      }

      if ((!data.spotOptions || !data.budgetAllocation) && data.pendingJob) {
        setActiveJobId(data.pendingJob.id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load trip spots';
      setTripError(msg);
    } finally {
      setLoadingTrip(false);
    }
  }, [tripId, router]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        const data = await getTrip(tripId);
        if (!isMounted) return;
        setTrip(data);

        if (data.status === 'DRAFT') {
          router.replace(`/trips/${tripId}/destinations`);
          return;
        }

        if (data.spotOptions) {
          const initialSelected = new Set(
            data.spotOptions
              .filter((s) => s.isSelected)
              .map((s) => s.providerRef.id || s.name)
          );
          if (initialSelected.size > 0) {
            setSelectedSpotIds(initialSelected);
          }
        }

        if ((!data.spotOptions || !data.budgetAllocation) && data.pendingJob) {
          setActiveJobId(data.pendingJob.id);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : 'Failed to load trip spots';
        setTripError(msg);
      } finally {
        if (isMounted) {
          setLoadingTrip(false);
        }
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [tripId, router]);

  const { status: jobStatus, error: jobError, retry: retryJob } = useJob(
    !trip?.spotOptions ? activeJobId : null,
    {
      onCompleted: () => {
        fetchTrip();
      },
    }
  );

  const toggleSpotSelection = (spotId: string) => {
    setSelectedSpotIds((prev) => {
      const next = new Set(prev);
      if (next.has(spotId)) {
        next.delete(spotId);
      } else {
        next.add(spotId);
      }
      return next;
    });
  };

  const handleContinue = async () => {
    if (selectedSpotIds.size === 0) {
      alert('Please select at least 1 spot to include in your trip.');
      return;
    }

    setIsSubmittingSelection(true);
    try {
      const res = await selectSpots(tripId, Array.from(selectedSpotIds));
      setSelectionSuccess(true);
      if (trip) {
        setTrip({ ...trip, status: 'SPOTS_SELECTED' });
      }
      const nextUrl = res.searchFlightsJobId
        ? `/trips/${tripId}/flights?jobId=${res.searchFlightsJobId}`
        : `/trips/${tripId}/flights`;
      router.push(nextUrl);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save spot selections';
      alert(msg);
    } finally {
      setIsSubmittingSelection(false);
    }
  };

  if (loadingTrip) {
    return (
      <JobState
        status="loading"
        loadingMessage="Loading trip attractions and budget..."
      />
    );
  }

  if (tripError) {
    return (
      <JobState
        status="error"
        errorMessage={tripError}
        onRetry={fetchTrip}
      />
    );
  }

  const destinationLabel = trip?.destinationCity
    ? `${trip.destinationCity}, ${trip.destinationCountry || ''}`
    : 'your destination';

  // If job is in progress or failed
  if (!trip?.spotOptions) {
    if (jobStatus === 'failed') {
      return (
        <JobState
          status="error"
          errorMessage={jobError || "We couldn't fetch attractions for this destination."}
          onRetry={retryJob}
        />
      );
    }

    return (
      <JobState
        status="loading"
        loadingMessage={`Finding the best spots & calculating budget for ${destinationLabel}...`}
      />
    );
  }

  const spots = trip.spotOptions;

  if (spots.length === 0) {
    return (
      <JobState
        status="empty"
        emptyTitle="No spots found"
        emptyMessage="We couldn't find popular spots matching your vibes in this location."
        emptyAction={
          <Link href="/trips/new">
            <Button variant="outline">Create a new trip</Button>
          </Link>
        }
      />
    );
  }

  const budgetTotal = {
    amountMinor: trip.budgetTotalMinor,
    currency: trip.baseCurrency,
  };

  const allocations: CategoryAllocation[] = trip.budgetAllocation?.allocations || [];
  const explanation = trip.budgetAllocation?.explanation;

  return (
    <div className="py-4 pb-28">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full">
            Step 2 • Budget Distribution & Spots
          </span>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight mt-3">
            Explore {destinationLabel}
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Review your budget allocation and select the attractions you&apos;d love to visit.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs bg-indigo-50 text-indigo-700 px-3 py-1.5 rounded-xl font-semibold border border-indigo-100">
            {selectedSpotIds.size} of {spots.length} selected
          </span>
        </div>
      </div>

      {/* Budget Allocation Panel */}
      {allocations.length > 0 && (
        <div className="mb-8">
          <BudgetBreakdown
            totalBudget={budgetTotal}
            allocations={allocations}
            explanation={explanation}
          />
        </div>
      )}

      {/* Spot Selection Section */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-slate-900">Must-Visit Spots</h3>
          <p className="text-xs text-slate-500 mt-0.5">Click any card to select/deselect it for your itinerary</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {spots.map((spot) => {
          const spotId = spot.providerRef.id || spot.name;
          const isSelected = selectedSpotIds.has(spotId);

          return (
            <SpotCard
              key={spotId}
              spot={spot}
              selectable
              selected={isSelected}
              onToggleSelect={() => toggleSpotSelection(spotId)}
            />
          );
        })}
      </div>

      {/* Sticky Bottom Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-slate-200/90 py-4 px-6 shadow-2xl">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold text-sm shadow-md shadow-indigo-200">
              {selectedSpotIds.size}
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900">
                {selectedSpotIds.size === 1 ? '1 Spot Selected' : `${selectedSpotIds.size} Spots Selected`}
              </p>
              <p className="text-xs text-slate-500">
                {trip.status === 'SPOTS_SELECTED' || selectionSuccess
                  ? '✓ Spot selections saved! Ready for Phase 3 (Flights)'
                  : 'Select at least 1 spot to continue'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {selectedSpotIds.size > 0 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedSpotIds(new Set())}
              >
                Clear
              </Button>
            )}

            <Button
              variant="primary"
              size="md"
              disabled={selectedSpotIds.size === 0}
              isLoading={isSubmittingSelection}
              onClick={handleContinue}
            >
              {trip.status === 'SPOTS_SELECTED' || selectionSuccess
                ? 'Update Selections ✓'
                : `Save & Continue (${selectedSpotIds.size}) →`}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
