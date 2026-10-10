'use client';

import React from 'react';
import { HotelOption } from '../../lib/api/schemas';
import { Button } from '../ui/Button';

interface HotelCardProps {
  hotel: HotelOption;
  baseCurrency?: string;
  nights?: number;
  selected?: boolean;
  onSelect?: () => void;
  isSelecting?: boolean;
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

export function HotelCard({
  hotel,
  baseCurrency = 'INR',
  nights = 1,
  selected = false,
  onSelect,
  isSelecting = false,
}: HotelCardProps) {
  const pricePerNightMinor = hotel.pricePerNight.amountMinor;
  const priceCurr = hotel.pricePerNight.currency;

  const convertedPerNight = hotel.convertedPricePerNight || {
    amountMinor: pricePerNightMinor,
    currency: priceCurr,
  };

  const totalPriceMinor = hotel.totalPrice?.amountMinor ?? convertedPerNight.amountMinor * nights;
  const isCrossCurrency = priceCurr.toUpperCase() !== baseCurrency.toUpperCase();
  const matchPercent = Math.round(hotel.score * 100);

  return (
    <div
      className={`rounded-2xl border transition-all duration-200 bg-white p-5 flex flex-col justify-between relative shadow-sm hover:shadow-md ${
        selected
          ? 'border-indigo-600 ring-2 ring-indigo-600/20 bg-indigo-50/20'
          : 'border-slate-200 hover:border-slate-300'
      }`}
    >
      {selected && (
        <div className="absolute -top-3 right-4 bg-indigo-600 text-white text-[11px] font-bold px-3 py-0.5 rounded-full shadow-sm flex items-center gap-1">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
          Selected Stay
        </div>
      )}

      {/* Top Header */}
      <div>
        <div className="flex items-start justify-between gap-3 mb-2">
          <div>
            <h4 className="font-bold text-slate-900 text-base leading-snug">{hotel.name}</h4>
            <div className="flex items-center gap-2 mt-1">
              {hotel.rating && (
                <span className="flex items-center text-xs font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-100">
                  ★ {hotel.rating.toFixed(1)}
                </span>
              )}
              <span className="text-[11px] font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-100">
                {matchPercent}% Match
              </span>
            </div>
          </div>
        </div>

        {/* Review snippet */}
        {hotel.reviewSnippet && (
          <p className="text-xs text-slate-600 italic bg-slate-50 p-2.5 rounded-xl border border-slate-100 mt-2 mb-3 line-clamp-2">
            &ldquo;{hotel.reviewSnippet}&rdquo;
          </p>
        )}

        {/* Distance to each selected spot */}
        {hotel.distances && hotel.distances.length > 0 && (
          <div className="mt-3 mb-4">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1.5">
              Distance to your spots
            </span>
            <div className="flex flex-wrap gap-1.5">
              {hotel.distances.map((dist, idx) => (
                <div
                  key={`${dist.spotId}-${idx}`}
                  className="flex items-center gap-1 bg-slate-50 border border-slate-200/80 px-2.5 py-1 rounded-lg text-xs"
                >
                  <span className="text-slate-400 text-[10px]">📍</span>
                  <span className="font-medium text-slate-700 max-w-[120px] truncate" title={dist.spotName}>
                    {dist.spotName}
                  </span>
                  <span className="font-bold text-slate-900 text-[11px]">
                    {dist.distanceKm} km
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Bottom Pricing & Actions */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-3">
        <div>
          <div className="flex items-baseline gap-1">
            <span className="text-lg font-extrabold text-slate-900">
              {formatCurrency(convertedPerNight.amountMinor, baseCurrency)}
            </span>
            <span className="text-xs text-slate-500 font-normal">/ night</span>
          </div>

          <div className="text-[11px] text-slate-500 mt-0.5">
            Total: <span className="font-bold text-slate-800">{formatCurrency(totalPriceMinor, baseCurrency)}</span> ({nights} night{nights > 1 ? 's' : ''})
            {isCrossCurrency && (
              <span className="block text-[10px] text-slate-400">
                Original: {formatCurrency(pricePerNightMinor, priceCurr)}/nt
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hotel.providerRef?.deepLink && (
            <a
              href={hotel.providerRef.deepLink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-slate-500 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 px-3 py-2 rounded-xl font-semibold transition-colors flex items-center gap-1"
            >
              <span>View</span>
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                />
              </svg>
            </a>
          )}

          {onSelect && (
            <Button
              variant={selected ? 'secondary' : 'primary'}
              size="sm"
              onClick={onSelect}
              isLoading={isSelecting}
              className={selected ? 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100' : ''}
            >
              {selected ? 'Selected' : 'Select Stay'}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
