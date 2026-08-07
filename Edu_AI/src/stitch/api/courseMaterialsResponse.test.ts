import assert from "node:assert/strict";
import test from "node:test";

import { unwrapCourseMaterials } from "./courseMaterialsResponse.ts";

const material = {
  material_id: "report-1",
  material_type: "report",
  course_id: "course-1",
};

test("unwrapCourseMaterials accepts unpaged and paged backend responses", () => {
  assert.deepEqual(unwrapCourseMaterials([material]), [material]);
  assert.deepEqual(
    unwrapCourseMaterials({
      items: [material],
      count: 1,
      total: 1,
      limit: 6,
      offset: 0,
    }),
    [material],
  );
});
