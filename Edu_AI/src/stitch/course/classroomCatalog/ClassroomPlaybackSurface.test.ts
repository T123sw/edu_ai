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

test("focused playback renders only the stage and approved core controls", async () => {
  const [surface, css] = await Promise.all([
    source("./ClassroomPlaybackSurface.tsx"),
    source("../../styles.css"),
  ]);
  const controlsStart = surface.indexOf('<footer className="classroom-console__controls"');
  const controlsEnd = surface.indexOf("</footer>", controlsStart);
  const controls = surface.slice(controlsStart, controlsEnd);

  assert.ok(controlsStart >= 0 && controlsEnd > controlsStart);
  assert.doesNotMatch(surface, /classroom-console__header/);
  assert.doesNotMatch(surface, /classroom-console__catalog/);
  assert.doesNotMatch(surface, /课堂页面目录|打开课堂目录|进入演示/);
  assert.match(controls, /ClassroomVideoExportButton/);
  assert.match(controls, /PptxExportButton/);
  assert.match(controls, /上一页/);
  assert.match(controls, /下一页/);
  assert.match(controls, /togglePlayback/);
  assert.match(controls, /toggleFullscreen/);
  assert.match(controls, /classroom-page-count/);
  assert.doesNotMatch(controls, /classroom-current-scene|subtitles|classroom-voice-status/);
  assert.match(css, /grid-template-rows:\s*minmax\(0,\s*1fr\)\s+auto/);
  assert.match(surface, /onComplete=\{\(\)\s*=>\s*\{[\s\S]*completeAndAdvance\(\{/);
});
