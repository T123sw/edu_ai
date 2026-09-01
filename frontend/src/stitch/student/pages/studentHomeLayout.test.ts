import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("student home reuses the teacher course catalog presentation", async () => {
  const source = await readFile(new URL("./StudentHome.tsx", import.meta.url), "utf8");

  assert.match(source, /toCourseCardPresentation/);
  assert.match(source, /teacher-home__intro/);
  assert.match(source, /teacher-course-grid/);
  assert.match(source, /teacher-course-card__metrics/);
  assert.match(source, /最近学习/);
  assert.doesNotMatch(source, /student-home__hero/);
});

test("student personal center follows the shared course header action position", async () => {
  const source = await readFile(
    new URL("../shell/StudentShell.tsx", import.meta.url),
    "utf8",
  );

  const jobCenterPosition = source.indexOf('<JobCenterTrigger placement="inline" />');
  const profilePosition = source.indexOf('className="student-shell__profile"');
  assert.ok(jobCenterPosition >= 0);
  assert.ok(profilePosition > jobCenterPosition);
  assert.doesNotMatch(source, /student-shell__profile-link/);
});

test("student learning home omits the global navigation sidebar", async () => {
  const source = await readFile(
    new URL("../shell/StudentShell.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /const isHome = activeRoute === "student-home"/);
  assert.match(source, /\{isHome \? null : \(/);
  assert.match(source, /isHome && "is-home"/);
  assert.match(source, /!isHome && drawerOpen/);
});
