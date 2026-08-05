import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(
  new URL("../../src/stitch/pages/CourseResources.tsx", import.meta.url),
  "utf8",
);

assert.match(page, /min-h-0/, "resource columns should be allowed to shrink inside the page");
assert.match(page, /min-w-0/, "resource preview should not force horizontal overflow");
assert.match(
  page,
  /<AppSurface className="flex min-h-screen xl:h-screen xl:overflow-hidden">/,
  "desktop resource workspace should stay within the viewport",
);
assert.match(
  page,
  /<main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-x-hidden xl:overflow-y-hidden">/,
  "main content should reject horizontal overflow",
);
assert.match(
  page,
  /xl:grid-cols-\[340px_minmax\(0,1fr\)\] xl:overflow-hidden/,
  "desktop resource list and preview should share the available width",
);
assert.match(
  page,
  /min-h-0 min-w-0 flex-1 space-y-3 overflow-y-auto pr-2/,
  "resource list should own its vertical scrolling",
);
assert.match(
  page,
  /mt-5 min-h-0 min-w-0 flex-1 overflow-y-auto pr-2/,
  "resource preview should own its vertical scrolling",
);
assert.doesNotMatch(page, /overflow-x-auto/, "resource center should not rely on horizontal scrolling");

console.log("courseResources scroll layout tests passed");
