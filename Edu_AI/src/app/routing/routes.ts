export const routes = {
  workspace: "workspace",
  course: "course",
  courseDetail: "course-detail",
  video: "video",
  ai: "ai",
  home: "home",
  profile: "profile",
  graph: "graph",
  ppt: "ppt",
  resources: "resources",
  knowledge: "knowledge",
  edit: "edit",
} as const;

export type RouteKey = (typeof routes)[keyof typeof routes];
export type ThemeName = "ocean" | "forest" | "sunset" | "dark";

export function routeHref(route: RouteKey) {
  return `#${route}`;
}
