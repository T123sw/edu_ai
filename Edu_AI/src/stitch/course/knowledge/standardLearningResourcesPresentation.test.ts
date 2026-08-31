import assert from "node:assert/strict";
import test from "node:test";

import type { StandardResourceBatch, StandardResourceLeaf } from "../../api/types";
import {
  groupStandardResourceLeaves,
  standardBatchProgress,
  standardReviewLabel,
  standardSelectionSummary,
  toggleStandardResourceLeafScope,
} from "./standardLearningResourcesPresentation";
import * as presentation from "./standardLearningResourcesPresentation";

test("knowledge leaves remain grouped in source chapter order", () => {
  const leaves = [
    { leaf_id: "a", title: "A", chapter_id: "c1", chapter_title: "第一章", path_titles: [], slots: [] },
    { leaf_id: "b", title: "B", chapter_id: "c2", chapter_title: "第二章", path_titles: [], slots: [] },
    { leaf_id: "c", title: "C", chapter_id: "c1", chapter_title: "第一章", path_titles: [], slots: [] },
  ] satisfies StandardResourceLeaf[];

  const groups = groupStandardResourceLeaves(leaves);

  assert.deepEqual(groups.map((group) => group.chapterTitle), ["第一章", "第二章"]);
  assert.deepEqual(groups[0].leaves.map((leaf) => leaf.leaf_id), ["a", "c"]);
});

test("batch progress distinguishes running and partial failure", () => {
  const batch = {
    total_items: 6,
    succeeded_items: 3,
    failed_items: 1,
    status: "running",
  } as StandardResourceBatch;
  assert.deepEqual(standardBatchProgress(batch), {
    percent: 67,
    label: "已完成 4/6 项",
  });

  assert.equal(
    standardBatchProgress({ ...batch, status: "partial" }).label,
    "3 项完成，1 项失败",
  );
});

test("review statuses have stable learner-facing labels", () => {
  assert.equal(standardReviewLabel("pending"), "待审核");
  assert.equal(standardReviewLabel("approved"), "已发布");
  assert.equal(standardReviewLabel("rejected"), "已退回");
});

test("selection summary reports knowledge points and three resources per point", () => {
  assert.deepEqual(standardSelectionSummary(4), {
    leafCount: 4,
    resourceCount: 12,
    label: "已选择 4 个知识点，将生成 12 项资源",
  });
});

test("chapter selection adds and removes only that chapter scope", () => {
  const current = new Set(["outside"]);
  const selected = toggleStandardResourceLeafScope(current, ["a", "b"]);

  assert.deepEqual([...selected], ["outside", "a", "b"]);
  assert.deepEqual([...toggleStandardResourceLeafScope(selected, ["a", "b"])], ["outside"]);
});

test("knowledge scope keeps only generated resources for the selected node subtree", () => {
  const selectForScope = (presentation as unknown as Record<string, unknown>)[
    "standardResourceLeavesForKnowledgeScope"
  ];
  assert.equal(typeof selectForScope, "function");
  if (typeof selectForScope !== "function") return;

  const leaves = [
    {
      leaf_id: "selected-leaf",
      title: "Selected",
      path_titles: [],
      slots: [
        { standard_kind: "study_guide", material_type: "report", material_id: "r1", review_status: "pending", resource: { material_id: "r1", material_type: "report" } },
      ],
    },
    {
      leaf_id: "empty-leaf",
      title: "Empty",
      path_titles: [],
      slots: [
        { standard_kind: "practice", material_type: "quiz", material_id: "q1", review_status: "not_generated", resource: null },
      ],
    },
    {
      leaf_id: "outside-leaf",
      title: "Outside",
      path_titles: [],
      slots: [
        { standard_kind: "practice", material_type: "quiz", material_id: "q2", review_status: "approved", resource: { material_id: "q2", material_type: "quiz" } },
      ],
    },
  ] satisfies StandardResourceLeaf[];

  const selected = (selectForScope as (
    items: StandardResourceLeaf[],
    scopeIds: ReadonlySet<string>,
  ) => StandardResourceLeaf[])(leaves, new Set(["selected-leaf", "empty-leaf"]));

  assert.deepEqual(selected.map((leaf) => leaf.leaf_id), ["selected-leaf"]);
});
