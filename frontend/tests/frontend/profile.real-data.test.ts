import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const page = fs.readFileSync(path.join(root, "src/stitch/pages/Profile.tsx"), "utf8");
const api = fs.readFileSync(path.join(root, "src/stitch/api/profile.ts"), "utf8");

test("profile renders backend account data and exposes real editing actions", () => {
  assert.match(page, /getUserProfile/);
  assert.match(page, /updateUserProfile/);
  assert.match(page, /changeUserPassword/);
  assert.match(page, /uploadUserAvatar/);
  assert.doesNotMatch(page, /林知夏|lin\.zhixia@edu-ai\.local|138 0000 1024/);
});

test("profile API uses authenticated account endpoints without persisting passwords", () => {
  assert.match(api, /\/api\/auth\/me/);
  assert.match(api, /\/api\/auth\/change-password/);
  assert.match(api, /\/api\/auth\/avatar/);
  assert.doesNotMatch(api, /localStorage.*password|sessionStorage.*password/s);
});

test("profile keeps one edit action and AI service configuration under account services", () => {
  assert.equal(page.match(/>编辑资料</g)?.length, 1);
  assert.match(page, /账号与服务[\s\S]*AI 服务配置/);
  assert.match(page, /routeHref\(routes\.settings\)/);
  assert.doesNotMatch(page, /profile\.role\s*===\s*["']admin["'][\s\S]*AI 服务配置/);
  assert.doesNotMatch(page, /快捷入口|Quick Access|quickLinks/);
});
