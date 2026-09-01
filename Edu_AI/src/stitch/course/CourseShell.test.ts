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

test("desktop workbar navigation is left aligned with readable labels", async () => {
  const styles = await readFile(new URL("../styles.css", import.meta.url), "utf8");

  assert.match(styles, /\.course-navigation--desktop\s*\{[^}]*justify-content:\s*flex-start;/u);
  assert.match(styles, /\.course-shell__brand\s*\{[^}]*font-size:\s*22px;/u);
  assert.match(styles, /\.course-shell__course-trigger,[\s\S]*?\.course-shell__course-name\s*\{[^}]*font-size:\s*25px;/u);
  assert.match(styles, /\.course-shell__workbar\s*\{[^}]*grid-template-columns:\s*auto auto minmax\(0, 1fr\) auto;/u);
  assert.match(styles, /\.course-shell__course-trigger\s*\{[^}]*width:\s*fit-content;/u);
  assert.match(styles, /\.course-shell__course-trigger > span:first-child\s*\{\s*flex:\s*0 1 auto;/u);
  assert.match(styles, /\.course-navigation__link strong\s*\{[^}]*font-size:\s*25px;/u);
  assert.match(styles, /\.course-navigation__icon \.app-icon\s*\{[^}]*font-size:\s*17px;/u);
  assert.match(styles, /\.course-shell__profile\s*\{[^}]*font-size:\s*16px;/u);
  assert.match(styles, /\.course-shell__actions \.job-center-launcher__label\s*\{[^}]*font-size:\s*16px;/u);
});

test("course homepage and settings live only in the teacher course menu", async () => {
  const shell = await readFile(new URL("./CourseShell.tsx", import.meta.url), "utf8");

  assert.match(shell, /!isStudent[\s\S]*course-shell__course-trigger/u);
  assert.match(shell, /buildRoleCourseHash\(user\?\.role, "course-detail", courseId\)[\s\S]*<span>课程首页<\/span>[\s\S]*buildRoleCourseHash\(user\?\.role, "edit", courseId\)/u);
  assert.match(shell, /buildRoleCourseHash\(user\?\.role, "edit", courseId\)/u);
  assert.match(shell, /<span>课程设置<\/span>/u);
  assert.match(shell, /isStudent[\s\S]*course-shell__course-name/u);
  assert.doesNotMatch(shell, /studentNavigationLabels/u);
});
