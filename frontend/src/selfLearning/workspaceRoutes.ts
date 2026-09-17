import { buildRoleCourseHash } from "../stitch/shared/routes/roleCourseRouteResolver";
import type { AuthUser } from "../stitch/authSession";

export function isLearningWorkspace() {
  const params = new URLSearchParams(window.location.search);
  return params.get("workspace") === "1" && params.get("legacy") !== "1";
}

export function learningHomeHref() {
  const url = new URL(window.location.href);
  url.searchParams.delete("workspace");
  url.searchParams.delete("legacy");
  url.hash = "/";
  return `${url.pathname}${url.search}${url.hash}`;
}

export function courseWorkspaceHref(courseId: string, role?: string) {
  const url = new URL(window.location.href);
  for (const key of ["legacy", "preview", "demo"]) url.searchParams.delete(key);
  url.searchParams.set("workspace", "1");
  url.hash = buildRoleCourseHash(role as AuthUser["role"], "classroom-studio", courseId);
  return `${url.pathname}${url.search}${url.hash}`;
}
