import assert from "node:assert/strict";
import { test } from "node:test";

import {
  applyWhiteColorKeyTransparency,
  getWhiteColorKeyAlpha,
} from "./avatarTransparency.ts";

test("getWhiteColorKeyAlpha makes white and near-white pixels transparent", () => {
  assert.equal(getWhiteColorKeyAlpha(255, 255, 255), 0);
  assert.equal(getWhiteColorKeyAlpha(248, 250, 252), 0);
});

test("getWhiteColorKeyAlpha preserves clear foreground pixels", () => {
  assert.equal(getWhiteColorKeyAlpha(38, 56, 92), 255);
  assert.equal(getWhiteColorKeyAlpha(190, 160, 130), 255);
});

test("getWhiteColorKeyAlpha feathers pixels near the white key boundary", () => {
  const alpha = getWhiteColorKeyAlpha(218, 220, 222);

  assert.ok(alpha > 0);
  assert.ok(alpha < 255);
});

test("applyWhiteColorKeyTransparency updates image alpha in place", () => {
  const data = new Uint8ClampedArray([
    255, 255, 255, 255,
    218, 220, 222, 255,
    28, 40, 82, 255,
  ]);

  applyWhiteColorKeyTransparency(data);

  assert.equal(data[3], 0);
  assert.ok(data[7] > 0 && data[7] < 255);
  assert.equal(data[11], 255);
});
