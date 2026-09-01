import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("course knowledge tree renders child structure before root-level documents", async () => {
  const source = await readFile(new URL("./SourcePanel.tsx", import.meta.url), "utf8");
  const renderStart = source.indexOf("const renderCourseLibraryTreeNode");
  const renderEnd = source.indexOf("const courseLibraryTreeRoot", renderStart);
  const renderSource = source.slice(renderStart, renderEnd);

  const childrenPosition = renderSource.indexOf("source-panel__tree-node-children");
  const documentsPosition = renderSource.indexOf("source-panel__tree-node-files");

  assert.ok(childrenPosition >= 0, "course tree must render child nodes");
  assert.ok(documentsPosition >= 0, "course tree must render directly assigned documents");
  assert.ok(
    childrenPosition < documentsPosition,
    "child chapters must stay above large root-level document collections",
  );
});

test("course tree layout keeps child structure visually ahead of direct documents", async () => {
  const styles = await readFile(new URL("./SourcePanel.css", import.meta.url), "utf8");

  assert.match(styles, /\.source-panel__tree-node\s*{[^}]*display:\s*flex;/s);
  assert.match(styles, /\.source-panel__tree-node\s*{[^}]*flex-direction:\s*column;/s);
  assert.match(styles, /\.source-panel__tree-node-children\s*{[^}]*order:\s*1;/s);
  assert.match(styles, /\.source-panel__tree-node-files\s*{[^}]*order:\s*2;/s);
});
