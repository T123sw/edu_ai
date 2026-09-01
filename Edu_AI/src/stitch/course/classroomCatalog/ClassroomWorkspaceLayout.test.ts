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

test("responsive rails use two breakpoints and contain their own scrolling", async () => {
  const css = await source("./courseClassroomCatalog.css");
  assert.match(css, /@media\s*\(max-width:\s*1279px\)/);
  assert.match(css, /@media\s*\(max-width:\s*959px\)/);
  assert.match(css, /overscroll-behavior:\s*contain/);
  assert.match(css, /env\(safe-area-inset-bottom/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
});

test("drawers expose controls, escape handling, and trigger focus restoration", async () => {
  const [component, page] = await Promise.all([
    source("./ClassroomWorkspaceLayout.tsx"),
    source("../../pages/ClassroomStudio.tsx"),
  ]);
  assert.match(component, /directoryTriggerRef/);
  assert.match(component, /qaTriggerRef/);
  assert.match(component, /requestAnimationFrame/);
  assert.match(component, /event\.key === "Escape"/);
  assert.match(component, /id="classroom-workspace-directory"/);
  assert.match(component, /id="classroom-workspace-qa"/);
  assert.match(page, /aria-expanded=\{drawerOpen\}/);
  assert.match(page, /aria-expanded=\{qaOpen\}/);
  assert.match(page, /aria-controls="classroom-workspace-directory"/);
  assert.match(page, /aria-controls="classroom-workspace-qa"/);
});
