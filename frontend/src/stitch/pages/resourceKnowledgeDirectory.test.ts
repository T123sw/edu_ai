import assert from "node:assert/strict";
import test from "node:test";
import { buildResourceDirectory } from "./resourceKnowledgeDirectory";
import type { CourseMaterial, KnowledgeGraphNode } from "../api/types";
const root: KnowledgeGraphNode = { id: "course", label: "课程", children: [
  { id: "a", label: "链表" }, { id: "b", label: "排序" }, { id: "c", label: "排序" },
] };
const material = (id: string, extra: Partial<CourseMaterial> = {}): CourseMaterial => ({ material_id: id, material_type: "report", ...extra });
test("persisted knowledge links win over topic text and ambiguous or stale links remain discoverable", () => {
  const nodes = buildResourceDirectory(root, [
    material("linked", { scope_type: "knowledge_point", scope_id: "a", topic: "排序" }),
    material("legacy", { topic: "链表" }), material("ambiguous", { topic: "排序" }),
    material("stale", { scope_id: "deleted", topic: "链表" }),
    material("general", { scope_type: "course" }),
  ]);
  assert.deepEqual(nodes[0].children[0].materials.map(item => item.material_id), ["linked", "legacy"]);
  assert.equal(nodes[0].count, 3);
  assert.deepEqual(nodes[1].materials.map(item => item.material_id), ["ambiguous", "stale"]);
});
test("missing course directory never drops resources", () => {
  const nodes = buildResourceDirectory(null, [material("one", { scope_id: "a" })]);
  assert.equal(nodes[0].label, "未分类资源");
  assert.equal(nodes[0].count, 1);
});

test("root and non-leaf resources live in separate collections after knowledge children", () => {
  const curriculum: KnowledgeGraphNode = { id: "root", label: "课程", children: [
    { id: "chapter", label: "第一章", children: [{ id: "leaf", label: "第一节" }] },
  ] };
  const resources = [
    material("root-one", { scope_type: "course" }),
    material("root-two", { scope_type: "knowledge_point", scope_id: "root" }),
    material("chapter-one", { scope_type: "knowledge_point", scope_id: "chapter" }),
    material("leaf-one", { scope_type: "knowledge_point", scope_id: "leaf" }),
  ];
  const [course] = buildResourceDirectory(curriculum, resources);
  assert.equal(course.count, 4);
  assert.equal(course.materials.length, 0);
  assert.deepEqual(course.children.map(node => node.label), ["第一章", "课程资源"]);
  assert.deepEqual(course.children[1].materials.map(item => item.material_id), ["root-one", "root-two"]);
  const chapter = course.children[0];
  assert.equal(chapter.count, 2);
  assert.equal(chapter.materials.length, 0);
  assert.deepEqual(chapter.children.map(node => node.label), ["第一节", "本节资源"]);
  assert.equal(chapter.children[1].materials[0].material_id, "chapter-one");
  assert.equal(chapter.children[0].materials[0].material_id, "leaf-one");
  assert.equal(curriculum.children![0].children!.length, 1, "presentation folders never alter the curriculum");
});

test("a root without knowledge children still collects course resources", () => {
  const [course] = buildResourceDirectory({ id: "root", label: "课程" }, [material("one", { scope_type: "course" })]);
  assert.equal(course.children[0].label, "课程资源");
  assert.equal(course.children[0].count, 1);
  assert.equal(course.materials.length, 0);
});
