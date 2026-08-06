import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

test("course resources expose explicit rename pin and complete delete actions", async () => {
  const source = await readFile(new URL("./CourseResources.tsx", import.meta.url), "utf8");
  assert.match(source, /renameCourseMaterial/);
  assert.match(source, /pinCourseMaterial/);
  assert.match(source, /deleteCourseMaterial/);
  assert.match(source, /及其全部导出文件/);
  assert.match(source, /打开课堂/);
});

test("course resources recover the exact material selected by a task result", async () => {
  const source = await readFile(
    new URL("./CourseResources.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /readCourseMaterialTarget/);
  assert.match(source, /getCourseMaterial/);
  assert.match(source, /courseMaterialKey/);
  assert.match(source, /结果资源不存在或无权访问/);
});

test("formal generated types have dedicated storage directories", async () => {
  const source = await readFile(
    new URL("../../../api/src/core/course_storage.py", import.meta.url),
    "utf8",
  );
  for (const mapping of [
    '"ppt": "ppts"',
    '"flashcard": "flashcards"',
    '"game": "games"',
    '"classroom": "classrooms"',
  ]) {
    assert.match(source, new RegExp(mapping));
  }
});
