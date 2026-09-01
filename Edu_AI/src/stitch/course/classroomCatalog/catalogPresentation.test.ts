import assert from "node:assert/strict";
import test from "node:test";

import type { ClassroomCatalogLeaf } from "../../api/types.ts";
import {
  buildCatalogHash,
  buildCurriculumResourceTree,
  catalogLeafSummary,
  filterCurriculumTree,
  readCatalogTarget,
} from "./catalogPresentation.ts";


const leaf = (leafId: string, pathTitles: string[]): ClassroomCatalogLeaf => ({
  leaf_id: leafId,
  title: pathTitles.at(-1) ?? leafId,
  chapter_id: null,
  chapter_title: null,
  path_titles: pathTitles,
  resources: [],
  learning_summary: { completed: 0, total: 0 },
});


test("curriculum tree drops the course root and preserves source order", () => {
  const tree = buildCurriculumResourceTree([
    leaf("leaf-1", ["数据结构", "第一章", "1.1 线性表"]),
    leaf("leaf-2", ["数据结构", "第一章", "1.2 栈"]),
  ]);

  assert.equal(tree[0].title, "第一章");
  assert.deepEqual(tree[0].children.map((item) => item.title), ["1.1 线性表", "1.2 栈"]);
});


test("search retains matching leaf ancestors and removes unmatched siblings", () => {
  const tree = buildCurriculumResourceTree([
    leaf("leaf-1", ["数据结构", "第一章", "1.1 线性表"]),
    leaf("leaf-2", ["数据结构", "第一章", "1.2 栈"]),
  ]);

  const filtered = filterCurriculumTree(tree, "栈");
  assert.equal(filtered[0].title, "第一章");
  assert.deepEqual(filtered[0].children.map((item) => item.title), ["1.2 栈"]);
  assert.equal(filterCurriculumTree(tree, ""), tree);
});


test("catalog deep links encode and recover exact selection", () => {
  const hash = buildCatalogHash("student", "course/一", "leaf-1", "guide-1");
  assert.equal(
    hash,
    "#student-classroom?course_id=course%2F%E4%B8%80&node_id=leaf-1&resource_id=guide-1",
  );
  assert.deepEqual(readCatalogTarget(hash), { nodeId: "leaf-1", resourceId: "guide-1" });
});


test("student leaf summaries use resource completion counts", () => {
  assert.equal(catalogLeafSummary(leaf("empty", ["课程", "暂无"])), "暂无资料");
  assert.equal(catalogLeafSummary({
    ...leaf("partial", ["课程", "部分"]),
    learning_summary: { completed: 2, total: 3 },
  }), "已完成 2/3");
});
