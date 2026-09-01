import assert from "node:assert/strict";
import test from "node:test";

import {
  getAiStudioGridTemplate,
  getAiStudioLayoutMode,
  resolveCompactPanelState,
} from "./aiStudioLayout.ts";

test("workspace breakpoints use the measured content width", () => {
  assert.equal(getAiStudioLayoutMode(1539), "compact");
  assert.equal(getAiStudioLayoutMode(1540), "wide");
  assert.equal(getAiStudioLayoutMode(1199), "drawer");
  assert.equal(getAiStudioLayoutMode(1200), "compact");
});

test("drawer layout reserves the full row for conversation", () => {
  assert.equal(
    getAiStudioGridTemplate({
      mode: "drawer",
      leftCollapsed: false,
      rightCollapsed: false,
    }),
    "minmax(0, 1fr)",
  );
});

test("compact layout never leaves both side panels expanded", () => {
  assert.deepEqual(
    resolveCompactPanelState({ leftCollapsed: false, rightCollapsed: false }),
    { leftCollapsed: true, rightCollapsed: false },
  );
  assert.deepEqual(
    resolveCompactPanelState({ leftCollapsed: false, rightCollapsed: true }),
    { leftCollapsed: false, rightCollapsed: true },
  );
});
