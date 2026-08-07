import assert from "node:assert/strict";
import test from "node:test";
import {
  collectKnowledgeSubtreeNodeIds,
  collectScopedKnowledgeNodeIds,
} from "./knowledgeScopeSelection.ts";

const graph = {
  id: "root",
  children: [
    {
      id: "chapter-1",
      children: [{ id: "section-1" }, { id: "section-2" }],
    },
    { id: "chapter-2" },
  ],
};

test("selecting a parent knowledge node includes every descendant node", () => {
  assert.deepEqual(collectScopedKnowledgeNodeIds(graph, "chapter-1"), [
    "chapter-1",
    "section-1",
    "section-2",
  ]);
});

test("subtree collection is stable for leaf nodes and unknown scopes", () => {
  assert.deepEqual(collectKnowledgeSubtreeNodeIds({ id: "leaf" }), ["leaf"]);
  assert.deepEqual(collectScopedKnowledgeNodeIds(graph, "missing"), []);
});
