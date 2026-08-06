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

  assert.match(drawer, /export function JobCenterTrigger/);
  assert.match(drawer, /edu-ai:open-job-center/);
  assert.match(drawer, /showLauncher/);
  assert.match(app, /showLauncher=\{!isCourseRoute\}/);
  assert.match(courseShell, /<JobCenterTrigger placement="inline" \/>/);
});
