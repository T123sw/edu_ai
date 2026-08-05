import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const studioPanel = readFileSync(
  new URL("../../src/components/teacher/StudioPanel.tsx", import.meta.url),
  "utf8",
);
const studioCss = readFileSync(
  new URL("../../src/components/teacher/StudioPanel.css", import.meta.url),
  "utf8",
);
const workspace = readFileSync(
  new URL("../../src/stitch/pages/AIWorkspace.tsx", import.meta.url),
  "utf8",
);
const workspaceLayoutHook = readFileSync(
  new URL("../../src/pages/teacher/useAiStudioLayout.ts", import.meta.url),
  "utf8",
);
const workspaceCss = readFileSync(
  new URL("../../src/pages/teacher/AiStudioPage.css", import.meta.url),
  "utf8",
);

assert.doesNotMatch(
  studioPanel,
  /六个功能/,
  "StudioPanel should not retain the obsolete six-entry layout assumption",
);
assert.match(
  studioPanel,
  /报告、教案、博客、习题、PPT、闪卡、思维导图和小游戏/,
  "empty state should explain all eight available resource types",
);
assert.match(
  studioCss,
  /container-type:\s*inline-size/,
  "the studio grid should respond to its panel width, not only viewport width",
);
assert.match(
  studioCss,
  /@container\s*\(max-width:\s*419px\)[\s\S]*grid-template-columns:\s*repeat\(2/,
  "narrow studio panels should switch to two columns",
);
assert.match(
  studioCss,
  /@container\s*\(max-width:\s*279px\)[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
  "very narrow studio panels should switch to one column",
);
assert.match(
  studioCss,
  /\.studio-panel\s*\{[\s\S]*overflow-y:\s*auto/,
  "the entire generation panel should remain scrollable when entries grow",
);
assert.match(
  workspaceLayoutHook,
  /ResizeObserver/,
  "workspace breakpoints should observe the actual content container",
);
assert.match(
  workspace,
  /ai-studio-panel-switcher/,
  "drawer layout should keep both side panels reachable",
);
assert.match(
  workspaceCss,
  /\.ai-studio-page--drawer[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
  "drawer layout should reserve the full row for the conversation",
);

console.log("studioPanel responsive layout tests passed");
