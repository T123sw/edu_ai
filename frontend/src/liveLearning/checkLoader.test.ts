import test from 'node:test';
import assert from 'node:assert/strict';
import { loadCheck } from './checkLoader';
test('large quiz loads at most three checks and a failure releases its slot', async () => {
  let running = 0; let maximum = 0;
  const jobs = Array.from({ length: 15 }, (_, i) => loadCheck(async () => {
    running++; maximum = Math.max(maximum, running);
    try {
      await new Promise(resolve => setTimeout(resolve, 2));
      if (i === 1) throw new Error('network unavailable');
      return i;
    } finally { running--; }
  }));
  const results = await Promise.allSettled(jobs);
  assert.equal(maximum, 3); assert.equal(running, 0);
  assert.equal(results.filter(r => r.status === 'fulfilled').length, 14);
  assert.equal(results[1].status, 'rejected');
  assert.equal(await loadCheck(async () => 'recovered'), 'recovered');
});
