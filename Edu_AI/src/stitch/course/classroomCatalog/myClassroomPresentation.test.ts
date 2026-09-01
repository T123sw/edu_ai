import assert from "node:assert/strict";
import test from "node:test";
import { presentMyClassrooms } from "./myClassroomPresentation.ts";

test("my classroom keeps personal classrooms and sorts newest first", () => {
  const result = presentMyClassrooms([
    { material_id: "old", material_type: "classroom", title: "旧课堂", updated_at: "2026-08-01", scenes: [] },
    { material_id: "new", material_type: "classroom", title: "新课堂", updated_at: "2026-09-01", scenes: [{ id: "s1", type: "slide" }] },
    { material_id: "report", material_type: "report", title: "报告", updated_at: "2026-09-02" },
  ]);

  assert.deepEqual(result.map((item) => item.id), ["new", "old"]);
  assert.equal(result[0].status, "ready");
  assert.equal(result[1].status, "empty");
});

test("my classroom exposes generation and failure states without treating them as playable", () => {
  const result = presentMyClassrooms([
    { material_id: "running", material_type: "classroom", title: "生成中", video_status: "running" },
    { material_id: "failed", material_type: "classroom", title: "失败", video_status: "failed" },
  ]);

  assert.deepEqual(result.map((item) => item.status), ["generating", "failed"]);
});
