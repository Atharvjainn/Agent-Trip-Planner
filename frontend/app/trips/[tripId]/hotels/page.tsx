'use client';

import React, { useEffect, useState, useCallback, use } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { getTrip, getHotelOptions, selectHotel, searchHotels } from '../../../lib/api/trips';
import { TripResponse, HotelOption } from '../../../lib/api/schemas';
import { useJob } from '../../../hooks/useJob';
import { HotelCard } from '../../../components/trips/HotelCard';
import { StayBudgetSlider } from '../../../components/trips/StayBudgetSlider';
import { BudgetTracker } from '../../../components/trips/BudgetTracker';
import { JobState } from '../../../components/trips/JobState';
import { Button } from '../../../components/ui/Button';

export default function HotelsPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const resolvedParams = use(params);
  const tripId = resolvedParams.tripId;
  const router = useRouter();
  const searchParams = useSearchParams();

  const [trip, setTrip] = useState<TripResponse | null>(null);
  const [hotelOptions, setHotelOptions] = useState<HotelOption[]>([]);
  const [selectedHotel, setSelectedHotel] = useState<any | null>(null);
  const [stayBudgetMinor, setStayBudgetMinor] = useState<number>(0);
  const [nights, setNights] = useState<number>(1);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const [selectingHotelId, setSelectingHotelId] = useState<string | null>(null);
  const [trackerRefreshKey, setTrackerRefreshKey] = useState(0);

  // Client-side Slider filter & Sort controls
  const [clientMaxStayBudget, setClientMaxStayBudget] = useState<number | null>(null);
  const [sortBy, setSortBy] = useState<'score' | 'price' | 'distance'>('score');

  const queryJobId = searchParams.get('jobId');
  const [activeJobId, setActiveJobId] = useState<string | null>(queryJobId);

  const fetchHotelData = useCallback(async () => {
    try {
      setPageError(null);
      const tripData = await getTrip(tripId);
      setTrip(tripData);

      // Route guard: if no destination, redirect to destinations
      if (tripData.status === 'DRAFT') {
        router.replace(`/trips/${tripId}/destinations`);
        return;
      }

      const hotelsData = await getHotelOptions(tripId);
      setHotelOptions(hotelsData.options || []);
      setSelectedHotel(hotelsData.selectedHotel || null);
      setNights(hotelsData.nights || 1);
      setStayBudgetMinor(hotelsData.stayBudgetMinor || Math.floor(tripData.budgetTotalMinor * 0.35));

      if ((!hotelsData.options || hotelsData.options.length === 0) && hotelsData.pendingJob) {
        setActiveJobId(hotelsData.pendingJob.id);
      } else if (!hotelsData.options || hotelsData.options.length === 0) {
        if (!activeJobId) {
          try {
            const res = await searchHotels(tripId);
            setActiveJobId(res.jobId);
          } catch (e: any) {
            console.error('Failed to trigger hotel search:', e);
          }
        }
      }
    } catch (err: any) {
      console.error('Failed to load hotel page data:', err);
      setPageError(err.message || 'Failed to load hotel options');
    } finally {
      setLoading(false);
    }
  }, [tripId, router, activeJobId]);

  useEffect(() => {
    fetchHotelData();
  }, [fetchHotelData]);

  // Hook for polling active search-hotels job
  const {
    status: jobStatus,
    error: jobError,
    retry: retryJob,
  } = useJob(activeJobId, {
    onCompleted: () => {
      fetchHotelData();
    },
  });

  const handleSelectHotel = async (hotel: HotelOption) => {
    const hotelId = hotel.providerRef.id || hotel.name;
    setSelectingHotelId(hotelId);
    try {
      const res = await selectHotel(tripId, hotel);
      setSelectedHotel({
        providerId: hotelId,
        providerName: hotel.name,
      });
      setTrackerRefreshKey((prev) => prev + 1);
      // Advance to Summary / Savings step
      const nextUrl = res.buildSummaryJobId
        ? `/trips/${tripId}/summary?jobId=${res.buildSummaryJobId}`
        : `/trips/${tripId}/summary`;
      router.push(nextUrl);
    } catch (err: any) {
      alert(err.message || 'Failed to save hotel selection');
    } finally {
      setSelectingHotelId(null);
    }
  };

  if (loading) {
    return (
      <JobState
        status="loading"
        loadingMessage="Finding hotels near your spots..."
      />
    );
  }

  if (pageError) {
    return (
      <JobState
        status="error"
        errorMessage={pageError}
        onRetry={fetchHotelData}
      />
    );
  }

  // Active Job state
  if (hotelOptions.length === 0 && (jobStatus === 'active' || jobStatus === 'queued' || Boolean(activeJobId))) {
    return (
      <div className="py-4">
        <BudgetTracker tripId={tripId} refreshKey={trackerRefreshKey} className="mb-6 sticky top-4 z-20" />
        <JobState
          status="loading"
          loadingMessage={`Finding the best hotels in ${trip?.destinationCity || 'your destination'} scored by distance to your spots...`}
        />
      </div>
    );
  }

  if (hotelOptions.length === 0 && jobStatus === 'failed') {
    return (
      <div className="py-4">
        <BudgetTracker tripId={tripId} refreshKey={trackerRefreshKey} className="mb-6 sticky top-4 z-20" />
        <JobState
          status="error"
          errorMessage={jobError || "We couldn't fetch hotels for your selected spots. Please try again."}
          onRetry={retryJob}
        />
      </div>
    );
  }

  // Client-side filtering by Stay Budget slider only when explicitly adjusted by user
  let displayOptions = [...hotelOptions];

  if (clientMaxStayBudget !== null && clientMaxStayBudget > 0) {
    displayOptions = displayOptions.filter((h) => {
      const total = h.totalPrice?.amountMinor ?? (h.pricePerNight.amountMinor * nights);
      return total <= clientMaxStayBudget * 1.25; // 25% tolerance for slider filtering
    });
  }

  displayOptions.sort((a, b) => {
    if (sortBy === 'price') {
      const priceA = a.totalPrice?.amountMinor ?? a.pricePerNight.amountMinor * nights;
      const priceB = b.totalPrice?.amountMinor ?? b.pricePerNight.amountMinor * nights;
      return priceA - priceB;
    }
    if (sortBy === 'distance') {
      const avgDistA = a.distances.length > 0
        ? a.distances.reduce((sum, d) => sum + d.distanceKm, 0) / a.distances.length
        : 999;
      const avgDistB = b.distances.length > 0
        ? b.distances.reduce((sum, d) => sum + d.distanceKm, 0) / b.distances.length
        : 999;
      return avgDistA - avgDistB;
    }
    return b.score - a.score;
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
            Step 4 • Select Stay & Accommodation
          </span>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight mt-3">
            Hotels in {trip?.destinationCity || 'Destination'}
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Hotels ranked by proximity to your selected spots for {nights} night{nights > 1 ? 's' : ''}.
          </p>
        </div>

        {/* Sort Controls */}
        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="text-xs font-semibold bg-white text-slate-700 border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="score">Sort: Best Match Score</option>
            <option value="price">Sort: Lowest Total Price</option>
            <option value="distance">Sort: Closest to Spots</option>
          </select>
        </div>
      </div>

      {/* Stay Budget Slider Panel */}
      <div className="mb-6">
        <StayBudgetSlider
          tripId={tripId}
          initialStayBudgetMinor={stayBudgetMinor}
          totalTripBudgetMinor={trip?.budgetTotalMinor || stayBudgetMinor * 3}
          baseCurrency={baseCurrency}
          onBudgetChange={(newVal) => {
            setClientMaxStayBudget(newVal);
            setTrackerRefreshKey((prev) => prev + 1);
          }}
        />
      </div>

      {/* Empty State */}
      {displayOptions.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center max-w-lg mx-auto">
          <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl mx-auto mb-3">
            🏨
          </div>
          <h3 className="text-base font-bold text-slate-900 mb-1">
            {hotelOptions.length > 0
              ? 'No hotels match the current slider budget'
              : 'No hotels found'}
          </h3>
          <p className="text-xs text-slate-500 mb-6">
            {hotelOptions.length > 0
              ? `There are ${hotelOptions.length} hotel options available above this budget range. Try adjusting or resetting the slider.`
              : `We couldn't find hotel options for this destination. Try searching again.`}
          </p>
          {hotelOptions.length > 0 && clientMaxStayBudget !== null ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setClientMaxStayBudget(null)}
            >
              Show all {hotelOptions.length} hotels
            </Button>
          ) : hotelOptions.length === 0 ? (
            <Button
              variant="primary"
              size="sm"
              onClick={async () => {
                const res = await searchHotels(tripId);
                setActiveJobId(res.jobId);
              }}
            >
              Search Hotels Again
            </Button>
          ) : null}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {displayOptions.map((hotel, idx) => {
            const hotelId = hotel.providerRef.id || hotel.name || `hotel-${idx}`;
            const isSelected = selectedHotel
              ? hotelId === selectedHotel.providerId || hotel.isSelected
              : false;

            return (
              <HotelCard
                key={hotelId}
                hotel={hotel}
                baseCurrency={baseCurrency}
                nights={nights}
                selected={isSelected}
                isSelecting={selectingHotelId === hotelId}
                onSelect={() => handleSelectHotel(hotel)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
