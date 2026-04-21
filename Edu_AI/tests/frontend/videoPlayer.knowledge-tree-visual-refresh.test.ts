import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../../src/stitch/pages/VideoPlayer.tsx", import.meta.url), "utf8");

assert.match(
  page,
  /function shouldShowStructureSummary\(/,
  "VideoPlayer should define a helper that suppresses duplicate node summaries",
);

assert.match(
  page,
  /const isRootNode = depth === 0;/,
  "VideoPlayer should treat the root node as a dedicated visual tier",
);

assert.match(
  page,
  /const isBranchNode = depth === 1;/,
  "VideoPlayer should treat first-level children as branch cards",
);

assert.match(
  page,
  /style=\{\{ marginLeft: depth > 0 \? `\$\{depth \* 12\}px` : "0px" \}\}/,
  "VideoPlayer should keep nested node indentation compact while preserving parent-child structure",
);

assert.match(
  page,
  /className="relative ml-2\.5 space-y-2 border-l border-\[rgba\(37,99,235,0\.12\)\] pl-2\.5"/,
  "VideoPlayer should render nested children inside a compact guided subtree lane",
);

assert.match(
  page,
  /shouldShowStructureSummary\(node\) \?/,
  "VideoPlayer should only render helper text when it adds information beyond the title",
);

console.log("videoPlayer.knowledge-tree-visual-refresh tests passed");
