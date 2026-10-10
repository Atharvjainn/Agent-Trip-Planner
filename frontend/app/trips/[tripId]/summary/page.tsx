'use client';

import React, { useEffect, useState, useCallback, use } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { getTripSummary, buildTripSummary } from '../../../lib/api/trips';
import { FullSummaryResponse } from '../../../lib/api/schemas';
import { useJob } from '../../../hooks/useJob';
import { BudgetTracker } from '../../../components/trips/BudgetTracker';
import { JobState } from '../../../components/trips/JobState';
import { Button } from '../../../components/ui/Button';

function formatCurrency(amountMinor: number, currency: string): string {
  const amount = amountMinor / 100;
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString()}`;
  }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

export default function TripSummaryPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const resolvedParams = use(params);
  const tripId = resolvedParams.tripId;
  const router = useRouter();
  const searchParams = useSearchParams();

  const [data, setData] = useState<FullSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const queryJobId = searchParams.get('jobId');
  const [activeJobId, setActiveJobId] = useState<string | null>(queryJobId);

  const fetchSummaryData = useCallback(async () => {
    try {
      setPageError(null);
      const res = await getTripSummary(tripId);
      setData(res);

      // If summary is missing and not already building, trigger build job
      if (!res.summary && !res.pendingJob) {
        if (!activeJobId) {
          try {
            const buildRes = await buildTripSummary(tripId);
            setActiveJobId(buildRes.jobId);
          } catch (e: any) {
            console.error('Failed to trigger build-summary:', e);
          }
        }
      } else if (res.pendingJob && !activeJobId) {
        setActiveJobId(res.pendingJob.id);
      }
    } catch (err: any) {
      console.error('Failed to load summary data:', err);
      setPageError(err.message || 'Failed to load trip summary');
    } finally {
      setLoading(false);
    }
  }, [tripId, activeJobId]);

  useEffect(() => {
    fetchSummaryData();
  }, [fetchSummaryData]);

  // Hook for polling active build-summary job
  const {
    status: jobStatus,
    error: jobError,
    retry: retryJob,
  } = useJob(activeJobId, {
    onCompleted: () => {
      fetchSummaryData();
    },
  });

  if (loading) {
    return (
      <JobState
        status="loading"
        loadingMessage="Generating your comprehensive trip summary & itinerary..."
      />
    );
  }

  if (pageError) {
    return (
      <JobState
        status="error"
        errorMessage={pageError}
        onRetry={fetchSummaryData}
      />
    );
  }

  if (!data?.summary && (jobStatus === 'active' || jobStatus === 'queued' || Boolean(activeJobId))) {
    return (
      <div className="py-4">
        <BudgetTracker tripId={tripId} className="mb-6 sticky top-4 z-20" />
        <JobState
          status="loading"
          loadingMessage={`Crafting your itinerary & estimating local commute for ${data?.trip?.destinationCity || 'your destination'}...`}
        />
      </div>
    );
  }

  if (!data?.summary && jobStatus === 'failed') {
    return (
      <div className="py-4">
        <BudgetTracker tripId={tripId} className="mb-6 sticky top-4 z-20" />
        <JobState
          status="error"
          errorMessage={jobError || "We couldn't generate the itinerary summary. Please try again."}
          onRetry={retryJob}
        />
      </div>
    );
  }

  const trip = data?.trip;
  const selections = data?.selections;
  const costs = data?.costs;
  const summary = data?.summary;
  const savings = data?.savingSuggestions || [];
  const baseCurrency = trip?.baseCurrency || 'INR';

  const flight = selections?.flight;
  const hotel = selections?.hotel;
  const spots = selections?.spots || [];

  const flightMeta = flight?.metadata as any;
  const hotelMeta = hotel?.metadata as any;

  const totalSpent = (costs?.flightSpentMinor || 0) + (costs?.hotelSpentMinor || 0) + (costs?.commuteSpentMinor || 0);
  const tripBudget = trip?.budgetTotalMinor || 1;
  const spentPercent = Math.min(100, Math.round((totalSpent / tripBudget) * 100));

  return (
    <div className="py-4 pb-28 max-w-5xl mx-auto">
      {/* Sticky Budget Tracker */}
      <BudgetTracker tripId={tripId} className="mb-6 sticky top-4 z-20" />

      {/* Header Banner */}
      <div className="bg-gradient-to-br from-indigo-900 via-indigo-800 to-slate-900 text-white rounded-3xl p-6 sm:p-8 shadow-xl mb-8 relative overflow-hidden">
        <div className="absolute right-0 top-0 translate-x-8 -translate-y-8 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider bg-white/10 backdrop-blur-md px-3.5 py-1.5 rounded-full border border-white/10 text-emerald-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Step 5 • Trip Summary & Final Itinerary
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={() => window.print()}
              className="text-xs font-semibold bg-white/10 hover:bg-white/20 text-white border border-white/20 px-3.5 py-2 rounded-xl transition-colors flex items-center gap-1.5"
            >
              <span>🖨️ Print / Save</span>
            </button>
            <Link
              href="/trips/new"
              className="text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white px-3.5 py-2 rounded-xl transition-colors shadow-sm"
            >
              + Plan New Trip
            </Link>
          </div>
        </div>

        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
          Trip to {trip?.destinationCity || 'Destination'}
        </h1>
        <p className="text-indigo-200 text-sm mt-2 flex flex-wrap items-center gap-3">
          <span>📅 {formatDate(trip?.startDate || '')} — {formatDate(trip?.endDate || '')}</span>
          <span>•</span>
          <span>🌙 {data?.nights} night{data?.nights && data.nights > 1 ? 's' : ''}</span>
          <span>•</span>
          <span>👥 {trip?.travelers} Traveler{trip?.travelers && trip.travelers > 1 ? 's' : ''}</span>
        </p>

        {/* AI Narrative Box */}
        {summary?.narrative && (
          <div className="mt-6 bg-white/10 backdrop-blur-md border border-white/15 rounded-2xl p-4 sm:p-5 text-sm leading-relaxed text-indigo-50 shadow-inner">
            <div className="flex items-center gap-2 text-indigo-300 text-xs font-bold uppercase tracking-wider mb-2">
              <span>✨ AI Itinerary Narrative</span>
            </div>
            <p>{summary.narrative}</p>
          </div>
        )}
      </div>

      {/* Grid: Flight & Hotel Selections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* Selected Flight Card */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm">
                ✈️
              </span>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Selected Flight</h3>
                <p className="text-[11px] text-slate-500">Transportation to destination</p>
              </div>
            </div>
            <span className="text-xs font-extrabold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-lg">
              {formatCurrency(costs?.flightSpentMinor || 0, baseCurrency)}
            </span>
          </div>

          {flight ? (
            <div className="mt-3 bg-slate-50 border border-slate-100 rounded-xl p-3.5 text-xs">
              <div className="flex items-center justify-between font-bold text-slate-800 mb-1">
                <span>{flight.providerName || 'Commercial Flight'}</span>
                {flightMeta?.outbound?.[0]?.flightNumber && (
                  <span className="text-[11px] text-slate-400 font-mono">
                    {flightMeta.outbound[0].flightNumber}
                  </span>
                )}
              </div>
              <div className="text-slate-500 flex items-center gap-1.5 mt-1">
                <span>Route:</span>
                <span className="font-semibold text-slate-700">
                  {flightMeta?.outbound?.[0]?.departureAirport || trip?.source} → {flightMeta?.outbound?.[0]?.arrivalAirport || trip?.destinationCity}
                </span>
              </div>
              {flight.deepLink && (
                <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex justify-end">
                  <a
                    href={flight.deepLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1"
                  >
                    <span>View Booking Provider</span>
                    <span>↗</span>
                  </a>
                </div>
              )}
            </div>
          ) : (
            <div className="mt-3 bg-slate-50 rounded-xl p-4 text-center text-xs text-slate-400">
              No flight selection recorded
            </div>
          )}
        </div>

        {/* Selected Hotel Card */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold text-sm">
                🏨
              </span>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Selected Stay</h3>
                <p className="text-[11px] text-slate-500">Accommodation for {data?.nights} nights</p>
              </div>
            </div>
            <span className="text-xs font-extrabold text-purple-600 bg-purple-50 px-2.5 py-1 rounded-lg">
              {formatCurrency(costs?.hotelSpentMinor || 0, baseCurrency)}
            </span>
          </div>

          {hotel ? (
            <div className="mt-3 bg-slate-50 border border-slate-100 rounded-xl p-3.5 text-xs">
              <div className="flex items-center justify-between font-bold text-slate-800 mb-1">
                <span className="truncate max-w-[200px]" title={hotel.providerName || ''}>
                  {hotel.providerName}
                </span>
                {hotelMeta?.rating && (
                  <span className="text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded text-[11px] font-bold">
                    ★ {hotelMeta.rating.toFixed(1)}
                  </span>
                )}
              </div>
              {hotelMeta?.pricePerNightConverted && (
                <div className="text-slate-500 mt-1">
                  Rate: <span className="font-semibold text-slate-700">{formatCurrency(hotelMeta.pricePerNightConverted.amountMinor, baseCurrency)}/night</span>
                </div>
              )}
              {hotel.deepLink && (
                <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex justify-end">
                  <a
                    href={hotel.deepLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-semibold text-purple-600 hover:text-purple-800 flex items-center gap-1"
                  >
                    <span>View Hotel Deep Link</span>
                    <span>↗</span>
                  </a>
                </div>
              )}
            </div>
          ) : (
            <div className="mt-3 bg-slate-50 rounded-xl p-4 text-center text-xs text-slate-400">
              No hotel selection recorded
            </div>
          )}
        </div>
      </div>

      {/* Local Commute Estimate Card */}
      {summary?.commute && (
        <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-sm mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2.5">
              <span className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-lg">
                🚕
              </span>
              <div>
                <h3 className="text-base font-bold text-slate-900">Estimated Local Commute</h3>
                <p className="text-xs text-slate-500">
                  Calculated based on distances between your hotel and {spots.length} selected spots
                </p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-400 block font-medium">Total Trip Commute</span>
              <span className="text-lg font-extrabold text-emerald-600">
                {formatCurrency(summary.commute.tripTotalCost.amountMinor, baseCurrency)}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-100 text-xs">
            <div>
              <span className="text-slate-400 block mb-0.5">Average Daily Distance</span>
              <span className="font-bold text-slate-800 text-sm">{summary.commute.dailyDistanceKm} km/day</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Daily Commute Cost</span>
              <span className="font-bold text-slate-800 text-sm">
                {formatCurrency(summary.commute.dailyCost.amountMinor, baseCurrency)}/day
              </span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Recommended Commute Mode</span>
              <span className="font-bold text-emerald-700 capitalize bg-emerald-100/60 px-2 py-0.5 rounded text-xs inline-block">
                {summary.commute.mode}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Selected Spots Grid */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-sm mb-8">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-lg">📍</span>
            <h3 className="text-base font-bold text-slate-900">
              Selected Spots & Attractions ({spots.length})
            </h3>
          </div>
          <Link
            href={`/trips/${tripId}/spots`}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
          >
            Edit Spots →
          </Link>
        </div>

        {spots.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {spots.map((spot, idx) => (
              <div
                key={spot.id || `spot-${idx}`}
                className="bg-slate-50 border border-slate-100 rounded-xl p-3 flex items-start gap-2.5"
              >
                <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                  {idx + 1}
                </span>
                <div>
                  <h4 className="text-xs font-bold text-slate-900 leading-snug">{spot.providerName}</h4>
                  <span className="text-[10px] text-slate-500 capitalize">Must-visit spot</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400">No spots selected.</p>
        )}
      </div>

      {/* Smart Cost-Saving Suggestions */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-sm mb-8">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg">💡</span>
          <h3 className="text-base font-bold text-slate-900">Cost-Saving Optimization</h3>
        </div>

        {savings.length > 0 ? (
          <div className="space-y-3">
            {savings.map((s, idx) => (
              <div
                key={s.strategyId || idx}
                className="bg-amber-50/60 border border-amber-200/80 rounded-xl p-3.5 text-xs flex items-start justify-between gap-3"
              >
                <div>
                  <h4 className="font-bold text-amber-900 text-sm mb-0.5">{s.title}</h4>
                  <p className="text-amber-800 text-xs">{s.description}</p>
                </div>
                <span className="font-extrabold text-emerald-700 text-xs bg-emerald-50 px-2.5 py-1 rounded-lg shrink-0">
                  Save {formatCurrency(s.estimatedSavings.amountMinor, s.estimatedSavings.currency)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 text-xs text-slate-500 flex items-center gap-2">
            <span>ℹ️</span>
            <span>
              Your selections are already well-optimized within your allocated budget. No additional cost-saving adjustments are necessary!
            </span>
          </div>
        )}
      </div>

      {/* Budget Distribution Summary Card */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 mb-4">Total Cost & Budget Utilization</h3>
        
        <div className="space-y-3 text-xs mb-4">
          <div className="flex justify-between items-center">
            <span className="text-slate-500">✈️ Flight Selection</span>
            <span className="font-bold text-slate-800">
              {formatCurrency(costs?.flightSpentMinor || 0, baseCurrency)}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-500">🏨 Hotel Accommodation ({data?.nights} nights)</span>
            <span className="font-bold text-slate-800">
              {formatCurrency(costs?.hotelSpentMinor || 0, baseCurrency)}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-500">🚕 Local Commute (Estimated)</span>
            <span className="font-bold text-slate-800">
              {formatCurrency(costs?.commuteSpentMinor || 0, baseCurrency)}
            </span>
          </div>
          <div className="pt-2 border-t border-slate-200 flex justify-between items-center font-bold text-sm">
            <span className="text-slate-900">Total Estimated Trip Cost</span>
            <span className="text-indigo-600">
              {formatCurrency(totalSpent, baseCurrency)}
            </span>
          </div>
          <div className="flex justify-between items-center text-xs">
            <span className="text-slate-500">Allocated Trip Budget</span>
            <span className="font-bold text-slate-700">
              {formatCurrency(trip?.budgetTotalMinor || 0, baseCurrency)}
            </span>
          </div>
          <div className="flex justify-between items-center text-xs font-semibold">
            <span className="text-slate-500">Remaining Budget Buffer</span>
            <span className={costs && costs.remainingMinor >= 0 ? 'text-emerald-600 font-bold' : 'text-red-500 font-bold'}>
              {formatCurrency(costs?.remainingMinor || 0, baseCurrency)}
            </span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-2.5 rounded-full ${
              spentPercent > 100 ? 'bg-red-500' : 'bg-indigo-600'
            }`}
            style={{ width: `${Math.min(100, spentPercent)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
