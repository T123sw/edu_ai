import {
  Component,
  Suspense,
  lazy,
  useEffect,
  useLayoutEffect,
  useState,
  type ErrorInfo,
  type ReactNode,
} from "react";
import { LoginPage } from "./pages/LoginPage";
import { backendCourseToSummary } from "./api/courses";
import {
  AuthSessionProvider,
  AUTH_STORAGE_KEY,
  normalizeAuthUser,
  parseStoredAuthSession,
  type AuthUser,
} from "./authSession";
import {
  CourseRouteProvider,
  useCourseRoute,
} from "./course/CourseRouteProvider";
import {
  AppShellProvider,
  ThemeCustomizer,
  routeHref,
  routes,
  type CourseSummary,
  type RouteKey,
  type ThemeName,
} from "./shared";
import { login, verifyToken } from "../services/auth";
import { isCourseWorkspaceRoute } from "./course/courseNavigation";
import { isStudentRoute, type StudentRoute } from "./student/routes/studentRoutes";
import { defaultHashForRole, resolveRoleHash } from "./shared/routes/roleRouteResolver";

const WorkspaceOverviewPage = lazy(() => import("./pages/WorkspaceOverview").then((module) => ({ default: module.WorkspaceOverviewPage })));
const CourseResourcesPage = lazy(() => import("./pages/CourseResources").then((module) => ({ default: module.CourseResourcesPage })));
const CourseLearningPage = lazy(() => import("./pages/CourseLearning").then((module) => ({ default: module.CourseLearningPage })));
const AIWorkspacePage = lazy(() => import("./pages/AIWorkspace").then((module) => ({ default: module.AIWorkspacePage })));
const HomeDashboardPage = lazy(() => import("./pages/HomeDashboard").then((module) => ({ default: module.HomeDashboardPage })));
const PptStudioPage = lazy(() => import("./pages/PptStudio").then((module) => ({ default: module.PptStudioPage })));
const CourseKnowledgePage = lazy(() => import("./pages/CourseKnowledge").then((module) => ({ default: module.CourseKnowledgePage })));
const LegacyKnowledgeGraphRedirect = lazy(() => import("./pages/CourseKnowledge").then((module) => ({ default: module.LegacyKnowledgeGraphRedirect })));
const CourseDetailPage = lazy(() => import("./pages/CourseDetail").then((module) => ({ default: module.CourseDetailPage })));
const CourseListPage = lazy(() => import("./pages/CourseDetail").then((module) => ({ default: module.CourseListPage })));
const CourseEditPage = lazy(() => import("./pages/CourseEdit").then((module) => ({ default: module.CourseEditPage })));
const ProfilePage = lazy(() => import("./pages/Profile").then((module) => ({ default: module.ProfilePage })));
const RuntimeSettingsPage = lazy(() => import("./pages/RuntimeSettings").then((module) => ({ default: module.RuntimeSettingsPage })));
const PlayerSmokePage = lazy(() => import("./pages/_dev/PlayerSmoke").then((module) => ({ default: module.PlayerSmokePage })));
const ClassroomVideoRenderPage = lazy(() => import("./pages/_dev/ClassroomVideoRender").then((module) => ({ default: module.ClassroomVideoRenderPage })));
const ClassroomStudioPage = lazy(() => import("./pages/ClassroomStudio").then((module) => ({ default: module.ClassroomStudioPage })));
const ClassroomPlayerPage = lazy(() => import("./pages/ClassroomPlayer").then((module) => ({ default: module.ClassroomPlayerPage })));
const StudentApp = lazy(() => import("./student/StudentApp").then((module) => ({ default: module.StudentApp })));
const GlobalJobManager = lazy(() => import("../jobs/GlobalJobManager").then((module) => ({ default: module.GlobalJobManager })));
const CourseShell = lazy(() => import("./course/CourseShell").then((module) => ({ default: module.CourseShell })));

const pages = [
  [routes.profile, "Profile", ProfilePage],
  [routes.settings, "Runtime Settings", RuntimeSettingsPage],
  [routes.home, "Home", HomeDashboardPage],
  [routes.course, "Course List", CourseListPage],
  [routes.courseDetail, "Course Detail", CourseDetailPage],
  [routes.learning, "Course Learning", CourseLearningPage],
  [routes.workspace, "Workspace", WorkspaceOverviewPage],
  [routes.resources, "Personal Resources", CourseResourcesPage],
  [routes.ai, "AI Workspace", AIWorkspacePage],
  [routes.graph, "Knowledge Graph", LegacyKnowledgeGraphRedirect],
  [routes.ppt, "PPT Studio", PptStudioPage],
  [routes.knowledge, "Course Knowledge", CourseKnowledgePage],
  [routes.edit, "Course Edit", CourseEditPage],
  [routes.playerSmoke, "Player Smoke (dev)", PlayerSmokePage],
  [routes.videoRender, "Video Render", ClassroomVideoRenderPage],
  [routes.classroomStudio, "Classroom Studio", ClassroomStudioPage],
  [routes.classroomPlayer, "Classroom Player", ClassroomPlayerPage],
] as const;

