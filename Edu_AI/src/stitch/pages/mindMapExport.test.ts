import assert from "node:assert/strict";
import test from "node:test";

import { serializeMindMapContent } from "./mindMapExport.ts";


test("mind map export produces readable JSON with stable node IDs", () => {
  const exported = serializeMindMapContent({
    root: {
      id: "root",
      title: "链表",
      children: [{ id: "root-1", title: "节点", children: [] }],
    },
    max_depth: 3,
  });

  const parsed = JSON.parse(exported);
  assert.equal(parsed.root.id, "root");
  assert.equal(parsed.root.children[0].id, "root-1");
  assert.match(exported, /\n  "root"/);
});

test("mind map export rejects content without a root node", () => {
  assert.throws(() => serializeMindMapContent({}), /根节点/);
});
