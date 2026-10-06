'use client';

import React, { useEffect, useState, useCallback, use } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { getTrip } from '../../../lib/api/trips';
import { TripResponse } from '../../../lib/api/schemas';
import { useJob } from '../../../hooks/useJob';
import { SpotCard } from '../../../components/trips/SpotCard';
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

      if (!data.spotOptions && data.pendingJob) {
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

        if (!data.spotOptions && data.pendingJob) {
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

  if (loadingTrip) {
    return (
      <JobState
        status="loading"
        loadingMessage="Loading trip attractions..."
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
        loadingMessage={`Finding the best spots in ${destinationLabel}...`}
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

  return (
    <div className="py-4">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full">
            Step 2 • Discover Spots
          </span>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight mt-3">
            Popular Spots in {destinationLabel}
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Curated attractions and events tailored to your vibe preferences.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs bg-slate-100 text-slate-600 px-3 py-1.5 rounded-xl font-medium">
            {spots.length} spots discovered
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {spots.map((spot) => (
          <SpotCard key={spot.providerRef.id || spot.name} spot={spot} />
        ))}
      </div>
    </div>
  );
}