type AppRouteKey = RouteKey | StudentRoute;

class RouteErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Route rendering failed", error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <main className="grid min-h-screen place-items-center bg-slate-50 px-6 text-center text-slate-700">
        <section className="max-w-lg rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <h1 className="text-xl font-semibold text-slate-900">页面加载失败</h1>
          <p className="mt-3 text-sm leading-6">
            页面模块没有正常启动。请刷新后重试；如果问题持续出现，请将下方信息提供给管理员。
          </p>
          <pre className="mt-4 overflow-auto rounded-lg bg-slate-100 p-3 text-left text-xs text-slate-600">
            {this.state.error.message}
          </pre>
          <button
            type="button"
            className="mt-5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            onClick={() => window.location.reload()}
          >
            重新加载
          </button>
        </section>
      </main>
    );
  }
}

function DeferredGlobalJobManager({
  enabled,
  showLauncher,
  currentCourseId,
  currentCourseTitle,
}: {
  enabled: boolean;
  showLauncher: boolean;
  currentCourseId: string | null;
  currentCourseTitle: string | null;
}) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setReady(true), 1_500);
    return () => window.clearTimeout(timer);
  }, []);

  return ready ? (
    <Suspense fallback={null}>
      <GlobalJobManager
        enabled={enabled}
        showLauncher={showLauncher}
        currentCourseId={currentCourseId}
        currentCourseTitle={currentCourseTitle}
      />
    </Suspense>
  ) : null;
}

