import assert from "node:assert/strict";
import test from "node:test";

import { getCourseNavigation } from "./courseNavigation.ts";

test("editors see the complete course workspace navigation", () => {
  assert.deepEqual(
    getCourseNavigation("editor").map((item) => item.id),
    ["overview", "workspace", "knowledge", "classroom", "resources", "settings"],
  );
  assert.equal(
    getCourseNavigation("editor").some((item) => "description" in item),
    false,
  );
});

test("viewers cannot open course settings", () => {
  assert.equal(
    getCourseNavigation("viewer").some((item) => item.id === "settings"),
    false,
  );
});

test("knowledge graph deep links belong to the course knowledge section", () => {
  const knowledge = getCourseNavigation("owner").find((item) => item.id === "knowledge");
  assert.deepEqual(knowledge?.routes, ["knowledge", "graph"]);
});
