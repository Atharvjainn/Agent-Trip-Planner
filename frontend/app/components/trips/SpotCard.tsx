import React from 'react';
import { SpotOption } from '../../lib/api/schemas';
import { Chip } from '../ui/Chip';

interface SpotCardProps {
  spot: SpotOption;
}

export const SpotCard: React.FC<SpotCardProps> = ({ spot }) => {
  // Sort vibes by score descending and take top 3
  const sortedVibes = [...spot.vibeScores]
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm hover:shadow-md transition-all duration-200 flex flex-col justify-between h-full">
      <div>
        <div className="flex items-start justify-between gap-2 mb-2">
          <h4 className="text-base font-bold text-slate-900 leading-snug">
            {spot.name}
          </h4>
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
            className="text-indigo-600 font-medium hover:underline inline-flex items-center gap-0.5"
          >
            View Place ↗
          </a>
        )}
      </div>
    </div>
  );
};
