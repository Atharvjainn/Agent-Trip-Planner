'use client';

import React, { useEffect, useState, useCallback, use } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { getTrip, selectDestination } from '../../../lib/api/trips';
import { TripResponse, DestinationOption } from '../../../lib/api/schemas';
import { getExpectedRouteForStatus } from '../../../lib/trip-steps';
import { useJob } from '../../../hooks/useJob';
import { DestinationCard } from '../../../components/trips/DestinationCard';
import { JobState } from '../../../components/trips/JobState';
import { Button } from '../../../components/ui/Button';

export default function DestinationsPage({
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
  const [selectingCity, setSelectingCity] = useState<string | null>(null);

  const queryJobId = searchParams.get('jobId');
  const [activeJobId, setActiveJobId] = useState<string | null>(queryJobId);

  const fetchTrip = useCallback(async () => {
    try {
      setTripError(null);
      const data = await getTrip(tripId);
      setTrip(data);

      // Status check / redirect guard
      if (data.status !== 'DRAFT') {
        const expected = getExpectedRouteForStatus(tripId, data.status);
        if (expected !== `/trips/${tripId}/destinations`) {
          router.replace(expected);
          return;
        }
      }

      if (!data.destinationOptions && data.pendingJob) {
        setActiveJobId(data.pendingJob.id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load trip details';
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

        if (data.status !== 'DRAFT') {
          const expected = getExpectedRouteForStatus(tripId, data.status);
          if (expected !== `/trips/${tripId}/destinations`) {
            router.replace(expected);
            return;
          }
        }

        if (!data.destinationOptions && data.pendingJob) {
          setActiveJobId(data.pendingJob.id);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : 'Failed to load trip details';
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
    !trip?.destinationOptions ? activeJobId : null,
    {
      onCompleted: () => {
        fetchTrip();
      },
    }
  );

  const handleSelectDestination = async (option: DestinationOption) => {
    setSelectingCity(option.city);
    try {
      const res = await selectDestination(tripId, {
        city: option.city,
        country: option.country,
      });
      router.push(`/trips/${tripId}/spots?jobId=${res.jobId}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to select destination';
      alert(msg);
    } finally {
      setSelectingCity(null);
    }
  };

  if (loadingTrip) {
    return (
      <JobState
        status="loading"
        loadingMessage="Loading your trip plan..."
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

  // If job is in progress or failed
  if (!trip?.destinationOptions) {
    if (jobStatus === 'failed') {
      return (
        <JobState
          status="error"
          errorMessage={jobError || "We couldn't fetch recommendations. Please try again."}
          onRetry={retryJob}
        />
      );
    }

    return (
      <JobState
        status="loading"
        loadingMessage="Finding destinations that match your vibe..."
      />
    );
  }

  const options = trip.destinationOptions;

  if (options.length === 0) {
    return (
      <JobState
        status="empty"
        emptyTitle="No matching destinations"
        emptyMessage="We couldn't find destinations matching all selected vibes and budget constraints."
        emptyAction={
          <Link href="/trips/new">
            <Button variant="outline">Try with different vibes</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="py-4">
      <div className="max-w-2xl mb-8">
        <span className="text-xs font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full">
          Step 1 • Pick a Destination
        </span>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight mt-3">
          Top destinations for your trip
        </h1>
        <p className="text-sm text-slate-600 mt-1">
          Ranked by flight affordability from <strong>{trip.source}</strong> and your vibe preferences.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {options.map((option) => (
          <DestinationCard
            key={`${option.city}-${option.country}`}
            option={option}
            onSelect={handleSelectDestination}
            isSelecting={selectingCity === option.city}
          />
        ))}
      </div>
    </div>
  );
}
