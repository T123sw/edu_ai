import { routes, type RouteKey, type ThemeName } from "./routes";
import { defaultCourse, type CourseSummary } from "../providers/AppShellProvider";

export function getCurrentRoute(pages: ReadonlyArray<readonly [RouteKey, string, unknown]>): RouteKey {
  const hash = window.location.hash.replace(/^#/, "");
  const route = hash.split("?")[0] as RouteKey;
  return pages.some(([id]) => id === route) ? route : routes.home;
}

export function getStoredTheme(): ThemeName {
  const stored = window.localStorage.getItem("stitch-theme");
  return stored === "forest" || stored === "sunset" || stored === "dark" ? stored : "ocean";
}

export function getStoredCourse(): CourseSummary | null {
  const raw = window.localStorage.getItem("stitch-course");

  if (!raw) return defaultCourse;

  try {
    return JSON.parse(raw) as CourseSummary;
  } catch {
    return defaultCourse;
  }
}

export function resetRouteScrollPosition() {
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
  document.querySelectorAll("[data-route-scroll-root]").forEach((element) => {
    if (element instanceof HTMLElement) {
      element.scrollTop = 0;
      element.scrollLeft = 0;
    }
  });
}
