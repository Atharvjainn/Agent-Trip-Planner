import { Money } from './api/schemas';

export function formatMoney(
  money: Money | { amountMinor: number; currency: string },
  options: { approximate?: boolean } = {}
): string {
  const { amountMinor, currency } = money;
  const majorUnits = amountMinor / 100;

  try {
    const formatted = new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currency.toUpperCase(),
      maximumFractionDigits: 2,
    }).format(majorUnits);

    return options.approximate ? `≈ ${formatted}` : formatted;
  } catch {
    // Fallback if currency code is unexpected
    const fallback = `${currency.toUpperCase()} ${majorUnits.toLocaleString()}`;
    return options.approximate ? `≈ ${fallback}` : fallback;
  }
}
