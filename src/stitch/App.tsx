import { useEffect, useState } from "react";
import { WorkspaceOverviewPage } from "./pages/WorkspaceOverview";
import { VideoPlayerPage } from "./pages/VideoPlayer";
import { AIWorkspacePage } from "./pages/AIWorkspace";
import { HomeDashboardPage } from "./pages/HomeDashboard";
import { KnowledgeGraphPage } from "./pages/KnowledgeGraph";
import { PptStudioPage } from "./pages/PptStudio";
import { CourseKnowledgeBasePage } from "./pages/CourseKnowledgeBase";
import { CourseDetailPage, CourseListPage } from "./pages/CourseDetail";
import { CourseEditPage } from "./pages/CourseEdit";
import { ProfilePage } from "./pages/Profile";
import { LoginPage } from "./pages/LoginPage";
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
  [routes.home, "首页", HomeDashboardPage],
  [routes.course, "我的课程", CourseListPage],
  [routes.courseDetail, "课程详情", CourseDetailPage],
  [routes.workspace, "课程工作台", WorkspaceOverviewPage],
  [routes.video, "视频学习", VideoPlayerPage],
  [routes.ai, "AI 问答", AIWorkspacePage],
  [routes.graph, "知识图谱", KnowledgeGraphPage],
  [routes.ppt, "PPT 工作室", PptStudioPage],
  [routes.knowledge, "课程知识库", CourseKnowledgeBasePage],
  [routes.edit, "详情编辑", CourseEditPage],
] as const;

const AUTH_STORAGE_KEY = "edu-ai-auth";

function getCurrentRoute(): RouteKey {
  const hash = window.location.hash.replace(/^#/, "");
  const route = hash.split("?")[0] as RouteKey;
  if (route === routes.resources) {
    window.location.hash = routeHref(routes.video);
    return routes.video;
  }
  return pages.some(([id]) => id === route) ? route : routes.home;
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
        <div className="grid min-h-screen place-items-center text-sm text-slate-500">正在验证登录状态...</div>
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
