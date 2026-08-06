import assert from "node:assert/strict";
import test from "node:test";

import {
  courseMaterialKey,
  readCourseMaterialTarget,
} from "./courseMaterialTarget.ts";

test("reads an exact material target from the resources hash", () => {
  assert.deepEqual(
    readCourseMaterialTarget(
      "#resources?course_id=course-a&material_type=report&material_id=report%2F1",
    ),
    { materialType: "report", materialId: "report/1" },
  );
});

test("rejects incomplete material targets", () => {
  assert.equal(
    readCourseMaterialTarget(
      "#resources?course_id=course-a&material_id=report-1",
    ),
    null,
  );
  assert.equal(
    readCourseMaterialTarget(
      "#resources?course_id=course-a&material_type=report",
    ),
    null,
  );
});

test("material keys keep equal ids in different resource types distinct", () => {
  assert.notEqual(
    courseMaterialKey("report", "shared-id"),
    courseMaterialKey("quiz", "shared-id"),
  );
});
