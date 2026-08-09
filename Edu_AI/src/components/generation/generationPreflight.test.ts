import assert from "node:assert/strict";
import test from "node:test";

import { generationPreflightResourceType } from "./generationPreflight";

test("mind map uses the graph resource type expected by generation preflight", () => {
  assert.equal(generationPreflightResourceType("mind_map"), "graph");
  assert.equal(generationPreflightResourceType("quiz"), "quiz");
});
