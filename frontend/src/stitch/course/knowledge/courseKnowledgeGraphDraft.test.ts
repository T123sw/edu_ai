import assert from "node:assert/strict";
import test from "node:test";

import type { KnowledgeGraphNode } from "../../api/types";
import {
  addGraphChild,
  buildGraphReviewModel,
  canEditGraphNodeStructure,
  graphDraftStats,
  moveGraphNode,
  moveGraphSibling,
  removeGraphNode,
  updateGraphNode,
  visibleGraphNodeIds,
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
  const updated = updateGraphNode(source, "p1", {
    label: "线性方程",
    summary: "新的说明",
    sourceOutlineRefs: ["chapter-1", "chapter-2"],
  });
  assert.equal(source.children?.[0].children?.[0].label, "一元方程");
  assert.equal(updated.children?.[0].children?.[0].label, "线性方程");
  assert.equal(updated.children?.[0].children?.[0].data?.summary, "新的说明");
  assert.deepEqual(updated.children?.[0].children?.[0].data?.source_outline_refs, ["chapter-1", "chapter-2"]);
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

test("review model identifies baseline nodes and selects the first issue", () => {
  const baseline = graph();
  const current = graph();
  current.children![0].children!.push({
    id: "new-point",
    label: "新增知识点",
    data: { type: "knowledge_point", summary: "", review_state: "new" },
    children: [],
  });

  const model = buildGraphReviewModel(current, baseline);

  assert.equal(model.nodesById.get("p1")?.isExisting, true);
  assert.equal(model.nodesById.get("new-point")?.isExisting, false);
  assert.equal(model.issues[0].nodeId, "new-point");
  assert.equal(model.initialSelectedNodeId, "new-point");
});

test("tree search keeps ancestors and filters retain matching nodes", () => {
  const baseline = graph();
  const current = graph();
  current.children![0].children!.push({
    id: "new-point",
    label: "新方程方法",
    data: { type: "knowledge_point", summary: "说明", review_state: "new" },
    children: [],
  });
  const model = buildGraphReviewModel(current, baseline);

  assert.deepEqual(visibleGraphNodeIds(model, "一次函数", "all"), ["root", "m2", "p3"]);
  assert.deepEqual(visibleGraphNodeIds(model, "", "new"), ["root", "m1", "new-point"]);
});

test("existing node structural edits are rejected but summaries remain editable", () => {
  const baseline = graph();
  const current = graph();
  current.children![0].children!.push({
    id: "new-point",
    label: "新增知识点",
    data: { type: "knowledge_point", summary: "说明" },
    children: [],
  });

  assert.equal(canEditGraphNodeStructure("p1", baseline), false);
  assert.equal(canEditGraphNodeStructure("new-point", baseline), true);
  const updated = updateGraphNode(current, "p1", { summary: "补充说明" });
  assert.equal(updated.children?.[0].children?.[0].data?.summary, "补充说明");
});
