import assert from "node:assert/strict";
import test from "node:test";

import { reportDefinition } from "./report.ts";


test("report generation disables retired image enrichment even for an old draft", () => {
  const config = reportDefinition.defaultConfig();
  const serialized = reportDefinition.serialize({
    courseId: "course-1",
    source: { mode: "none", selectedDocumentIds: [] },
    config: { ...config, includeVisuals: true } as typeof config,
  });

  assert.equal("includeVisuals" in config, false);
  assert.equal(
    (serialized.report_config as Record<string, unknown>).include_visuals,
    false,
  );
});
