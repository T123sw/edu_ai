import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { parseTheme, resolveTheme, themeNames } from './appearance';

const componentUrl = new URL("./ThemeAppearanceSettings.tsx", import.meta.url);

test("profile appearance settings expose all five accessible choices", () => {
  assert.equal(existsSync(fileURLToPath(componentUrl)), true);
  const source = readFileSync(fileURLToPath(componentUrl), "utf8");
  for (const label of ["纸间绿", "雾海蓝", "暖杏", "石墨夜", "跟随系统"]) {
    assert.match(source, new RegExp(label, "u"));
  }
  assert.match(source, /setTheme/u);
  assert.match(source, /name=["']palette["']/u);
  assert.match(source, /aria-pressed=/u);
  assert.match(source, /focus-visible:/u);
  assert.match(source, />当前</u);
});

test("missing and invalid choices preserve the current palette; saved choices survive parsing", () => {
  assert.equal(parseTheme(null), 'forest');
  assert.equal(parseTheme('unknown'), 'forest');
  for (const theme of themeNames) assert.equal(parseTheme(theme), theme);
});
test("only system preference follows the device; explicit palettes stay fixed", () => {
  assert.equal(resolveTheme('system', true), 'dark');
  assert.equal(resolveTheme('system', false), 'forest');
  for (const theme of themeNames.filter(theme => theme !== 'system')) {
    assert.equal(resolveTheme(theme, true), theme);
    assert.equal(resolveTheme(theme, false), theme);
  }
});
