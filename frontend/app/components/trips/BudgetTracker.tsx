'use client';

import React, { useState, useEffect } from 'react';
import { getTripBudget } from '../../lib/api/trips';

interface BudgetTrackerProps {
  tripId: string;
  refreshKey?: number | string;
  className?: string;
}

const CATEGORY_ICONS: Record<string, string> = {
  flights: '✈️',
  stay: '🏨',
  local_commute: '🚕',
  food: '🍽️',
  activities: '🎟️',
  buffer: '🛡️',
};

const CATEGORY_NAMES: Record<string, string> = {
  flights: 'Flights',
  stay: 'Stay & Hotels',
  local_commute: 'Local Commute',
  food: 'Food & Dining',
  activities: 'Activities & Spots',
  buffer: 'Emergency Buffer',
};

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

export function BudgetTracker({ tripId, refreshKey, className = '' }: BudgetTrackerProps) {
  const [budgetData, setBudgetData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        const data = await getTripBudget(tripId);
        if (isMounted) {
          setBudgetData(data);
          setLoading(false);
        }
      } catch (err) {
        console.error('Failed to load trip budget tracker:', err);
        if (isMounted) setLoading(false);
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, [tripId, refreshKey]);

  if (loading || !budgetData) {
    return (
      <div className={`w-full bg-white/95 backdrop-blur-md border border-slate-200/80 rounded-2xl p-3.5 shadow-sm animate-pulse ${className}`}>
        <div className="flex items-center justify-between">
          <div className="h-4 w-32 bg-slate-200 rounded"></div>
          <div className="h-4 w-48 bg-slate-200 rounded"></div>
        </div>
      </div>
    );
  }

  const currency = budgetData.currency || 'INR';
  const totalBudgetMinor = budgetData.totalBudget?.amountMinor || 0;
  const totalSpentMinor = budgetData.totalSpent?.amountMinor || 0;
  const totalRemainingMinor = budgetData.totalRemaining?.amountMinor ?? (totalBudgetMinor - totalSpentMinor);
  const isOverBudget = budgetData.isOverBudget || totalSpentMinor > totalBudgetMinor;

  const spentPercent = totalBudgetMinor > 0 ? Math.min(100, Math.round((totalSpentMinor / totalBudgetMinor) * 100)) : 0;
  const trackerItems = budgetData.tracker || [];

  return (
    <div className={`w-full bg-white/95 backdrop-blur-md border border-slate-200/90 rounded-2xl shadow-md transition-all duration-200 ${className}`}>
      {/* Pinned Main Header Bar */}
      <div className="p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Left: Summary Numbers */}
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="flex h-3 w-3 relative">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isOverBudget ? 'bg-rose-400' : 'bg-emerald-400'}`}></span>
              <span className={`relative inline-flex rounded-full h-3 w-3 ${isOverBudget ? 'bg-rose-500' : 'bg-emerald-500'}`}></span>
            </span>
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Live Budget Tracker</span>
          </div>

          <div className="h-4 w-px bg-slate-200 hidden sm:block"></div>

          <div className="flex items-center gap-3">
            <div>
              <span className="text-[11px] font-medium text-slate-500 block">Total Budget</span>
              <span className="text-sm font-bold text-slate-900">{formatCurrency(totalBudgetMinor, currency)}</span>
            </div>
            <div className="text-slate-300">/</div>
            <div>
              <span className="text-[11px] font-medium text-slate-500 block">Spent So Far</span>
              <span className={`text-sm font-extrabold ${isOverBudget ? 'text-rose-600' : 'text-indigo-600'}`}>
                {formatCurrency(totalSpentMinor, currency)}
              </span>
            </div>
            <div className="text-slate-300">/</div>
            <div>
              <span className="text-[11px] font-medium text-slate-500 block">Remaining</span>
              <span className={`text-sm font-bold ${totalRemainingMinor < 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                {formatCurrency(totalRemainingMinor, currency)}
              </span>
            </div>
          </div>
        </div>

        {/* Right: Progress Bar & Toggle */}
        <div className="flex items-center gap-3 sm:w-64">
          <div className="flex-1">
            <div className="flex items-center justify-between text-[11px] font-semibold mb-1">
              <span className={isOverBudget ? 'text-rose-600' : 'text-slate-600'}>
                {spentPercent}% spent
              </span>
              {isOverBudget && (
                <span className="text-[10px] bg-rose-100 text-rose-700 font-bold px-1.5 py-0.5 rounded">
                  Over Budget
                </span>
              )}
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  isOverBudget ? 'bg-rose-500' : spentPercent > 80 ? 'bg-amber-500' : 'bg-indigo-600'
                }`}
                style={{ width: `${spentPercent}%` }}
              />
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1 shrink-0"
          >
            <span>{isExpanded ? 'Hide' : 'Details'}</span>
            <svg
              className={`w-3.5 h-3.5 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Expandable Category Breakdown Details */}
      {isExpanded && trackerItems.length > 0 && (
        <div className="border-t border-slate-100 p-4 bg-slate-50/70 rounded-b-2xl">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {trackerItems.map((item: any) => {
              const icon = CATEGORY_ICONS[item.category] || '📌';
              const name = CATEGORY_NAMES[item.category] || item.category;
              const isOver = item.isOverBudget;

              return (
                <div
                  key={item.category}
                  className={`p-2.5 rounded-xl border bg-white ${
                    isOver ? 'border-rose-300 bg-rose-50/40' : 'border-slate-200/80'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">{icon}</span>
                    {isOver && (
                      <span className="text-[9px] font-bold bg-rose-100 text-rose-700 px-1 py-0.2 rounded">
                        Over
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] font-semibold text-slate-800 truncate" title={name}>
                    {name}
                  </div>
                  <div className="mt-1 text-xs">
                    <div className="text-slate-500 text-[10px]">Spent</div>
                    <div className={`font-bold ${isOver ? 'text-rose-600' : 'text-slate-900'}`}>
                      {formatCurrency(item.spentMinor, currency)}
                    </div>
                  </div>
                  <div className="mt-0.5 text-[10px] text-slate-400">
                    of {formatCurrency(item.allocatedMinor, currency)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
