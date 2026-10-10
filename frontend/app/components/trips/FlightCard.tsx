'use client';

import React from 'react';
import { FlightOption, FlightLeg } from '../../lib/api/schemas';
import { Button } from '../ui/Button';

interface FlightCardProps {
  flight: FlightOption;
  baseCurrency?: string;
  selected?: boolean;
  onSelect?: () => void;
  isSelecting?: boolean;
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

function formatTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr;
  }
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

function LegRow({ leg, label }: { leg: FlightLeg; label: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-100 last:border-b-0">
      <div className="flex items-center gap-3">
        <span className="text-[10px] uppercase font-bold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
          {label}
        </span>
        <div>
          <div className="text-sm font-semibold text-slate-800">
            {leg.airline} <span className="text-xs text-slate-500 font-normal">({leg.flightNumber})</span>
          </div>
          <div className="text-xs text-slate-500">
            {leg.departureAirport} → {leg.arrivalAirport}
          </div>
        </div>
      </div>

      <div className="text-right">
        <div className="text-xs font-bold text-slate-700">
          {formatTime(leg.departsAt)} – {formatTime(leg.arrivesAt)}
        </div>
      </div>
    </div>
  );
}

export function FlightCard({
  flight,
  baseCurrency = 'INR',
  selected = false,
  onSelect,
  isSelecting = false,
}: FlightCardProps) {
  const firstOutbound = flight.outbound[0];
  const airline = firstOutbound?.airline || 'Airline';
  const priceMinor = flight.price.amountMinor;
  const priceCurr = flight.price.currency;

  const convertedPrice = flight.convertedPrice || {
    amountMinor: priceMinor,
    currency: priceCurr,
  };

  const isCrossCurrency = priceCurr.toUpperCase() !== baseCurrency.toUpperCase();

  const stopsText = flight.stops === 0 ? 'Non-stop' : `${flight.stops} stop${flight.stops > 1 ? 's' : ''}`;

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
          Selected Flight
        </div>
      )}

      {/* Top Header */}
      <div>
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-sm">
              ✈️
            </div>
            <div>
              <h4 className="font-bold text-slate-900 text-base leading-tight">{airline}</h4>
              <span className="text-xs text-slate-500">
                Duration: {formatDuration(flight.totalDurationMinutes)}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                flight.stops === 0
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                  : 'bg-amber-50 text-amber-700 border border-amber-100'
              }`}
            >
              {stopsText}
            </span>
          </div>
        </div>

        {/* Flight Legs */}
        <div className="bg-slate-50/80 rounded-xl p-3 mb-4">
          {flight.outbound.map((leg, idx) => (
            <LegRow key={`out-${idx}`} leg={leg} label={flight.outbound.length > 1 ? `Leg ${idx + 1}` : 'Outbound'} />
          ))}
          {flight.inbound &&
            flight.inbound.map((leg, idx) => (
              <LegRow key={`in-${idx}`} leg={leg} label={flight.inbound.length > 1 ? `Return ${idx + 1}` : 'Return'} />
            ))}
        </div>
      </div>

      {/* Bottom Action / Price Bar */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-3">
        <div>
          <div className="text-lg font-extrabold text-slate-900 leading-none">
            {formatCurrency(convertedPrice.amountMinor, baseCurrency)}
          </div>
          {isCrossCurrency && (
            <div className="text-[11px] text-slate-500 mt-0.5">
              Original: {formatCurrency(priceMinor, priceCurr)}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {flight.providerRef?.deepLink && (
            <a
              href={flight.providerRef.deepLink}
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
              {selected ? 'Selected' : 'Select Flight'}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
