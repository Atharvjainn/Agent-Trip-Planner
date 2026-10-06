import { tripRepository } from '../repositories/trip.repository';
import { NotFoundError } from '../lib/errors';
import { CategoryAllocation } from '../schemas/budget.schema';
import budgetCategoriesJson from '../shared/budget_categories.json';

const DEFAULT_SPLIT_DOMESTIC: Record<string, number> = {
  flights: 30,
  stay: 35,
  local_commute: 10,
  food: 12,
  activities: 8,
  buffer: 5,
};

const DEFAULT_SPLIT_INTERNATIONAL: Record<string, number> = {
  flights: 40,
  stay: 30,
  local_commute: 8,
  food: 10,
  activities: 7,
  buffer: 5,
};

export class BudgetService {
  /**
   * Calculates fallback budget split to exact minor integer units ensuring the sum strictly equals budgetTotalMinor.
   */
  calculateDefaultSplit(
    budgetTotalMinor: number,
    currency: string,
    isInternational = false
  ) {
    const percentages = isInternational ? DEFAULT_SPLIT_INTERNATIONAL : DEFAULT_SPLIT_DOMESTIC;
    const categories = budgetCategoriesJson.values;

    let allocatedTotal = 0;
    const allocations: CategoryAllocation[] = categories.map((cat, idx) => {
      const pct = percentages[cat] || 0;
      // For the last category, allocate whatever remains to ensure exact sum match
      const amountMinor =
        idx === categories.length - 1
          ? budgetTotalMinor - allocatedTotal
          : Math.floor((budgetTotalMinor * pct) / 100);

      allocatedTotal += amountMinor;
      return {
        category: cat as any,
        amount: {
          amountMinor,
          currency,
        },
      };
    });

    return {
      currency,
      allocations,
      explanation: 'Default split based on standard travel allocation rules.',
    };
  }

  async getTripBudget(tripId: string, userId: string) {
    const trip = await tripRepository.findByIdAndUser(tripId, userId);
    if (!trip) {
      throw new NotFoundError('Trip not found');
    }

    const rawAllocation = (trip as any).budgetAllocation;
    if (rawAllocation && typeof rawAllocation === 'object') {
      const stored = rawAllocation as any;
      const allocations: CategoryAllocation[] = Array.isArray(stored.allocations)
        ? stored.allocations
        : Array.isArray(stored)
        ? stored
        : [];

      if (allocations.length > 0) {
        return {
          tripId: trip.id,
          currency: stored.currency || trip.baseCurrency,
          totalBudget: {
            amountMinor: trip.budgetTotalMinor,
            currency: trip.baseCurrency,
          },
          allocations,
          explanation: stored.explanation || undefined,
        };
      }
    }

    const isInternational = Boolean(
      trip.destinationCountry &&
        !['india', 'in'].includes(trip.destinationCountry.toLowerCase().trim())
    );

    const fallback = this.calculateDefaultSplit(
      trip.budgetTotalMinor,
      trip.baseCurrency,
      isInternational
    );

    return {
      tripId: trip.id,
      currency: trip.baseCurrency,
      totalBudget: {
        amountMinor: trip.budgetTotalMinor,
        currency: trip.baseCurrency,
      },
      allocations: fallback.allocations,
      explanation: fallback.explanation,
    };
  }
}

export const budgetService = new BudgetService();
