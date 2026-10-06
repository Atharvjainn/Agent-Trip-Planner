import React from 'react';
import { SpotOption } from '../../lib/api/schemas';
import { Chip } from '../ui/Chip';

interface SpotCardProps {
  spot: SpotOption;
  selectable?: boolean;
  selected?: boolean;
  onToggleSelect?: () => void;
}

export const SpotCard: React.FC<SpotCardProps> = ({
  spot,
  selectable = false,
  selected = false,
  onToggleSelect,
}) => {
  // Sort vibes by score descending and take top 3
  const sortedVibes = [...spot.vibeScores]
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);

  return (
    <div
      onClick={selectable ? onToggleSelect : undefined}
      className={`rounded-2xl border p-5 transition-all duration-200 flex flex-col justify-between h-full relative ${
        selectable ? 'cursor-pointer' : ''
      } ${
        selected
          ? 'bg-indigo-50/40 border-indigo-600 shadow-md ring-2 ring-indigo-500/20'
          : 'bg-white border-slate-200/80 shadow-sm hover:shadow-md hover:border-slate-300'
      }`}
    >
      <div>
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            {selectable && (
              <div
                className={`w-5 h-5 rounded-md flex items-center justify-center border transition-all ${
                  selected
                    ? 'bg-indigo-600 border-indigo-600 text-white'
                    : 'bg-white border-slate-300'
                }`}
              >
                {selected && (
                  <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                )}
              </div>
            )}
            <h4 className="text-base font-bold text-slate-900 leading-snug">
              {spot.name}
            </h4>
          </div>

          {spot.rating != null && (
            <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200 shrink-0">
              ★ {spot.rating.toFixed(1)}
            </span>
          )}
        </div>

        {spot.matchingEvent && (
          <div className="mb-3">
            <Chip
              variant="event"
              label={`🎉 Event: ${spot.matchingEvent.name}${
                spot.matchingEvent.date ? ` (${spot.matchingEvent.date})` : ''
              }`}
            />
          </div>
        )}

        <div className="flex flex-wrap gap-1.5 mt-3 mb-4">
          {sortedVibes.map((v) => (
            <Chip key={v.vibe} variant="vibe" label={`#${v.vibe}`} />
          ))}
        </div>
      </div>

      <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
        <span>Provider: Google Maps</span>
        {spot.providerRef.deepLink && (
          <a
            href={spot.providerRef.deepLink}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-indigo-600 font-medium hover:underline inline-flex items-center gap-0.5"
          >
            View Place ↗
          </a>
        )}
      </div>
    </div>
  );
};
