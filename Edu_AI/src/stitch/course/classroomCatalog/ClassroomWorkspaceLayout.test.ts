import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (path: string) => readFile(new URL(path, import.meta.url), "utf8");

test("desktop classroom workspace is full-width with three semantic rails", async () => {
  const [component, css] = await Promise.all([
    source("./ClassroomWorkspaceLayout.tsx"),
    source("./courseClassroomCatalog.css"),
  ]);

  assert.match(component, /course-classroom-workspace__directory/);
  assert.match(component, /course-classroom-workspace__viewer/);
  assert.match(component, /course-classroom-workspace__qa/);
  assert.match(component, /aria-label="课程与个人课堂导航"/);
  assert.match(component, /aria-label="当前学习内容"/);
  assert.match(component, /aria-label="当前内容问答"/);
  assert.match(
    css,
    /grid-template-columns:\s*clamp\(310px,\s*18vw,\s*360px\)\s+minmax\(520px,\s*1fr\)\s+clamp\(340px,\s*21vw,\s*420px\)/,
  );
  assert.doesNotMatch(
    css,
    /course-classroom-catalog__layout[^}]*max-width:\s*1560px/s,
  );
});
