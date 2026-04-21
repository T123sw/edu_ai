import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../../src/stitch/pages/VideoPlayer.tsx", import.meta.url), "utf8");
const exportHelper = readFileSync(new URL("../../src/stitch/wordExport.ts", import.meta.url), "utf8");

assert.match(
  exportHelper,
  /export function isCourseMaterialWordExportable\(/,
  "Word export helper should expose an exportability guard for course materials",
);

assert.match(
  exportHelper,
  /new Set\(\["report", "lesson_plan", "quiz", "blog"\]\)/,
  "Word export helper should explicitly allow text-first course material types",
);

assert.match(
  exportHelper,
  /new Set\(\["ppt", "ai_lecture_session"\]\)/,
  "Word export helper should explicitly block non-document material types for Word export",
);

assert.match(
  exportHelper,
  /application\/msword;charset=utf-8/,
  "Word export helper should generate a Word-compatible blob",
);

assert.match(
  exportHelper,
  /\.download = `\$\{safeFileName\}\.doc`/,
  "Word export helper should download the exported document with a .doc extension",
);

assert.match(
  exportHelper,
  /export function getCourseMaterialPptExportUrl\(/,
  "Export helper should expose a PPT export url resolver for course materials",
);

assert.match(
  exportHelper,
  /pptx_url/,
  "Export helper should read generated PPT export urls from pptx_url fields",
);

assert.match(
  exportHelper,
  /API_BASE_URL/,
  "Export helper should resolve relative PPT asset urls against the stitch API base url",
);

assert.match(
  page,
  /import\s+\{[\s\S]*exportCourseMaterialAsWord,[\s\S]*getCourseMaterialPptExportUrl,[\s\S]*getCourseMaterialPptPreviewUrl,[\s\S]*isCourseMaterialWordExportable[\s\S]*\}\s+from\s+["']\.\.\/wordExport["'];/,
  "VideoPlayer should import the shared course material export helpers",
);

assert.match(
  page,
  /const canExportActiveMaterial = isCourseMaterialWordExportable\(activeMaterial,\s*activeMaterialMarkdown\);/,
  "VideoPlayer should compute whether the active course material can be exported as a Word document",
);

assert.match(
  page,
  /const activeMaterialPptExportUrl = getCourseMaterialPptExportUrl\(activeMaterial\);/,
  "VideoPlayer should resolve the PPT export url for generated PPT course materials",
);

assert.match(
  page,
  /const handleExportActiveMaterial = \(\) => \{[\s\S]*exportCourseMaterialAsWord\(activeMaterial,\s*activeMaterialMarkdown\);[\s\S]*\};/,
  "VideoPlayer should export the active course material through the shared Word helper",
);

assert.match(
  page,
  /canExportActiveMaterial \? \([\s\S]*onClick=\{handleExportActiveMaterial\}[\s\S]*DOC/,
  "VideoPlayer should show a DOC export action only for exportable text materials",
);

assert.match(
  page,
  /activeMaterialPptExportUrl \? \([\s\S]*window\.open\(activeMaterialPptExportUrl,\s*["_']_blank["_'],\s*["']noopener,noreferrer["']\)[\s\S]*PPT/,
  "VideoPlayer should show a PPT export action that reuses the generated deck download url",
);

console.log("videoPlayer.material-doc-export tests passed");
