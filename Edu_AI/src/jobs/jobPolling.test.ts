import assert from "node:assert/strict";
import test from "node:test";
import {
  JobLeaderLease,
  getJobPollDelay,
  type LeaseStorage,
} from "./jobPolling.ts";

class MemoryStorage implements LeaseStorage {
  values = new Map<string, string>();
  getItem(key: string) {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
  removeItem(key: string) {
    this.values.delete(key);
  }
}

test("poll delay follows visibility, status and bounded network backoff", () => {
  assert.equal(
    getJobPollDelay({ visible: true, hasRunning: true, hasQueued: false, failures: 0 }),
    2_000,
  );
  assert.equal(
    getJobPollDelay({ visible: true, hasRunning: false, hasQueued: true, failures: 0 }),
    3_000,
  );
  assert.equal(
    getJobPollDelay({ visible: false, hasRunning: true, hasQueued: false, failures: 0 }),
    8_000,
  );
  assert.deepEqual(
    [1, 2, 3, 4, 5, 8].map((failures) =>
      getJobPollDelay({
        visible: true,
        hasRunning: true,
        hasQueued: false,
        failures,
      }),
    ),
    [2_000, 4_000, 8_000, 15_000, 30_000, 30_000],
  );
  assert.equal(
    getJobPollDelay({ visible: true, hasRunning: false, hasQueued: false, failures: 0 }),
    null,
  );
});

test("only one tab owns the polling lease until it expires or releases", () => {
  const storage = new MemoryStorage();
  const first = new JobLeaderLease(storage, "tab-a", "lease", 10_000);
  const second = new JobLeaderLease(storage, "tab-b", "lease", 10_000);

  assert.equal(first.claim(1_000), true);
  assert.equal(second.claim(2_000), false);
  assert.equal(second.claim(11_001), true);
  assert.equal(first.claim(11_100), false);
  second.release();
  assert.equal(first.claim(11_200), true);
});
