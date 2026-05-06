import { useEffect, useLayoutEffect, useState } from "react";
import { WorkspaceOverviewPage } from "../stitch/pages/WorkspaceOverview";
import { VideoPlayerPage } from "../stitch/pages/VideoPlayer";
import { CourseResourcesPage } from "../stitch/pages/CourseResources";
import { AIWorkspacePage } from "../stitch/pages/AIWorkspace";
import { HomeDashboardPage } from "../stitch/pages/HomeDashboard";
import { KnowledgeGraphPage } from "../stitch/pages/KnowledgeGraph";
import { PptStudioPage } from "../stitch/pages/PptStudio";
import { CourseKnowledgeBasePage } from "../stitch/pages/CourseKnowledgeBase";
import { CourseDetailPage, CourseListPage } from "../stitch/pages/CourseDetail";
import { CourseEditPage } from "../stitch/pages/CourseEdit";
import { ProfilePage } from "../stitch/pages/Profile";
import { LoginPage } from "../stitch/pages/LoginPage";
import { ThemeCustomizer } from "./shell";
import { AppShellProvider, type CourseSummary } from "./providers";
import {
  getCurrentRoute,
  getStoredCourse,
  getStoredTheme,
  resetRouteScrollPosition,
  routeHref,
  routes,
  type RouteKey,
  type ThemeName,
} from "./routing";
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
] as const;

const AUTH_STORAGE_KEY = "edu-ai-auth";

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

export default function App() {
  const [current, setCurrent] = useState<RouteKey>(() => getCurrentRoute(pages));
  const [selectedCourse, setSelectedCourse] = useState<CourseSummary | null>(getStoredCourse);
  const [theme, setTheme] = useState<ThemeName>(getStoredTheme);
  const [authReady, setAuthReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    if (!window.location.hash) {
      window.location.hash = routeHref(routes.home);
    }

    const syncRoute = () => setCurrent(getCurrentRoute(pages));
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
      {!authReady ? (
        <div className="grid min-h-screen place-items-center text-sm text-slate-500">Loading...</div>
      ) : authenticated ? (
        <div key={current} className="route-stage">
          <ActivePage />
        </div>
      ) : (
        <LoginPage onLogin={handleLogin} />
      )}
      <ThemeCustomizer />
    </AppShellProvider>
  );
}
