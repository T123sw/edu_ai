import assert from "node:assert/strict";
import test from "node:test";

import { defaultHashForRole, resolveRoleHash } from "./roleRouteResolver.ts";

test("role defaults enter their own workspace", () => {
  assert.equal(defaultHashForRole("student"), "#student-home");
  assert.equal(defaultHashForRole("teacher"), "#home");
  assert.equal(defaultHashForRole("admin"), "#home");
});

test("students share account pages but cannot enter teacher workspace routes", () => {
  assert.equal(resolveRoleHash("student", "#edit?course_id=c1"), "#student-home");
  assert.equal(resolveRoleHash("student", "#home"), "#student-home");
  assert.equal(resolveRoleHash("student", "#profile"), "#profile");
  assert.equal(resolveRoleHash("student", "#settings"), "#settings");
  assert.equal(resolveRoleHash("student", "#student-ai?course_id=c1"), "#student-ai?course_id=c1");
});

test("teacher and admin cannot accidentally enter student workspace routes", () => {
  assert.equal(resolveRoleHash("teacher", "#student-resources?course_id=c1"), "#home");
  assert.equal(resolveRoleHash("admin", "#student-home"), "#home");
  assert.equal(resolveRoleHash("teacher", "#knowledge?course_id=c1"), "#knowledge?course_id=c1");
});
