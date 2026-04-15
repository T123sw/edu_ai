import { useEffect, useState, type FormEvent } from "react";
import { WorkspaceOverviewPage } from "./pages/WorkspaceOverview";
import { VideoPlayerPage } from "./pages/VideoPlayer";
import { AIWorkspacePage } from "./pages/AIWorkspace";
import { HomeDashboardPage } from "./pages/HomeDashboard";
import { KnowledgeGraphPage } from "./pages/KnowledgeGraph";
import { PptStudioPage } from "./pages/PptStudio";
import { CourseResourcesPage } from "./pages/CourseResources";
import { CourseKnowledgeBasePage } from "./pages/CourseKnowledgeBase";
import { CourseDetailPage } from "./pages/CourseDetail";
import { CourseEditPage } from "./pages/CourseEdit";
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
  [routes.home, "首页", HomeDashboardPage],
  [routes.course, "课程详情", CourseDetailPage],
  [routes.workspace, "课程工作台", WorkspaceOverviewPage],
  [routes.video, "视频学习", VideoPlayerPage],
  [routes.ai, "AI 问答", AIWorkspacePage],
  [routes.graph, "知识图谱", KnowledgeGraphPage],
  [routes.ppt, "PPT 工作室", PptStudioPage],
  [routes.resources, "课程资源", CourseResourcesPage],
  [routes.knowledge, "课程知识库", CourseKnowledgeBasePage],
  [routes.edit, "详情编辑", CourseEditPage],
] as const;

const AUTH_STORAGE_KEY = "edu-ai-auth";

function getCurrentRoute(): RouteKey {
  const hash = window.location.hash.replace(/^#/, "") as RouteKey;
  return pages.some(([id]) => id === hash) ? hash : routes.home;
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

function AuthScreen({
  onLogin,
}: {
  onLogin: (payload: { username: string; password: string }) => Promise<void>;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setLoading(true);
      setError(null);
      await onLogin({ username, password });
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,#0f172a_0%,#1d4ed8_45%,#eff6ff_100%)] px-6 py-10 text-slate-900">
      <div className="mx-auto grid min-h-[calc(100vh-80px)] max-w-6xl items-center gap-8 lg:grid-cols-[1.1fr_460px]">
        <div className="text-white">
          <p className="text-sm font-bold uppercase tracking-[0.32em] text-white/70">Edu AI</p>
          <h1 className="mt-6 max-w-2xl text-5xl font-black leading-[0.95] tracking-tight md:text-6xl">教师工作台已切到 Stitch 前端</h1>
          <p className="mt-6 max-w-xl text-base leading-8 text-white/82">
            这套界面现在直接连接 `Edu_AI` 后端。由于课程资源、知识图谱、视频检索和问答都需要 Bearer Token，先登录再进入工作区。
          </p>
        </div>

        <div className="rounded-[32px] border border-white/40 bg-white/90 p-8 shadow-[0_24px_80px_rgba(15,23,42,0.24)] backdrop-blur-xl">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-[var(--accent-strong)]">登录</p>
          <h2 className="mt-3 text-3xl font-black text-[var(--accent-strong)]">进入课程工作区</h2>
          <form className="mt-8 space-y-4" onSubmit={(event) => void handleSubmit(event)}>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">账号</span>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none"
                placeholder="请输入账号"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">密码</span>
              <input
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                type="password"
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none"
                placeholder="请输入密码"
              />
            </label>
            {error ? <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-600">{error}</div> : null}
            <button
              type="submit"
              disabled={loading || !username.trim() || !password.trim()}
              className="w-full rounded-2xl bg-[var(--accent)] px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "登录中..." : "登录"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
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

  if (!authReady) {
    return <div className="grid min-h-screen place-items-center text-sm text-slate-500">正在验证登录状态...</div>;
  }

  if (!authenticated) {
    return <AuthScreen onLogin={handleLogin} />;
  }

  return (
    <AppShellProvider
      selectedCourse={selectedCourse}
      setSelectedCourse={setSelectedCourse}
      theme={theme}
      setTheme={setTheme}
    >
      <div key={current} className="route-stage">
        <ActivePage />
      </div>
      <ThemeCustomizer />
    </AppShellProvider>
  );
}
