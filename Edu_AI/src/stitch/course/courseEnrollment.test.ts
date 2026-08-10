import assert from "node:assert/strict";
import test from "node:test";

import { isCompleteCourseCode, normalizeCourseCodeInput } from "./courseEnrollment.ts";

test("normalizes a pasted course code for student enrollment", () => {
  assert.equal(normalizeCourseCodeInput(" abcd-2345 "), "ABCD2345");
  assert.equal(isCompleteCourseCode("abcd 2345"), true);
  assert.equal(isCompleteCourseCode("ABCD1234"), false);
});
