import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { initializeAppearance } from './stitch/theme/appearance';
import './stitch/theme/appearance.css';

initializeAppearance();
const legacy =
  new URLSearchParams(location.search).get("legacy") === "1" ||
  /^#\/(video-render|player-smoke)/.test(location.hash) ||
  /^#(video-render|player-smoke)/.test(location.hash);
const Entry = legacy
  ? lazy(() => import("./legacyEntry"))
  : new URLSearchParams(location.search).get("account") === "1"
    ? lazy(() => import("./liveLearning/AccountEntry"))
  : new URLSearchParams(location.search).get("liveWorkbench") === "1"
    ? lazy(() => import("./liveLearning/WorkbenchEntry"))
  : new URLSearchParams(location.search).get("learningPlayer") === "1"
    ? lazy(() => import("./liveLearning/MaterialEntry"))
  : new URLSearchParams(location.search).get("review") === "1" && new URLSearchParams(location.search).get("workbench") === "1"
    ? lazy(() => import("./frontendReview/WorkbenchEntry"))
  : new URLSearchParams(location.search).get("workspace") === "1"
    ? lazy(() => import("./learningWorkspaceEntry"))
    : lazy(() => import("./selfLearning/App"));

const container = document.getElementById("root");

if (!container) {
  throw new Error("Root element '#root' was not found.");
}

createRoot(container).render(
  <StrictMode>
    <Suspense fallback={<p>正在打开学习空间…</p>}>
      <Entry />
    </Suspense>
  </StrictMode>,
);
