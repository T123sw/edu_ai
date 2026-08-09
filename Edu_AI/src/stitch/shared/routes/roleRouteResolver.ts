import type { AuthUser } from "../../authSession";
import { isStudentRoute } from "../../student/routes/studentRoutes";

const sharedRoutes = new Set(["profile", "settings", "classroom-player", "player-smoke", "video-render"]);

export function defaultHashForRole(role: AuthUser["role"]): string {
  return role === "student" ? "#student-home" : "#home";
}

export function resolveRoleHash(role: AuthUser["role"], hash: string): string {
  const normalized = String(hash || "").startsWith("#") ? String(hash) : `#${String(hash || "")}`;
  const route = normalized.replace(/^#/, "").split("?")[0];
  if (sharedRoutes.has(route)) return normalized;
  if (role === "student") return isStudentRoute(route) ? normalized : defaultHashForRole(role);
  return isStudentRoute(route) ? defaultHashForRole(role) : normalized;
}
