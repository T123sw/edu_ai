import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("the task center supports a shared inline trigger without duplicating its store", async () => {
  const drawer = await readFile(new URL("./JobCenterDrawer.tsx", import.meta.url), "utf8");
  const app = await readFile(new URL("../stitch/App.tsx", import.meta.url), "utf8");
  const courseShell = await readFile(
    new URL("../stitch/course/CourseShell.tsx", import.meta.url),
    "utf8",
  );
  const studentShell = await readFile(
    new URL("../stitch/student/shell/StudentShell.tsx", import.meta.url),
    "utf8",
  );

  assert.match(drawer, /export function JobCenterTrigger/);
  assert.match(drawer, /edu-ai:open-job-center/);
  assert.match(drawer, /showLauncher/);
  assert.match(app, /showLauncher=\{authUser\?\.role !== "student" && !isCourseRoute && !isStudentWorkspace\}/);
  assert.match(courseShell, /<JobCenterTrigger placement="inline" \/>/);
  assert.match(studentShell, /<JobCenterTrigger placement="inline" \/>/);
});

test("the task center renders three status totals and no task id copy action", async () => {
  const drawer = await readFile(
    new URL("./JobCenterDrawer.tsx", import.meta.url),
    "utf8",
  );

  assert.match(drawer, /<span>已完成<\/span>/);
  assert.match(drawer, /<span>进行中<\/span>/);
  assert.match(drawer, /<span>失败<\/span>/);
  assert.doesNotMatch(
    drawer,
    /需关注率|平均耗时|复制任务 ID|navigator\.clipboard/,
  );
  assert.match(drawer, /getJobPrimaryAction/);
  assert.match(drawer, /isJobCenterVisible/);
});