function getCurrentRoute(): AppRouteKey {
  const hash = window.location.hash.replace(/^#/, "");
  const route = hash.split("?")[0];
  if (isStudentRoute(route)) return route;
  return pages.some(([id]) => id === route) ? route as RouteKey : routes.home;
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

  if (!raw) return null;

  try {
    return JSON.parse(raw) as CourseSummary;
  } catch {
    return null;
  }
}

function getStoredAuth() {
  const session = parseStoredAuthSession(
    window.localStorage.getItem(AUTH_STORAGE_KEY),
  );
  if (!session) {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  }
  return session;
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
  const [current, setCurrent] = useState<AppRouteKey>(getCurrentRoute);
  const [rememberedCourse, setRememberedCourse] = useState<CourseSummary | null>(getStoredCourse);
  const [theme, setTheme] = useState<ThemeName>(getStoredTheme);
  const [authReady, setAuthReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    if (!window.location.hash) {
      window.location.hash = routeHref(routes.home);
    }

    const syncRoute = () => {
      setCurrent(getCurrentRoute());
    };
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
          const verifiedUser = normalizeAuthUser(result.user);
          if (result.valid && verifiedUser) {
            setAuthUser(verifiedUser);
            setAuthenticated(true);
          } else {
            window.localStorage.removeItem(AUTH_STORAGE_KEY);
            setAuthUser(null);
            setAuthenticated(false);
          }
        }
      } catch {
        if (!cancelled) {
          window.localStorage.removeItem(AUTH_STORAGE_KEY);
          setAuthUser(null);
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

  useLayoutEffect(() => {
    if (!authReady || !authenticated || !authUser) return;
    const nextHash = resolveRoleHash(authUser.role, window.location.hash);
    if (nextHash !== window.location.hash) {
      window.location.replace(nextHash);
    }
  }, [authReady, authenticated, authUser, current]);

  async function handleLogin(payload: { username: string; password: string }) {
    const result = await login(payload.username, payload.password);
    const loggedInUser = normalizeAuthUser(result.user);
    if (!loggedInUser) throw new Error("登录用户角色无效");
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(result));
    window.location.hash = defaultHashForRole(loggedInUser.role);
    setAuthUser(loggedInUser);
    setAuthenticated(true);
    setAuthReady(true);
  }

  function handleLogout() {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    setAuthUser(null);
    setAuthenticated(false);
    setAuthReady(true);
    window.location.hash = routeHref(routes.home);
  }

  return (
    <AuthSessionProvider user={authUser} authenticated={authenticated}>
      <CourseRouteProvider
        enabled={authenticated}
        rememberedCourseId={rememberedCourse?.id}
      >
        <AppPresentation
          current={current}
          rememberedCourse={rememberedCourse}
          setRememberedCourse={setRememberedCourse}
          theme={theme}
          setTheme={setTheme}
          authReady={authReady}
          authenticated={authenticated}
          authUser={authUser}
          handleLogin={handleLogin}
          handleLogout={handleLogout}
        />
      </CourseRouteProvider>
    </AuthSessionProvider>
  );
}

function AppPresentation({
  current,
  rememberedCourse,
  setRememberedCourse,
  theme,
  setTheme,
  authReady,
  authenticated,
  authUser,
  handleLogin,
  handleLogout,
}: {
  current: AppRouteKey;
  rememberedCourse: CourseSummary | null;
  setRememberedCourse: (course: CourseSummary | null) => void;
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
  authReady: boolean;
  authenticated: boolean;
  authUser: AuthUser | null;
  handleLogin: (payload: { username: string; password: string }) => Promise<void>;
  handleLogout: () => void;
}) {
  const routeCourse = useCourseRoute();
  const selectedCourse = routeCourse.course
    ? backendCourseToSummary(routeCourse.course, 0)
    : null;

  useEffect(() => {
    if (!routeCourse.course) return;
    const remembered = backendCourseToSummary(routeCourse.course, 0);
    window.localStorage.setItem("stitch-course", JSON.stringify(remembered));
    setRememberedCourse(remembered);
  }, [routeCourse.course, setRememberedCourse]);

  const ActivePage = pages.find(([id]) => id === current)?.[2] ?? HomeDashboardPage;
  const isStandaloneDevRoute = current === routes.playerSmoke || isFixtureVideoRenderRoute();
  const isVideoRenderRoute = current === routes.videoRender;
  const isCourseRoute = isCourseWorkspaceRoute(current);
  const isStudentWorkspace = isStudentRoute(current);
  const authorizedHash = authUser ? resolveRoleHash(authUser.role, window.location.hash) : window.location.hash;
  const routeAuthorized = !authenticated || !authUser || authorizedHash === window.location.hash;
  const shellCourse = routeCourse.courseId
    ? selectedCourse
    : current === routes.home || isStudentWorkspace
      ? selectedCourse ?? rememberedCourse
      : null;
  const jobCenterCourseId = current === routes.home ? null : routeCourse.courseId;
  const jobCenterCourseTitle = jobCenterCourseId
    ? routeCourse.course?.title ?? null
    : null;

  function rememberCourse(course: CourseSummary | null) {
    setRememberedCourse(course);
    if (course) {
      window.localStorage.setItem("stitch-course", JSON.stringify(course));
    }
  }

  return (
    <AppShellProvider
      selectedCourse={shellCourse}
      setSelectedCourse={rememberCourse}
      theme={theme}
      setTheme={setTheme}
      logout={handleLogout}
    >
      <RouteErrorBoundary key={current}>
      <Suspense fallback={<div className="grid min-h-screen place-items-center text-sm text-slate-500">正在加载页面…</div>}>
        {isStandaloneDevRoute ? (
          // Dev-only: no backend dependency, so it skips the auth gate.
          <ActivePage />
        ) : !authReady ? (
          <div className="grid min-h-screen place-items-center text-sm text-slate-500">Loading...</div>
        ) : authenticated && !routeAuthorized ? (
          <div className="grid min-h-screen place-items-center text-sm text-slate-500">正在进入对应工作区…</div>
        ) : authenticated ? (
          <>
            <DeferredGlobalJobManager
              enabled={!isVideoRenderRoute}
              showLauncher={authUser?.role !== "student" && !isCourseRoute && !isStudentWorkspace}
              currentCourseId={jobCenterCourseId}
              currentCourseTitle={jobCenterCourseTitle}
            />
            <div key={current} className="route-stage">
              {isStudentWorkspace ? (
                <StudentApp current={current} />
              ) : isCourseRoute ? (
                <CourseShell activeRoute={current}>
                  <ActivePage />
                </CourseShell>
              ) : (
                <ActivePage />
              )}
            </div>
          </>
        ) : (
          <LoginPage onLogin={handleLogin} />
        )}
      </Suspense>
      </RouteErrorBoundary>
      {isVideoRenderRoute || authUser?.role === "student" ? null : <ThemeCustomizer />}
    </AppShellProvider>
  );
}
