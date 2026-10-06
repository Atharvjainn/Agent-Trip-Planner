import React from 'react';
import { CategoryAllocation, Money } from '../../lib/api/schemas';
import { formatMoney } from '../../lib/formatMoney';

interface BudgetBreakdownProps {
  totalBudget: Money;
  allocations: CategoryAllocation[];
  explanation?: string;
  className?: string;
}

const CATEGORY_META: Record<string, { label: string; icon: string; color: string }> = {
  flights: { label: 'Flights', icon: '✈️', color: 'bg-blue-500' },
  stay: { label: 'Stay / Hotel', icon: '🏨', color: 'bg-indigo-500' },
  local_commute: { label: 'Local Commute', icon: '🚕', color: 'bg-amber-500' },
  food: { label: 'Food & Dining', icon: '🍜', color: 'bg-emerald-500' },
  activities: { label: 'Activities & Sightseeing', icon: '🎟️', color: 'bg-purple-500' },
  buffer: { label: 'Safety Buffer', icon: '🛡️', color: 'bg-slate-500' },
};

export const BudgetBreakdown: React.FC<BudgetBreakdownProps> = ({
  totalBudget,
  allocations,
  explanation,
  className = '',
}) => {
  const totalMinor = totalBudget.amountMinor || 1;

  return (
    <div className={`bg-white rounded-3xl border border-slate-200/90 p-6 sm:p-7 shadow-sm ${className}`}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full">
            Smart Budget Distribution
          </span>
          <h3 className="text-xl font-bold text-slate-900 mt-2">
            Estimated Trip Budget: {formatMoney(totalBudget)}
          </h3>
        </div>
        <div className="text-xs text-slate-500 max-w-xs text-left sm:text-right">
          Automatically calibrated to destination prices and selected vibes.
        </div>
      </div>

      {/* Progress Multi-Bar */}
      <div className="w-full h-3.5 bg-slate-100 rounded-full overflow-hidden flex gap-0.5 mb-6">
        {allocations.map((item) => {
          const meta = CATEGORY_META[item.category] || { color: 'bg-slate-400' };
          const pct = Math.round((item.amount.amountMinor / totalMinor) * 100);
          if (pct === 0) return null;
          return (
            <div
              key={item.category}
              style={{ width: `${pct}%` }}
              className={`${meta.color} transition-all duration-300`}
              title={`${item.category}: ${pct}%`}
            />
          );
        })}
      </div>

      {/* Grid of Categories */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {allocations.map((item) => {
          const meta = CATEGORY_META[item.category] || {
            label: item.category,
            icon: '📌',
            color: 'bg-slate-400',
          };
          const pct = Math.round((item.amount.amountMinor / totalMinor) * 100);

          return (
            <div
              key={item.category}
              className="bg-slate-50/80 border border-slate-100 p-3.5 rounded-2xl flex flex-col justify-between"
            >
              <div className="flex items-center justify-between gap-1 mb-2">
                <span className="text-lg">{meta.icon}</span>
                <span className="text-xs font-bold text-slate-500 bg-white px-2 py-0.5 rounded-md border border-slate-200/60">
                  {pct}%
                </span>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-600 truncate">{meta.label}</p>
                <p className="text-sm font-bold text-slate-900 mt-0.5">
                  {formatMoney(item.amount)}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Explanation Banner */}
      {explanation && (
        <div className="mt-5 p-3.5 bg-indigo-50/50 border border-indigo-100/80 rounded-2xl flex items-start gap-2.5 text-xs text-indigo-900/90 leading-relaxed">
          <span className="text-sm">💡</span>
          <span>{explanation}</span>
        </div>
      )}
    </div>
  );
};
