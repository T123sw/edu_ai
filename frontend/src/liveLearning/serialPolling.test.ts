import test from 'node:test';
import assert from 'node:assert/strict';
import { serialPolling } from './serialPolling';
test('slow polling never overlaps and unmount aborts without rescheduling', async () => {
  let calls = 0; let running = 0; let maximum = 0; let signal: AbortSignal;
  const stop = serialPolling(async current => {
    signal = current; calls++; running++; maximum = Math.max(maximum, running);
    await new Promise(resolve => setTimeout(resolve, 15)); running--;
  }, 1);
  await new Promise(resolve => setTimeout(resolve, 40)); stop();
  const atStop = calls; await new Promise(resolve => setTimeout(resolve, 35));
  assert.equal(maximum, 1); assert.equal(calls, atStop); assert.equal(signal!.aborted, true);
});
