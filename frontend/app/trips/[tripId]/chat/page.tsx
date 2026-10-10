'use client';

import React, { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { getTrip } from '../../../lib/api/trips';
import { TripResponse } from '../../../lib/api/schemas';
import { ChatBot } from '../../../components/trips/ChatBot';
import { Spinner } from '../../../components/ui/Spinner';
import { formatMoney } from '../../../lib/formatMoney';

export default function TripChatPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const resolvedParams = use(params);
  const tripId = resolvedParams.tripId;

  const [trip, setTrip] = useState<TripResponse | null>(null);
  const [loadingTrip, setLoadingTrip] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await getTrip(tripId);
        setTrip(data);
      } catch (err) {
        console.error('Failed to load trip', err);
      } finally {
        setLoadingTrip(false);
      }
    }
    load();
  }, [tripId]);

  if (loadingTrip) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
        <Spinner size="lg" />
        <p className="text-sm font-medium text-slate-500">Connecting to AI Concierge...</p>
      </div>
    );
  }

  // Get current step route to switch back to visual wizard
  const getVisualRoute = () => {
    if (!trip) return `/trips/${tripId}/summary`;
    switch (trip.status) {
      case 'DRAFT':
        return `/trips/${tripId}/destinations`;
      case 'DESTINATION_SELECTED':
        return `/trips/${tripId}/spots`;
      case 'BUDGET_ESTIMATED':
      case 'SPOTS_SELECTED':
        return `/trips/${tripId}/flights`;
      case 'FLIGHT_SELECTED':
        return `/trips/${tripId}/hotels`;
      case 'HOTEL_SELECTED':
      case 'SUMMARY_READY':
      default:
        return `/trips/${tripId}/summary`;
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Top Bar Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
              Conversational Mode
            </span>
            {trip?.status && (
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                Status: {trip.status}
              </span>
            )}
          </div>
          <h1 className="text-xl font-bold text-slate-900">
            {trip?.destinationCity ? `Trip to ${trip.destinationCity}` : 'Your Vacation Plan'}
          </h1>
          {typeof trip?.budgetTotalMinor === 'number' && trip.budgetTotalMinor > 0 && (
            <p className="text-xs text-slate-500 mt-0.5">
              Budget: {formatMoney({ amountMinor: trip.budgetTotalMinor, currency: trip.baseCurrency })} • {trip.travelers} traveler(s)
            </p>
          )}
        </div>

        <div className="flex items-center gap-3">
          <Link
            href={getVisualRoute()}
            className="px-4 py-2 text-xs font-bold rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 transition-all flex items-center gap-2"
          >
            <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"
              />
            </svg>
            <span>Switch to Visual Planner</span>
          </Link>
        </div>
      </div>

      {/* Main Chatbot Interface */}
      <ChatBot tripId={tripId} />
    </div>
  );
}
