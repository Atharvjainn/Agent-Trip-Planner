'use client';

import React, { useState } from 'react';
import { VibeTags } from '../../lib/api/schemas';
import { createTripSchema, CreateTripFormData } from '../../lib/api/schemas';
import { Chip } from '../ui/Chip';
import { Button } from '../ui/Button';

interface TripFormProps {
  onSubmit: (data: CreateTripFormData) => Promise<void>;
  isLoading?: boolean;
}

export const TripForm: React.FC<TripFormProps> = ({ onSubmit, isLoading = false }) => {
  const today = new Date().toISOString().slice(0, 10);

  const [formData, setFormData] = useState<Partial<CreateTripFormData>>({
    source: '',
    destinationCity: '',
    destinationCountry: '',
    startDate: today,
    endDate: today,
    travelers: 1,
    budgetAmount: 50000,
    currency: 'INR',
    vibes: [],
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleVibeToggle = (vibe: string) => {
    setFormData((prev) => {
      const current = prev.vibes || [];
      const updated = current.includes(vibe)
        ? current.filter((v) => v !== vibe)
        : [...current, vibe];
      return { ...prev, vibes: updated };
    });
    if (errors.vibes) {
      setErrors((prev) => ({ ...prev, vibes: '' }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    const result = createTripSchema.safeParse({
      ...formData,
      budgetAmount: Number(formData.budgetAmount),
      travelers: Number(formData.travelers),
    });

    if (!result.success) {
      const newErrors: Record<string, string> = {};
      result.error.issues.forEach((issue) => {
        const field = issue.path[0] as string;
        if (field) {
          newErrors[field] = issue.message;
        }
      });
      setErrors(newErrors);
      return;
    }

    try {
      await onSubmit(result.data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create trip';
      setErrors({ form: msg });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl mx-auto bg-white p-8 rounded-3xl border border-slate-200/80 shadow-xl shadow-slate-100">
      {errors.form && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-sm text-rose-700">
          {errors.form}
        </div>
      )}

      {/* Source */}
      <div>
        <label className="block text-sm font-semibold text-slate-800 mb-1">
          Departure City / Airport <span className="text-rose-500">*</span>
        </label>
        <input
          type="text"
          placeholder="e.g. DEL, New Delhi, BOM, JFK"
          value={formData.source}
          onChange={(e) => setFormData({ ...formData, source: e.target.value })}
          className={`w-full px-4 py-3 rounded-xl border text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
            errors.source ? 'border-rose-400 bg-rose-50/20' : 'border-slate-200'
          }`}
        />
        <p className="text-xs text-slate-400 mt-1">City name or 3-letter IATA code</p>
        {errors.source && <p className="text-xs text-rose-500 mt-1">{errors.source}</p>}
      </div>

      {/* Destination (Optional pair) */}
      <div className="p-5 rounded-2xl bg-slate-50/80 border border-slate-100 space-y-4">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-semibold text-slate-800">
            Destination (Optional)
          </label>
          <span className="text-xs text-indigo-600 font-medium">
            Leave blank for AI recommendations
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <input
              type="text"
              placeholder="City (e.g. Tokyo)"
              value={formData.destinationCity}
              onChange={(e) =>
                setFormData({ ...formData, destinationCity: e.target.value })
              }
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm bg-white text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <input
              type="text"
              placeholder="Country (e.g. Japan)"
              value={formData.destinationCountry}
              onChange={(e) =>
                setFormData({ ...formData, destinationCountry: e.target.value })
              }
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm bg-white text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
        {errors.destinationCity && (
          <p className="text-xs text-rose-500">{errors.destinationCity}</p>
        )}
      </div>

      {/* Dates & Travelers */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-semibold text-slate-800 mb-1">
            Start Date <span className="text-rose-500">*</span>
          </label>
          <input
            type="date"
            value={formData.startDate}
            min={today}
            onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
            className={`w-full px-4 py-2.5 rounded-xl border text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
              errors.startDate ? 'border-rose-400 bg-rose-50/20' : 'border-slate-200'
            }`}
          />
          {errors.startDate && (
            <p className="text-xs text-rose-500 mt-1">{errors.startDate}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-semibold text-slate-800 mb-1">
            End Date <span className="text-rose-500">*</span>
          </label>
          <input
            type="date"
            value={formData.endDate}
            min={formData.startDate || today}
            onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
            className={`w-full px-4 py-2.5 rounded-xl border text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
              errors.endDate ? 'border-rose-400 bg-rose-50/20' : 'border-slate-200'
            }`}
          />
          {errors.endDate && (
            <p className="text-xs text-rose-500 mt-1">{errors.endDate}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-semibold text-slate-800 mb-1">
            Travelers
          </label>
          <input
            type="number"
            min={1}
            max={20}
            value={formData.travelers}
            onChange={(e) =>
              setFormData({ ...formData, travelers: Number(e.target.value) })
            }
            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      {/* Budget & Currency */}
      <div>
        <label className="block text-sm font-semibold text-slate-800 mb-1">
          Total Budget <span className="text-rose-500">*</span>
        </label>
        <div className="flex gap-3">
          <select
            value={formData.currency}
            onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
            className="px-3 py-2.5 rounded-xl border border-slate-200 text-sm font-medium bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="INR">INR (₹)</option>
            <option value="USD">USD ($)</option>
            <option value="EUR">EUR (€)</option>
            <option value="GBP">GBP (£)</option>
          </select>

          <input
            type="number"
            min={1}
            step={100}
            placeholder="e.g. 50000"
            value={formData.budgetAmount}
            onChange={(e) =>
              setFormData({ ...formData, budgetAmount: Number(e.target.value) })
            }
            className={`flex-1 px-4 py-2.5 rounded-xl border text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
              errors.budgetAmount ? 'border-rose-400 bg-rose-50/20' : 'border-slate-200'
            }`}
          />
        </div>
        {errors.budgetAmount && (
          <p className="text-xs text-rose-500 mt-1">{errors.budgetAmount}</p>
        )}
      </div>

      {/* Vibes multi-select */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-semibold text-slate-800">
            Trip Vibes <span className="text-rose-500">*</span>
          </label>
          <span className="text-xs text-slate-400">Select 1 or more</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {VibeTags.map((vibe) => {
            const isSelected = (formData.vibes || []).includes(vibe);
            return (
              <Chip
                key={vibe}
                label={vibe.replace('_', ' ')}
                selected={isSelected}
                onClick={() => handleVibeToggle(vibe)}
              />
            );
          })}
        </div>
        {errors.vibes && <p className="text-xs text-rose-500 mt-1">{errors.vibes}</p>}
      </div>

      {/* Submit Button */}
      <Button
        type="submit"
        variant="primary"
        size="lg"
        className="w-full mt-4"
        isLoading={isLoading}
      >
        Plan My Journey ✨
      </Button>
    </form>
  );
};
