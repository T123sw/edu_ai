import { useEffect, useLayoutEffect, useState } from "react";
import { WorkspaceOverviewPage } from "./pages/WorkspaceOverview";
import { VideoPlayerPage } from "./pages/VideoPlayer";
import { CourseResourcesPage } from "./pages/CourseResources";
import { AIWorkspacePage } from "./pages/AIWorkspace";
import { HomeDashboardPage } from "./pages/HomeDashboard";
import { KnowledgeGraphPage } from "./pages/KnowledgeGraph";
import { PptStudioPage } from "./pages/PptStudio";
import { CourseKnowledgeBasePage } from "./pages/CourseKnowledgeBase";
import { CourseDetailPage, CourseListPage } from "./pages/CourseDetail";
import { CourseEditPage } from "./pages/CourseEdit";
import { ProfilePage } from "./pages/Profile";
import { LoginPage } from "./pages/LoginPage";
import { PlayerSmokePage } from "./pages/_dev/PlayerSmoke";
import { ClassroomVideoRenderPage } from "./pages/_dev/ClassroomVideoRender";
import { ClassroomStudioPage } from "./pages/ClassroomStudio";
import { ClassroomPlayerPage } from "./pages/ClassroomPlayer";
import {
  AppShellProvider,
  ThemeCustomizer,
  defaultCourse,
  routeHref,
  routes,
  type CourseSummary,
  type RouteKey,
  type ThemeName,
} from "./shared";
import { login, verifyToken, type User } from "../services/auth";

const pages = [
  [routes.profile, "Profile", ProfilePage],
  [routes.home, "Home", HomeDashboardPage],
  [routes.course, "Course List", CourseListPage],
  [routes.courseDetail, "Course Detail", CourseDetailPage],
  [routes.workspace, "Workspace", WorkspaceOverviewPage],
  [routes.video, "Video Player", VideoPlayerPage],
  [routes.resources, "Course Resources", CourseResourcesPage],
  [routes.ai, "AI Workspace", AIWorkspacePage],
  [routes.graph, "Knowledge Graph", KnowledgeGraphPage],
  [routes.ppt, "PPT Studio", PptStudioPage],
  [routes.knowledge, "Knowledge Base", CourseKnowledgeBasePage],
  [routes.edit, "Course Edit", CourseEditPage],
  [routes.playerSmoke, "Player Smoke (dev)", PlayerSmokePage],
  [routes.videoRender, "Video Render", ClassroomVideoRenderPage],
  [routes.classroomStudio, "Classroom Studio", ClassroomStudioPage],
  [routes.classroomPlayer, "Classroom Player", ClassroomPlayerPage],
] as const;

const AUTH_STORAGE_KEY = "edu-ai-auth";

function getCurrentRoute(): RouteKey {
  const hash = window.location.hash.replace(/^#/, "");
  const route = hash.split("?")[0] as RouteKey;
  return pages.some(([id]) => id === route) ? route : routes.home;
}

function isFixtureVideoRenderRoute(): boolean {
  if (getCurrentRoute() !== routes.videoRender) return false;
  const query = window.location.hash.split("?")[1] ?? "";
  return new URLSearchParams(query).get("fixture") === "1";
}

function getStoredTheme(): ThemeName {
  const stored = window.localStorage.getItem("stitch-theme");
  return stored === "forest" || stored === "sunset" || stored === "dark" ? stored : "ocean";
}

function getStoredCourse(): CourseSummary | null {
  const raw = window.localStorage.getItem("stitch-course");

  if (!raw) return defaultCourse;

  try {
    return JSON.parse(raw) as CourseSummary;
  } catch {
    return defaultCourse;
  }
}

function getStoredAuth() {
  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);

  if (!raw) return null;

  try {
    return JSON.parse(raw) as { user: User; token: string };
  } catch {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

function resetRouteScrollPosition() {
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

export default function App() {
  const [current, setCurrent] = useState<RouteKey>(getCurrentRoute);
  const [selectedCourse, setSelectedCourse] = useState<CourseSummary | null>(getStoredCourse);
  const [theme, setTheme] = useState<ThemeName>(getStoredTheme);
  const [authReady, setAuthReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    if (!window.location.hash) {
      window.location.hash = routeHref(routes.home);
    }

    const syncRoute = () => setCurrent(getCurrentRoute());
    window.addEventListener("hashchange", syncRoute);
    return () => window.removeEventListener("hashchange", syncRoute);
  }, []);

  useEffect(() => {
    const previousScrollRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    return () => {
      window.history.scrollRestoration = previousScrollRestoration;
    };
  }, []);

  useLayoutEffect(() => {
    resetRouteScrollPosition();
    const frameId = window.requestAnimationFrame(resetRouteScrollPosition);
    return () => window.cancelAnimationFrame(frameId);
  }, [current]);

  useEffect(() => {
    window.localStorage.setItem("stitch-theme", theme);
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (selectedCourse) {
      window.localStorage.setItem("stitch-course", JSON.stringify(selectedCourse));
    }
  }, [selectedCourse]);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      const stored = getStoredAuth();

      if (!stored?.token) {
        if (!cancelled) {
          setAuthenticated(false);
          setAuthReady(true);
        }
        return;
      }

      try {
        const result = await verifyToken(stored.token);
        if (!cancelled) {
          if (result.valid) {
            setAuthenticated(true);
          } else {
            window.localStorage.removeItem(AUTH_STORAGE_KEY);
            setAuthenticated(false);
          }
        }
      } catch {
        if (!cancelled) {
          window.localStorage.removeItem(AUTH_STORAGE_KEY);
          setAuthenticated(false);
        }
      } finally {
        if (!cancelled) {
          setAuthReady(true);
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  const ActivePage = pages.find(([id]) => id === current)?.[2] ?? HomeDashboardPage;
  const isStandaloneDevRoute = current === routes.playerSmoke || isFixtureVideoRenderRoute();
  const isVideoRenderRoute = current === routes.videoRender;

  async function handleLogin(payload: { username: string; password: string }) {
    const result = await login(payload.username, payload.password);
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(result));
    setAuthenticated(true);
    setAuthReady(true);
  }

  function handleLogout() {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    setAuthenticated(false);
    setAuthReady(true);
    window.location.hash = routeHref(routes.home);
  }

  return (
    <AppShellProvider
      selectedCourse={selectedCourse}
      setSelectedCourse={setSelectedCourse}
      theme={theme}
      setTheme={setTheme}
      logout={handleLogout}
    >
      {isStandaloneDevRoute ? (
        // Dev-only: no backend dependency, so it skips the auth gate.
        <ActivePage />
      ) : !authReady ? (
        <div className="grid min-h-screen place-items-center text-sm text-slate-500">Loading...</div>
      ) : authenticated ? (
        <div key={current} className="route-stage">
          <ActivePage />
        </div>
      ) : (
        <LoginPage onLogin={handleLogin} />
      )}
      {isVideoRenderRoute ? null : <ThemeCustomizer />}
    </AppShellProvider>
  );
}
