import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(
  new URL("../../src/stitch/pages/CourseResources.tsx", import.meta.url),
  "utf8",
);
const presentation = readFileSync(
  new URL("../../src/stitch/api/courseMaterialPresentation.ts", import.meta.url),
  "utf8",
);

assert.match(page, /getCourseMaterialOpenTarget/, "resource cards should use the shared open-target contract");
assert.doesNotMatch(page, /routes\.video|去视频页/, "course resources must not use a generic video fallback");
assert.match(page, /重新加载/, "resource load failures should expose a retry action");
assert.match(presentation, /label:\s*"AI 课堂"/, "course resources should expose a classroom filter");
assert.match(presentation, /label:\s*"闪卡"/, "course resources should expose a flashcard filter");

console.log("courseResources material routing tests passed");
