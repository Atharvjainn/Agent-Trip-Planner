import React from 'react';

interface ChipProps {
  label: string;
  selected?: boolean;
  onClick?: () => void;
  variant?: 'default' | 'vibe' | 'event';
  className?: string;
}

export const Chip: React.FC<ChipProps> = ({
  label,
  selected = false,
  onClick,
  variant = 'default',
  className = '',
}) => {
  const isClickable = Boolean(onClick);

  let style = 'bg-slate-100 text-slate-700 border-transparent';
  if (selected) {
    style = 'bg-indigo-600 text-white border-indigo-600 font-medium shadow-sm';
  } else if (variant === 'vibe') {
    style = 'bg-purple-50 text-purple-700 border-purple-200 text-xs';
  } else if (variant === 'event') {
    style = 'bg-amber-50 text-amber-800 border-amber-300 text-xs font-semibold';
  }

  return (
    <button
      type="button"
      disabled={!isClickable}
      onClick={onClick}
      className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs sm:text-sm border transition-all duration-150 ${style} ${
        isClickable ? 'cursor-pointer hover:opacity-90 active:scale-95' : 'cursor-default'
      } ${className}`}
    >
      {label}
    </button>
  );
};
