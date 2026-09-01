import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("course shell uses a top workbar without a sidebar or left drawer", async () => {
  const shell = await readFile(new URL("./CourseShell.tsx", import.meta.url), "utf8");

  assert.match(shell, /className="course-shell__workbar"/u);
  assert.match(shell, /course-navigation--desktop/u);
  assert.match(shell, /className="course-shell__mobile-panel"/u);
  assert.doesNotMatch(shell, /course-shell__sidebar|course-shell__drawer|course-shell__back/u);
});

test("course settings live only in the teacher course menu", async () => {
  const shell = await readFile(new URL("./CourseShell.tsx", import.meta.url), "utf8");

  assert.match(shell, /!isStudent[\s\S]*course-shell__course-trigger/u);
  assert.match(shell, /buildRoleCourseHash\(user\?\.role, "edit", courseId\)/u);
  assert.match(shell, /<span>课程设置<\/span>/u);
  assert.match(shell, /isStudent[\s\S]*course-shell__course-name/u);
  assert.doesNotMatch(shell, /studentNavigationLabels/u);
});
