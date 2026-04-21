import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../../src/stitch/pages/VideoPlayer.tsx", import.meta.url), "utf8");
const exportHelper = readFileSync(new URL("../../src/stitch/wordExport.ts", import.meta.url), "utf8");

assert.match(
  exportHelper,
  /export function getCourseMaterialPptPreviewUrl\(/,
  "Export helper should expose a PPT preview url resolver for course materials",
);

assert.match(
  exportHelper,
  /html_full_url \|\| contentRecord\.html_full_url \|\| topLevelRecord\.html_url \|\| contentRecord\.html_url/,
  "PPT preview helper should read generated deck html preview urls from persisted material content",
);

assert.match(
  page,
  /const activeMaterialPptPreviewUrl = getCourseMaterialPptPreviewUrl\(activeMaterial\);/,
  "VideoPlayer should resolve the generated PPT preview url for course materials",
);

assert.match(
  page,
  /activeMaterialPptPreviewUrl \? \([\s\S]*<iframe[\s\S]*src=\{activeMaterialPptPreviewUrl\}[\s\S]*title=\{activeMaterial\.title \|\| activeMaterial\.topic \|\| activeMaterial\.material_id\}[\s\S]*\) : \([\s\S]*<MarkdownPreview content=\{activeMaterialMarkdown\} \/>/,
  "VideoPlayer should prefer deck.html iframe preview for PPT materials and fall back to markdown otherwise",
);

console.log("videoPlayer.ppt-preview tests passed");
