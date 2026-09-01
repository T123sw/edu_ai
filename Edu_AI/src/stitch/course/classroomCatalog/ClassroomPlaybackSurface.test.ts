import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (relativePath: string) => readFile(new URL(relativePath, import.meta.url), "utf8");

test("classroom playback is reusable by the standalone page and catalog viewer", async () => {
  const [surface, playerPage, viewer] = await Promise.all([
    source("./ClassroomPlaybackSurface.tsx"),
    source("../../pages/ClassroomPlayer.tsx"),
    source("./CourseResourceViewer.tsx"),
  ]);
  assert.match(surface, /export function ClassroomPlaybackSurface/);
  assert.match(surface, /courseId:\s*string/);
  assert.match(surface, /classroomId:\s*string/);
  assert.match(surface, /resourceVersion\?:\s*number/);
  assert.match(surface, /mode:\s*"manage"\s*\|\s*"learn"/);
  assert.match(surface, /onQaControllerChange/);
  assert.match(playerPage, /<ClassroomPlaybackSurface/);
  assert.match(viewer, /<ClassroomPlaybackSurface/);
  assert.doesNotMatch(viewer, /进入课堂学习|预览课堂/);
});
