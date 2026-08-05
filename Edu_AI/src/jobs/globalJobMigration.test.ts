import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const migratedComponents = [
  "../components/teacher/ClassroomGenerationEntry.tsx",
  "../stitch/pages/ClassroomStudio.tsx",
  "../openmaic/ClassroomVideoExportButton.tsx",
];

test("classroom generation and video export use the global task source", async () => {
  for (const path of migratedComponents) {
    const source = await readFile(new URL(path, import.meta.url), "utf8");
    assert.match(source, /useCourseJobs/);
    assert.match(source, /registerCreatedJob/);
    assert.doesNotMatch(source, /getJobStatus/);
    assert.doesNotMatch(source, /waitFor(?:ClassroomGeneration|VideoExport)Job/);
    assert.doesNotMatch(source, /setInterval/);
  }
});

test("the global manager is mounted outside the keyed route subtree", async () => {
  const source = await readFile(
    new URL("../stitch/App.tsx", import.meta.url),
    "utf8",
  );
  const managerIndex = source.indexOf("<GlobalJobManager");
  const keyedRouteIndex = source.indexOf("<div key={current}");
  assert.ok(managerIndex >= 0);
  assert.ok(keyedRouteIndex >= 0);
  assert.ok(managerIndex < keyedRouteIndex);
});
