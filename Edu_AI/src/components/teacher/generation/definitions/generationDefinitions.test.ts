import assert from "node:assert/strict";
import test from "node:test";

import { reportDefinition } from "./report.ts";


test("report generation requests the grounded visual pipeline by default", () => {
  const config = reportDefinition.defaultConfig();
  const serialized = reportDefinition.serialize({
    courseId: "course-1",
    source: { mode: "none", selectedDocumentIds: [] },
    config,
  });

  assert.equal(config.includeVisuals, true);
  assert.equal(
    (serialized.report_config as Record<string, unknown>).include_visuals,
    true,
  );
});
