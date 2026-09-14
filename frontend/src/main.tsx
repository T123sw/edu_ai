import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
const legacy =
  new URLSearchParams(location.search).get("legacy") === "1" ||
  /^#\/(video-render|player-smoke)/.test(location.hash) ||
  /^#(video-render|player-smoke)/.test(location.hash);
const Entry = legacy
  ? lazy(() => import("./legacyEntry"))
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
