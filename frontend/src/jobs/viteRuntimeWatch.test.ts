import assert from "node:assert/strict";
import test from "node:test";

import {
  BACKEND_RUNTIME_WATCH_IGNORES,
} from "../../vite.config";

test("vite ignores backend runtime files that change while jobs are running", () => {
  assert.deepEqual(BACKEND_RUNTIME_WATCH_IGNORES, [
    "**/node_modules/**",
    "**/.git/**",
    "**/dist/**",
    "**/backend/data/**",
    "**/backend/course_data/**",
    "**/backend/storage/**",
    "**/storage/**",
  ]);
});
