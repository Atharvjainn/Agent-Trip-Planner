export interface Money {
  amountMinor: number;
  currency: string;
}

export const MAX_BUDGET_MINOR = 2_000_000_000; // 20M in major units

export function toMinorUnits(amountMajor: number, currency = 'INR'): Money {
  if (amountMajor <= 0) {
    throw new Error('Budget amount must be a positive number');
  }
  const amountMinor = Math.round(amountMajor * 100);
  if (amountMinor > MAX_BUDGET_MINOR) {
    throw new Error(`Budget cannot exceed ${MAX_BUDGET_MINOR / 100} in major units`);
  }
  return {
    amountMinor,
    currency: currency.toUpperCase(),
  };
}

export function fromMinorUnits(money: Money): number {
  return money.amountMinor / 100;
}
