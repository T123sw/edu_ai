import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const page = fs.readFileSync(path.join(root, "src/stitch/pages/RuntimeSettings.tsx"), "utf8");
const api = fs.readFileSync(path.join(root, "src/stitch/api/runtimeConfig.ts"), "utf8");
const profile = fs.readFileSync(path.join(root, "src/stitch/pages/Profile.tsx"), "utf8");

test("configuration center implements save, verify, activate and rollback lifecycle", () => {
  assert.match(page, /saveRuntimeConfigDraft/);
  assert.match(page, /verifyRuntimeConfig/);
  assert.match(page, /activateRuntimeConfig/);
  assert.match(page, /rollbackRuntimeConfig/);
  assert.match(page, /disableRuntimeConfig/);
  assert.match(page, /测试连接/);
  assert.match(page, /启用/);
  assert.match(page, /停用并恢复默认/);
  assert.match(page, /timeout_seconds/);
  assert.match(page, /provider_name/);
  assert.match(profile, /routes\.settings/);
});

test("secret input is never prefilled or made visible", () => {
  assert.match(page, /field !== ["']api_key["']/);
  assert.match(page, /visibilityToggle=\{false\}/);
  assert.match(page, /autoComplete=["']new-password["']/);
  assert.doesNotMatch(api, /localStorage.*api_key|sessionStorage.*api_key/s);
});

test("system configuration controls are driven by backend role capability", () => {
  assert.match(page, /overview\?\.can_manage_system/);
  assert.match(page, /个人配置/);
  assert.match(page, /系统配置/);
});
