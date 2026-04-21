import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../../src/stitch/pages/VideoPlayer.tsx", import.meta.url), "utf8");

assert.match(
  page,
  /const \[hydratedSessionSnapshot, setHydratedSessionSnapshot\] = useState<AiLectureSessionSnapshot \| null>\(null\);/,
  "Realtime stage should keep the hydrated lecture session snapshot so it can render exported slide images",
);

assert.match(
  page,
  /const realtimeStageSlideImageUrls = Array\.isArray\(hydratedSessionSnapshot\?\.slide_image_urls\)/,
  "Realtime stage should derive a stable list of exported slide images from the session snapshot",
);

assert.match(
  page,
  /const realtimeStageFrameRef = useRef<HTMLDivElement \| null>\(null\);/,
  "Realtime stage should measure the live stage container so the PPT deck can fit fully inside the viewport",
);

assert.match(
  page,
  /const \[realtimeStageFrameWidth, setRealtimeStageFrameWidth\] = useState\(PPT_PREVIEW_BASE_WIDTH\);/,
  "Realtime stage should track the stage width for fit-width scaling",
);

assert.match(
  page,
  /new ResizeObserver\(\(entries\) => \{[\s\S]*setRealtimeStageFrameWidth\(nextWidth\);[\s\S]*\}\);/s,
  "Realtime stage should react to stage resize changes before scaling the PPT background",
);

assert.match(
  page,
  /const realtimeStagePptScale = Math\.min\(1,\s*realtimeStageFrameWidth \/ PPT_PREVIEW_BASE_WIDTH\);/,
  "Realtime stage should scale the PPT deck down to fit the full slide width inside the 16:9 stage",
);

assert.match(
  page,
  /const realtimeStageSlideImageUrl = realtimeStageSlideImageUrls\[activeSlideIndex\] \|\| "";/,
  "Realtime stage should derive the visible background from the current slide image index",
);

assert.match(
  page,
  /setHydratedSessionSnapshot\(snapshot\);/,
  "Realtime stage should store the fetched lecture session snapshot for downstream background rendering",
);

assert.match(
  page,
  /snapshot\.slide_image_urls/,
  "Realtime stage should hydrate slide image urls from the backend session detail payload",
);

assert.match(
  page,
  /const realtimeStagePptPreviewUrl = buildRealtimeStagePptPreviewUrl\(selectedPptPreviewUrl,\s*activeSlideIndex\);/,
  "Realtime stage should keep the iframe preview url only as a fallback path when slide images are unavailable",
);

assert.match(
  page,
  /fetchAuthenticatedBlobUrl\(realtimeStageSlideImageUrl\)[\s\S]*setRealtimeStageSlideObjectUrl\(objectUrl\)/s,
  "Realtime stage should fetch exported slide images with API auth before rendering them as object URLs",
);

assert.match(
  page,
  /realtimeStageSlideObjectUrl \? \([\s\S]*<img[\s\S]*src=\{realtimeStageSlideObjectUrl\}[\s\S]*object-contain[\s\S]*\) : realtimeStagePptPreviewUrl \? \([\s\S]*<iframe/s,
  "Realtime stage should prefer authenticated exported slide image object URLs and only fall back to the iframe preview when images are unavailable",
);

assert.match(
  page,
  /realtimeStagePptPreviewUrl \? \([\s\S]*<iframe[\s\S]*title=\{`\$\{selectedPptMaterial\?\.title \|\| sourcePptMaterial\?\.title \|\| course\.title\} slide \$\{activeSlideIndex \+ 1\}`\}/s,
  "Realtime stage should label the PPT iframe with the current slide number",
);

assert.match(
  page,
  /<video[\s\S]*className="absolute bottom-\[2%\] right-\[1\.8%\] z-20 h-auto w-\[24%\][\s\S]*bg-transparent object-contain mix-blend-multiply/,
  "Realtime stage should pin the digital human layer to the lower-right corner and visually remove the white video background",
);

assert.match(
  page,
  /setActiveSlideIndex\(nextSlideIndex\);[\s\S]*const sentences = await ensureSlideScript\(nextSlideIndex, sessionId\);/s,
  "Realtime autoplay should advance the active slide before generating the next script so the PPT background flips in sync",
);

console.log("videoPlayer.realtime-ppt-stage tests passed");
