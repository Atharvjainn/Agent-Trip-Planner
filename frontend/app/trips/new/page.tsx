'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { TripForm } from '../../components/trips/TripForm';
import { createTrip } from '../../lib/api/trips';
import { CreateTripFormData } from '../../lib/api/schemas';

export default function NewTripPage() {
  const router = useRouter();
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
    <div className="py-6">
      <div className="text-center max-w-xl mx-auto mb-8">
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight sm:text-4xl">
          Where would you like to explore?
        </h1>
        <p className="mt-2 text-base text-slate-600">
          Enter your departure and preferences. We’ll curate destinations and attractions based on real-time flights and vibe matching.
        </p>
      </div>

      <TripForm onSubmit={handleSubmit} isLoading={isLoading} />
    </div>
  );
}
