import assert from "node:assert/strict";
import test from "node:test";

import type { KnowledgeGraphNode } from "../../api/types";
import {
  defaultExpandedNodeIds,
  toggleExpandedNode,
  visibleKnowledgeTree,
} from "./knowledgeTreeExpansion";

const tree: KnowledgeGraphNode = {
  id: "root",
  label: "课程",
  children: [
    {
      id: "chapter-1",
      label: "第一章",
      children: [
        { id: "section-1", label: "第一节", children: [{ id: "topic-1", label: "知识点" }] },
      ],
    },
    { id: "chapter-2", label: "第二章" },
  ],
};

test("initial knowledge tree shows only the root and its immediate children", () => {
  const expanded = defaultExpandedNodeIds(tree);
  assert.deepEqual(
    visibleKnowledgeTree(tree, expanded).map((node) => node.id),
    ["root", "chapter-1", "chapter-2"],
  );
});

test("expanding a branch reveals one more level without expanding its descendants", () => {
  const expanded = toggleExpandedNode(defaultExpandedNodeIds(tree), tree.children![0]);
  assert.deepEqual(
    visibleKnowledgeTree(tree, expanded).map((node) => node.id),
    ["root", "chapter-1", "section-1", "chapter-2"],
  );
});

test("collapsing a branch clears expansion state below that branch", () => {
  let expanded = defaultExpandedNodeIds(tree);
  expanded = toggleExpandedNode(expanded, tree.children![0]);
  expanded = toggleExpandedNode(expanded, tree.children![0].children![0]);
  expanded = toggleExpandedNode(expanded, tree.children![0]);
  expanded = toggleExpandedNode(expanded, tree.children![0]);

  assert.deepEqual(
    visibleKnowledgeTree(tree, expanded).map((node) => node.id),
    ["root", "chapter-1", "section-1", "chapter-2"],
  );
});
