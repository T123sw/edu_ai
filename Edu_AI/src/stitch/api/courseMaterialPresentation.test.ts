import assert from "node:assert/strict";
import test from "node:test";

import {
  COURSE_MATERIAL_FILTERS,
  getCourseMaterialOpenTarget,
  getCourseMaterialTypeMeta,
  isCourseMaterialInFilter,
  toCourseMaterialPresentation,
} from "./courseMaterialPresentation.ts";

const material = (materialType: string) => ({
  material_id: `${materialType}-1`,
  material_type: materialType,
  course_id: "course/中文",
});

test("all formal resource types have explicit labels", () => {
  const expected = {
    classroom: "AI 课堂",
    report: "教学报告",
    lesson_plan: "教案",
    blog: "教学博客",
    quiz: "习题",
    game: "课堂小游戏",
    graph: "思维导图",
    ppt: "PPT",
    flashcard: "闪卡",
  };

  for (const [type, label] of Object.entries(expected)) {
    assert.equal(getCourseMaterialTypeMeta(type).label, label);
    assert.equal(getCourseMaterialTypeMeta(type).known, true);
  }
});

test("classroom materials open the matching classroom player identity", () => {
  assert.deepEqual(getCourseMaterialOpenTarget(material("classroom")), {
    kind: "route",
    value:
      "#classroom-player?course_id=course%2F%E4%B8%AD%E6%96%87&classroom_id=classroom-1",
  });
});

test("unknown materials stay in metadata preview and never route to video", () => {
  const target = getCourseMaterialOpenTarget(material("future_resource"));
  assert.deepEqual(target, { kind: "preview", value: "future_resource-1" });
  assert.doesNotMatch(target.value, /video/i);
  assert.equal(getCourseMaterialTypeMeta("future_resource").known, false);
});

test("filters mirror every formal generation type without invented groups", () => {
  assert.deepEqual(
    COURSE_MATERIAL_FILTERS.map((filter) => filter.key),
    [
      "all",
      "classroom",
      "report",
      "lesson_plan",
      "blog",
      "quiz",
      "ppt",
      "flashcard",
      "mind_map",
      "game",
    ],
  );
  assert.equal(isCourseMaterialInFilter(material("classroom"), "classroom"), true);
  assert.equal(isCourseMaterialInFilter(material("report"), "report"), true);
  assert.equal(isCourseMaterialInFilter(material("blog"), "blog"), true);
  assert.equal(isCourseMaterialInFilter(material("ppt"), "ppt"), true);
  assert.equal(isCourseMaterialInFilter(material("flashcard"), "flashcard"), true);
  assert.equal(isCourseMaterialInFilter(material("game"), "game"), true);
  assert.equal(isCourseMaterialInFilter(material("graph"), "mind_map"), true);
  assert.equal(isCourseMaterialInFilter(material("mind_map"), "mind_map"), true);
});

test("private resources describe personal visibility instead of course scope", () => {
  const presentation = toCourseMaterialPresentation({
    ...material("report"),
    visibility: "private",
    owner_user_id: "teacher",
  });

  assert.deepEqual(
    presentation.meta.find((item) => item.label === "可见范围"),
    { label: "可见范围", value: "仅自己可见" },
  );
});
