import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../../src/stitch/pages/VideoPlayer.tsx", import.meta.url), "utf8");

assert.match(
  page,
  /const PPT_PREVIEW_BASE_WIDTH = 1920;/,
  "VideoPlayer should define the same fixed PPT preview base width used by the studio preview",
);

assert.match(
  page,
  /const pptPreviewFrameRef = useRef<HTMLDivElement \| null>\(null\);/,
  "VideoPlayer should measure the PPT preview container width",
);

assert.match(
  page,
  /const \[pptPreviewFrameWidth, setPptPreviewFrameWidth\] = useState\(PPT_PREVIEW_BASE_WIDTH\);/,
  "VideoPlayer should track the live PPT preview frame width for fit-width scaling",
);

assert.match(
  page,
  /new ResizeObserver\(\(entries\) => \{[\s\S]*setPptPreviewFrameWidth\(nextWidth\);[\s\S]*\}\);/,
  "VideoPlayer should update PPT preview scaling when the preview container width changes",
);

assert.match(
  page,
  /const pptPreviewScale = Math\.min\(1,\s*pptPreviewFrameWidth \/ PPT_PREVIEW_BASE_WIDTH\);/,
  "VideoPlayer should scale the PPT iframe down to fit the available width",
);

assert.match(
  page,
  /ref=\{pptPreviewFrameRef\}[\s\S]*<iframe[\s\S]*width: `\$\{PPT_PREVIEW_BASE_WIDTH\}px`[\s\S]*height: `calc\(100% \/ \$\{pptPreviewScale\}\)`[\s\S]*transform: `scale\(\$\{pptPreviewScale\}\)`/,
  "VideoPlayer should render the PPT iframe with fixed internal width and fit-width scaling",
);

console.log("videoPlayer.ppt-preview-fit-width tests passed");
