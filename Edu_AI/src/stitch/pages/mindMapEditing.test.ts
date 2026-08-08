import assert from "node:assert/strict";
import test from "node:test";

import {
  addMindMapChild,
  removeMindMapNode,
  updateMindMapNodeTitle,
} from "./mindMapEditing.ts";

const root = {
  id: "root",
  title: "链表",
  children: [{ id: "root-1", title: "节点", children: [] }],
};

test("mind map nodes can be renamed without changing stable IDs", () => {
  const updated = updateMindMapNodeTitle(root, "root-1", "节点结构");
  assert.equal(updated.children[0].id, "root-1");
  assert.equal(updated.children[0].title, "节点结构");
});

test("mind map children receive collision-free stable IDs", () => {
  const updated = addMindMapChild(root, "root");
  assert.deepEqual(updated.children.map((node) => node.id), ["root-1", "root-2"]);
});

test("mind map child can be removed but root cannot", () => {
  assert.equal(removeMindMapNode(root, "root-1").children.length, 0);
  assert.equal(removeMindMapNode(root, "root"), root);
});
