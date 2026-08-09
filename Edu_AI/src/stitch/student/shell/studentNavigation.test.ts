import assert from "node:assert/strict";
import test from "node:test";

import { studentNavigationItems } from "./studentNavigation.ts";

test("student navigation has no teacher management or future placeholder entries", () => {
  const labels = studentNavigationItems.map((item) => item.label);
  assert.equal(labels.length, 6);
  for (const forbidden of ["课程详情", "课程设置", "快捷开始", "最近个人资料", "作业", "学习记录"]) {
    assert.equal(labels.some((label) => label.includes(forbidden)), false);
  }
});
