'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { TripForm } from '../../components/trips/TripForm';
import { ChatBot } from '../../components/trips/ChatBot';
import { createTrip } from '../../lib/api/trips';
import { CreateTripFormData } from '../../lib/api/schemas';

export default function NewTripPage() {
  const router = useRouter();
  const [planningMode, setPlanningMode] = useState<'form' | 'chat'>('form');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (data: CreateTripFormData) => {
    setIsLoading(true);
    try {
      const result = await createTrip(data);
      if (result.status === 'DESTINATION_SELECTED') {
        router.push(`/trips/${result.tripId}/spots?jobId=${result.jobId}`);
      } else {
        router.push(`/trips/${result.tripId}/destinations?jobId=${result.jobId}`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="py-6 max-w-4xl mx-auto">
      <div className="text-center max-w-xl mx-auto mb-8">
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight sm:text-4xl">
          Where would you like to explore?
        </h1>
        <p className="mt-2 text-base text-slate-600">
          Plan and book your trip using our visual step-by-step wizard or chat directly with our AI travel assistant.
        </p>

        {/* Mode Selector */}
        <div className="mt-6 inline-flex p-1 bg-slate-100 rounded-2xl border border-slate-200">
          <button
            type="button"
            onClick={() => setPlanningMode('form')}
            className={`px-5 py-2 text-xs font-bold rounded-xl transition-all flex items-center gap-2 ${
              planningMode === 'form'
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <span>Guided Form Planner</span>
          </button>

          <button
            type="button"
            onClick={() => setPlanningMode('chat')}
            className={`px-5 py-2 text-xs font-bold rounded-xl transition-all flex items-center gap-2 ${
              planningMode === 'chat'
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
            <span>Conversational AI Planner</span>
          </button>
        </div>
      </div>

      {planningMode === 'form' ? (
        <TripForm onSubmit={handleSubmit} isLoading={isLoading} />
      ) : (
        <ChatBot
          onTripCreated={(newTripId) => {
            // Optional callback when conversation creates a trip
            console.log('Trip created via chat:', newTripId);
          }}
        />
      )}
    </div>
  );
}
