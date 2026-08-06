import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const page = fs.readFileSync(path.join(root, "src/stitch/pages/RuntimeSettings.tsx"), "utf8");
const api = fs.readFileSync(path.join(root, "src/stitch/api/runtimeConfig.ts"), "utf8");
const profile = fs.readFileSync(path.join(root, "src/stitch/pages/Profile.tsx"), "utf8");

test("configuration center presents a vertical service catalog and an inline editor", () => {
  assert.match(page, /saveRuntimeConfigDraft/);
  assert.match(page, /verifyRuntimeConfig/);
  assert.match(page, /activateRuntimeConfig/);
  assert.match(page, /disableRuntimeConfig/);
  assert.match(page, /runtime-service-nav/);
  assert.match(page, /runtime-service-editor/);
  assert.match(page, /selectedProvider/);
  assert.match(page, /测试连接/);
  assert.match(page, /应用配置/);
  assert.match(page, /恢复部署默认配置/);
  assert.match(page, /timeout_seconds/);
  assert.match(page, /provider_name/);
  assert.match(profile, /routes\.settings/);
  assert.doesNotMatch(page, /<Modal/);
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

test("applying a configuration requires a successful test of the current form values", () => {
  assert.match(page, /testedRevision/);
  assert.match(page, /setTestedRevision\(null\)/);
  assert.match(page, /测试通过，可以应用配置/);
});
