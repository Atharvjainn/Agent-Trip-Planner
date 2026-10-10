'use client';

import React, { useState, useEffect, useRef } from 'react';
import { updateStayBudget } from '../../lib/api/trips';

interface StayBudgetSliderProps {
  tripId: string;
  initialStayBudgetMinor: number;
  totalTripBudgetMinor: number;
  baseCurrency?: string;
  onBudgetChange?: (newBudgetMinor: number) => void;
}

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

export function StayBudgetSlider({
  tripId,
  initialStayBudgetMinor,
  totalTripBudgetMinor,
  baseCurrency = 'INR',
  onBudgetChange,
}: StayBudgetSliderProps) {
  const [stayBudget, setStayBudget] = useState(initialStayBudgetMinor);
  const [isUpdating, setIsUpdating] = useState(false);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    setStayBudget(initialStayBudgetMinor);
  }, [initialStayBudgetMinor]);

  const minBudget = Math.max(100000, Math.floor(totalTripBudgetMinor * 0.1)); // At least 10%
  const maxBudget = Math.floor(totalTripBudgetMinor * 0.8); // Up to 80%
  const step = 50000; // Step in 500 currency units (minor)

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setStayBudget(val);
    onBudgetChange?.(val);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(async () => {
      setIsUpdating(true);
      try {
        await updateStayBudget(tripId, val);
      } catch (err) {
        console.error('Failed to update stay budget on server:', err);
      } finally {
        setIsUpdating(false);
      }
    }, 400);
  };

  const percentage = totalTripBudgetMinor > 0 ? Math.round((stayBudget / totalTripBudgetMinor) * 100) : 0;

  return (
    <div className="bg-white/90 backdrop-blur-md border border-slate-200/90 rounded-2xl p-4 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-base">🏨</span>
          <div>
            <h4 className="text-sm font-bold text-slate-900">Stay Budget Allocation</h4>
            <p className="text-[11px] text-slate-500">Adjust the target budget allocated for your accommodation</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isUpdating && <span className="text-[10px] text-indigo-500 animate-pulse font-medium">Saving...</span>}
          <div className="text-right">
            <span className="text-sm font-extrabold text-indigo-600">
              {formatCurrency(stayBudget, baseCurrency)}
            </span>
            <span className="text-xs text-slate-400 ml-1">({percentage}% of total)</span>
          </div>
        </div>
      </div>

      {/* Slider input */}
      <div className="mt-3">
        <input
          type="range"
          min={minBudget}
          max={maxBudget}
          step={step}
          value={stayBudget}
          onChange={handleSliderChange}
          className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-400"
        />
        <div className="flex justify-between text-[10px] font-semibold text-slate-400 mt-1">
          <span>Min: {formatCurrency(minBudget, baseCurrency)}</span>
          <span>Max: {formatCurrency(maxBudget, baseCurrency)}</span>
        </div>
      </div>
    </div>
  );
}
