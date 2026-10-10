import { fxService } from './fx.service';
import assert from 'node:assert';

async function runTests() {
  console.log('Running FX Service Unit Tests...');

  // Test 1: Same currency conversion returns identical amount and rate 1.0
  const same = await fxService.convert({ amountMinor: 500000, currency: 'INR' }, 'INR');
  assert.strictEqual(same.converted.amountMinor, 500000);
  assert.strictEqual(same.converted.currency, 'INR');
  assert.strictEqual(same.rate, 1.0);
  console.log('✓ Same currency conversion passed');

  // Test 2: Cross currency conversion returns integer minor units
  const cross = await fxService.convert({ amountMinor: 10000, currency: 'USD' }, 'INR');
  assert.strictEqual(Number.isInteger(cross.converted.amountMinor), true);
  assert.strictEqual(cross.converted.currency, 'INR');
  assert.strictEqual(cross.converted.amountMinor > 0, true);
  assert.strictEqual(cross.rate > 0, true);
  console.log(`✓ Cross currency conversion passed (100.00 USD -> ${cross.converted.amountMinor / 100} INR @ rate ${cross.rate})`);

  // Test 3: Zero amount conversion
  const zero = await fxService.convert({ amountMinor: 0, currency: 'EUR' }, 'USD');
  assert.strictEqual(zero.converted.amountMinor, 0);
  assert.strictEqual(zero.converted.currency, 'USD');
  console.log('✓ Zero amount conversion passed');

  console.log('✅ All FX Service Unit Tests Passed!\n');
}

runTests().catch((err) => {
  console.error('❌ FX Service Test Failed:', err);
  process.exit(1);
});
