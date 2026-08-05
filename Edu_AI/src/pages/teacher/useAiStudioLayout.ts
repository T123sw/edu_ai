import { useEffect, useRef, useState } from "react";

import {
  getAiStudioLayoutMode,
  type AiStudioLayoutMode,
} from "./aiStudioLayout";

export function useAiStudioLayout<T extends HTMLElement>() {
  const workspaceRef = useRef<T | null>(null);
  const [layoutMode, setLayoutMode] = useState<AiStudioLayoutMode>("drawer");

  useEffect(() => {
    const element = workspaceRef.current;
    if (!element) return;

    const updateMode = () => {
      setLayoutMode(getAiStudioLayoutMode(element.clientWidth));
    };
    updateMode();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateMode);
      return () => window.removeEventListener("resize", updateMode);
    }

    const observer = new ResizeObserver(updateMode);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { workspaceRef, layoutMode };
}
