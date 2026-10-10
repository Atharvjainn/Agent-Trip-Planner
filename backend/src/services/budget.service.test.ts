import assert from 'node:assert';
import { budgetService } from './budget.service';
import budgetCategoriesJson from '../shared/budget_categories.json';

function runTests() {
  console.log('Running Budget Math Unit Tests...');

  // Test 1: Domestic budget split sums exactly to total budget
  const domesticTotal = 8000000; // 80,000.00 INR in minor
  const domesticResult = budgetService.calculateDefaultSplit(domesticTotal, 'INR', false);

  assert.strictEqual(domesticResult.currency, 'INR');
  assert.strictEqual(domesticResult.allocations.length, budgetCategoriesJson.values.length);

  const sumDomestic = domesticResult.allocations.reduce(
    (acc, item) => acc + item.amount.amountMinor,
    0
  );
  assert.strictEqual(
    sumDomestic,
    domesticTotal,
    `Domestic split sum (${sumDomestic}) must equal total (${domesticTotal})`
  );

  // Test 2: International budget split sums exactly to total budget
  const intlTotal = 15432199; // Odd minor amount
  const intlResult = budgetService.calculateDefaultSplit(intlTotal, 'USD', true);

  assert.strictEqual(intlResult.currency, 'USD');
  const sumIntl = intlResult.allocations.reduce(
    (acc, item) => acc + item.amount.amountMinor,
    0
  );
  assert.strictEqual(
    sumIntl,
    intlTotal,
    `International split sum (${sumIntl}) must equal total (${intlTotal})`
  );

  // Test 3: Check all categories exist
  const expectedCategories = new Set(budgetCategoriesJson.values);
  const actualCategories = new Set(domesticResult.allocations.map((a) => a.category));
  assert.deepStrictEqual(actualCategories, expectedCategories);

  console.log('✅ All Budget Math Unit Tests Passed!');
}

runTests();
