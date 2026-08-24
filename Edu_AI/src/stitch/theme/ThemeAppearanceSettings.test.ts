import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const componentUrl = new URL("./ThemeAppearanceSettings.tsx", import.meta.url);

test("profile appearance settings expose four accessible themes", () => {
  assert.equal(existsSync(fileURLToPath(componentUrl)), true);
  const source = readFileSync(fileURLToPath(componentUrl), "utf8");
  for (const label of ["海蓝", "森绿", "日落", "暗色"]) {
    assert.match(source, new RegExp(label, "u"));
  }
  assert.match(source, /setTheme/u);
  assert.match(source, /name=["']palette["']/u);
  assert.match(source, /aria-pressed=/u);
  assert.match(source, /focus-visible:/u);
  assert.match(source, />当前</u);
});
