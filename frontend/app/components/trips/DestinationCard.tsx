import React from 'react';
import { DestinationOption } from '../../lib/api/schemas';
import { formatMoney } from '../../lib/formatMoney';
import { Button } from '../ui/Button';

interface DestinationCardProps {
  option: DestinationOption;
  onSelect: (option: DestinationOption) => void;
  isSelecting?: boolean;
}

export const DestinationCard: React.FC<DestinationCardProps> = ({
  option,
  onSelect,
  isSelecting = false,
}) => {
  const matchPercent = Math.round(option.vibeMatchScore * 100);

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm hover:shadow-md transition-all duration-200 flex flex-col justify-between">
      <div>
        <div className="flex items-start justify-between gap-2 mb-3">
          <div>
            <h3 className="text-xl font-bold text-slate-900 tracking-tight">
              {option.city}
            </h3>
            <p className="text-sm font-medium text-slate-500">{option.country}</p>
          </div>
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            {matchPercent}% match
          </span>
        </div>

        <p className="text-sm text-slate-600 mb-5 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100">
          &ldquo;{option.reason}&rdquo;
        </p>

        <div className="mb-6">
          <span className="text-xs text-slate-400 block mb-0.5">Est. Flight Price</span>
          <span className="text-lg font-bold text-slate-800">
            {formatMoney(option.estimatedFlightPrice, { approximate: true })}
          </span>
        </div>
      </div>

      <Button
        variant="primary"
        className="w-full"
        isLoading={isSelecting}
        onClick={() => onSelect(option)}
      >
        Choose {option.city}
      </Button>
    </div>
  );
};
