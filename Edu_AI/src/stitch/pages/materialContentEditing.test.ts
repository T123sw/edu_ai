import assert from "node:assert/strict";
import test from "node:test";

import type { CourseMaterial } from "../api/types.ts";
import {
  editableMaterialDraft,
  parseEditableMaterialDraft,
} from "./materialContentEditing.ts";

function material(values: Partial<CourseMaterial>): CourseMaterial {
  return {
    material_id: "material-1",
    material_type: "report",
    ...values,
  };
}

test("text resources edit their markdown content directly", () => {
  const item = material({ material_type: "report", content: "# 原报告" });
  assert.equal(editableMaterialDraft(item), "# 原报告");
  assert.equal(parseEditableMaterialDraft(item, "# 新报告"), "# 新报告");
});

test("mind maps edit and save their structured content", () => {
  const item = material({
    material_type: "graph",
    content: { root: { id: "root", title: "链表", children: [] } },
  });
  const draft = editableMaterialDraft(item);
  assert.equal(JSON.parse(draft).root.id, "root");
  assert.deepEqual(parseEditableMaterialDraft(item, draft), {
    root: { id: "root", title: "链表", children: [] },
  });
});

test("structured editor reports invalid JSON instead of silently saving", () => {
  const item = material({ material_type: "quiz", questions: [] });
  assert.throws(
    () => parseEditableMaterialDraft(item, "{not-json}"),
    /JSON/,
  );
});
