import assert from "node:assert/strict";
import test from "node:test";

import {
  parseRecentLearning,
  recordRecentLearning,
  serializeRecentLearning,
} from "./studentRecentLearning.ts";

test("recent learning keeps only the latest visited course", () => {
  const result = parseRecentLearning(JSON.stringify({
    version: 1,
    records: [
      { courseId: "c1", lastRoute: "student-ai", visitedAt: "2026-08-09T08:00:00.000Z" },
      { courseId: "c2", lastRoute: "student-resources", visitedAt: "2026-08-09T09:00:00.000Z" },
      { courseId: "c1", lastRoute: "student-classroom", visitedAt: "2026-08-09T10:00:00.000Z" },
    ],
  }), ["c1", "c2"]);

  assert.deepEqual(result.map((item) => [item.courseId, item.lastRoute]), [
    ["c1", "student-classroom"],
  ]);
});

test("recent learning removes missing courses, rejects unsafe routes, and keeps one", () => {
  const records = Array.from({ length: 8 }, (_, index) => ({
    courseId: `c${index}`,
    lastRoute: index === 0 ? "edit" : "student-ai",
    visitedAt: new Date(Date.UTC(2026, 7, 9, index)).toISOString(),
  }));
  const result = parseRecentLearning(JSON.stringify({ version: 1, records }), ["c1", "c2", "c3", "c4", "c5", "c6", "c7"]);
  assert.deepEqual(result.map((item) => item.courseId), ["c7"]);
  assert.equal(result.every((item) => item.lastRoute === "student-ai"), true);
});

test("recording a visit stores only the approved versioned fields", () => {
  const next = recordRecentLearning([], {
    courseId: " c1 ",
    lastRoute: "student-course-knowledge",
    visitedAt: "2026-08-09T10:00:00.000Z",
  });
  assert.equal(
    serializeRecentLearning(next),
    '{"version":1,"records":[{"courseId":"c1","lastRoute":"student-course-knowledge","visitedAt":"2026-08-09T10:00:00.000Z"}]}',
  );
});
