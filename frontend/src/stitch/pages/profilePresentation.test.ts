import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { presentAccessibleCourseCount } from "./profilePresentation.ts";

test("accessible course count presents the real successful response length", () => {
  assert.equal(presentAccessibleCourseCount(4), "4");
  assert.equal(presentAccessibleCourseCount(0), "0");
});

test("failed course membership lookup is not presented as zero", () => {
  assert.equal(presentAccessibleCourseCount(null), "暂不可用");
});

test("login is role-neutral and remember-account never persists a password", () => {
  const loginPage = readFileSync(
    fileURLToPath(new URL("./LoginPage.tsx", import.meta.url)),
    "utf8",
  );

  assert.match(loginPage, />平台账号</u);
  assert.doesNotMatch(loginPage, />教师账号</u);
  assert.match(loginPage, /localStorage\.setItem\(REMEMBERED_USERNAME_KEY, values\.username\)/u);
  assert.doesNotMatch(loginPage, /localStorage\.setItem\([^\n]*(?:password|values\.password)/iu);
});

test("profile obtains membership-backed courses instead of trusting profile course_count", () => {
  const profilePage = readFileSync(
    fileURLToPath(new URL("./Profile.tsx", import.meta.url)),
    "utf8",
  );

  assert.match(profilePage, /await listCourses\(\)/u);
  assert.match(profilePage, /setAccessibleCourseCount\(courses\.length\)/u);
  assert.doesNotMatch(profilePage, /profile\?\.course_count/u);
});
