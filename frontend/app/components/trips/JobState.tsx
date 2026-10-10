import React from 'react';
import { Spinner } from '../ui/Spinner';
import { Button } from '../ui/Button';

interface JobStateProps {
  status: 'loading' | 'error' | 'empty';
  loadingMessage?: string;
  errorMessage?: string;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyMessage?: string;
  emptyAction?: React.ReactNode;
}

export const JobState: React.FC<JobStateProps> = ({
  status,
  loadingMessage = 'Gathering recommendations...',
  errorMessage = 'Something went wrong. Please try again.',
  onRetry,
  emptyTitle = 'No results found',
  emptyMessage = 'We could not find any matches for your criteria.',
  emptyAction,
}) => {
  if (status === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center py-20 px-4 text-center">
        <Spinner size="lg" className="text-indigo-600 mb-6" />
        <h3 className="text-lg font-semibold text-slate-800 mb-2">{loadingMessage}</h3>
        <p className="text-sm text-slate-500 max-w-sm">
          Analyzing live data and vibe matches. This might take a few moments.
        </p>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4 text-center max-w-md mx-auto">
        <div className="w-12 h-12 rounded-full bg-rose-100 flex items-center justify-center text-rose-600 mb-4 font-bold text-xl">
          !
        </div>
        <h3 className="text-lg font-semibold text-slate-900 mb-1">Unable to load data</h3>
        <p className="text-sm text-slate-600 mb-6">{errorMessage}</p>
        {onRetry && (
          <Button onClick={onRetry} variant="primary">
            Try Again
          </Button>
        )}
      </div>
    );
  }

  if (status === 'empty') {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4 text-center max-w-md mx-auto">
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-4 text-xl">
          🔍
        </div>
        <h3 className="text-lg font-semibold text-slate-900 mb-1">{emptyTitle}</h3>
        <p className="text-sm text-slate-500 mb-6">{emptyMessage}</p>
        {emptyAction}
      </div>
    );
  }

  return null;
};
