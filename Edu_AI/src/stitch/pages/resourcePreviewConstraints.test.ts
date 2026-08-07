import assert from "node:assert/strict";
import test from "node:test";

import { toCourseMaterialPresentation } from "../api/courseMaterialPresentation.ts";
import {
  RESOURCE_RICH_PREVIEW_CLASSNAME,
  getCourseMaterialPreviewKind,
} from "./resourcePreviewConstraints.ts";

const fixture = {
  material_id: "report-internal-id",
  material_type: "report",
  course_id: "course-physics",
  title: "力学报告",
  created_by: "张老师",
  created_at: "2026-08-05T10:00:00+08:00",
  status: "completed",
  visibility: "course" as const,
  scope_type: "course" as const,
  source_snapshot: {
    mode: "selected_documents",
    rag_index_key: "private-rag-key",
  },
};

test("resource metadata exposes provenance without internal IDs", () => {
  const view = toCourseMaterialPresentation(fixture);
  assert.deepEqual(
    view.meta.map((item) => item.label),
    ["类型", "创建者", "可见范围", "资料来源", "创建时间"],
  );
  assert.deepEqual(
    view.meta.find((item) => item.label === "可见范围"),
    { label: "可见范围", value: "课程成员可见" },
  );
  assert.equal(JSON.stringify(view).includes("rag_index_key"), false);
  assert.equal(JSON.stringify(view).includes("private-rag-key"), false);
});

test("preview constraint class is applied to rich content", () => {
  assert.match(RESOURCE_RICH_PREVIEW_CLASSNAME, /edu-rich-preview/);
});

test("all generated resources select a factual preview", () => {
  assert.deepEqual(
    ["report", "lesson_plan", "blog", "quiz", "flashcard", "ppt", "graph", "game", "classroom"]
      .map((material_type) => getCourseMaterialPreviewKind({ ...fixture, material_type })),
    ["rich-text", "rich-text", "blog", "quiz", "flashcard", "ppt", "mind-map", "game", "classroom"],
  );
});
