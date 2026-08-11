import assert from "node:assert/strict";
import test from "node:test";

import type { KnowledgeGraphNode } from "../../api/types";
import {
  addGraphChild,
  graphDraftStats,
  moveGraphNode,
  moveGraphSibling,
  removeGraphNode,
  updateGraphNode,
} from "./courseKnowledgeGraphDraft";

function graph(): KnowledgeGraphNode {
  return {
    id: "root",
    label: "代数课程",
    data: { type: "course", summary: "课程" },
    children: [
      {
        id: "m1",
        label: "方程",
        data: { type: "knowledge_module", summary: "模块" },
        children: [
          { id: "p1", label: "一元方程", data: { type: "knowledge_point", summary: "知识点" }, children: [] },
          { id: "p2", label: "二元方程", data: { type: "knowledge_point", summary: "知识点" }, children: [] },
        ],
      },
      {
        id: "m2",
        label: "函数",
        data: { type: "knowledge_module", summary: "模块" },
        children: [
          { id: "p3", label: "一次函数", data: { type: "knowledge_point", summary: "知识点" }, children: [] },
        ],
      },
    ],
  };
}

test("graph editor updates content without mutating source", () => {
  const source = graph();
  const updated = updateGraphNode(source, "p1", { label: "线性方程", summary: "新的说明" });
  assert.equal(source.children?.[0].children?.[0].label, "一元方程");
  assert.equal(updated.children?.[0].children?.[0].label, "线性方程");
  assert.equal(updated.children?.[0].children?.[0].data?.summary, "新的说明");
});

test("graph editor adds, removes and reorders siblings", () => {
  const added = addGraphChild(graph(), "m1", 3);
  assert.ok(added.addedId);
  assert.equal(added.root.children?.[0].children?.length, 3);
  const moved = moveGraphSibling(added.root, added.addedId!, -1);
  assert.equal(moved.children?.[0].children?.[1].id, added.addedId);
  const removed = removeGraphNode(moved, added.addedId!);
  assert.equal(removed.children?.[0].children?.length, 2);
});

test("graph editor reparents only to a legal same-layer parent", () => {
  const moved = moveGraphNode(graph(), "p2", "m2");
  assert.deepEqual(moved.children?.[0].children?.map((item) => item.id), ["p1"]);
  assert.deepEqual(moved.children?.[1].children?.map((item) => item.id), ["p3", "p2"]);
  const source = graph();
  assert.equal(moveGraphNode(source, "m1", "p3"), source, "illegal move keeps original reference");
});

test("graph stats report actual structure and textbook mappings", () => {
  const source = graph();
  source.children![0].children![0].data!.source_outline_refs = ["chapter-1"];
  source.data!.unmapped_outline_items = ["appendix"];
  assert.deepEqual(graphDraftStats(source), {
    nodeCount: 6,
    moduleCount: 2,
    leafCount: 3,
    maxDepth: 3,
    mappedOutlineCount: 1,
    unmappedOutlineCount: 1,
  });
});
