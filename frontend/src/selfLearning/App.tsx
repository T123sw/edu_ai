import { lazy, Suspense, useEffect, useState } from "react";
import { AuthProvider, useAuth } from "../context/AuthContext";
import { Home } from "./Home";
import { LoginPage } from "../stitch/pages/LoginPage";
import { Classroom } from "./Classroom";
import { ResourceCenter } from "./Library";
import { addToLearning } from "./library";
import { createLearningSession, reviewEnabled, reviewOwner, reviewRole, reviewWorkbenchHref } from "./review";
import { PublishDialog } from "./PublishDialog";
import {
  addClassroom,
  createClassroom,
  startShared,
  updateRoom,
  type Classroom as Room,
} from "./model";
import { useLearningStore } from "./store";
import { Brand, Empty, Icon } from "./ui";
import "./styles.css";
import "./review.css";
import "./homeRefresh.css";

function useRoute() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const update = () => {
      setHash(window.location.hash);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  const [path, query] = hash.replace(/^#/, "").split("?");
  return { path: path || "/", query: new URLSearchParams(query) };
}
function LearningApp({
  username,
  role,
  preview,
  review = false,
  onLogout,
}: {
  username: string;
  role?: string;
  preview?: boolean;
  review?: boolean;
  onLogout: () => void;
}) {
  // Separate showcase storage preserves any progress in the original preview.
  const showcase =
    review || (!!preview && new URLSearchParams(location.search).get("demo") === "1");
  const owner = review ? reviewOwner() : `${preview ? "preview" : "user"}:${username}${showcase ? ":showcase" : ""}`;
  const { state, setState, shared, setShared, storageError } = useLearningStore(owner, showcase);
  const [workbenchSession] = useState(() => review ? undefined : createLearningSession(owner, role));
  const { path, query } = useRoute();
  const [publish, setPublish] = useState(false);
  const [account, setAccount] = useState(false);
  const [notice, setNotice] = useState("");
  const roomId = path.startsWith("/classroom/")
    ? path.slice("/classroom/".length)
    : query.get("classroom") || "";
  const room = state.rooms.find((r) => r.id === roomId);
  const home = path === "/";
  const studio = path === "/studio";
  const resources = path === "/resources";
  const PageHeader = home ? "div" : "header";
  const workbenchRoom = room || state.rooms[0];
  const workbenchHref = workbenchRoom ? reviewWorkbenchHref(workbenchRoom, undefined, workbenchSession) : "#/";
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(timer);
  }, [notice]);
  function open(value: Room, isShared?: boolean) {
    if (isShared) {
      const [next, copy] = startShared(state, value);
      setState(updateRoom(next, copy.id, r => ({ ...r, updatedAt: Date.now() })));
      location.hash = `/classroom/${copy.id}`;
    } else {
      setState(s => updateRoom(s, value.id, r => ({ ...r, updatedAt: Date.now() })));
      location.hash = `/classroom/${value.id}`;
    }
  }
  return (
    <div className={`sl-app ${review ? "frontend-review" : ""} ${room && !studio && !resources ? "in-classroom" : ""} ${!home ? "in-course-workspace" : ""}`}>
      <PageHeader className={home ? "sl-home-account" : "sl-header"}>
        {!home && (
          <a className="sl-home-link" href="#/" aria-label="Edu AI 首页">
            <Brand />
          </a>
        )}
        {room ? (
          <div className="sl-class-title">
            <a href="#/" aria-label="返回首页">
              <Icon name="back" size={17} />
            </a>
            <span>{room.title}</span>
            <small>自主学习课堂</small>
          </div>
        ) : null}
        {!home && (
          <nav className="sl-main-nav" aria-label="主导航">
            <a
              href={room ? `#/classroom/${room.id}` : "#/"}
              className={!studio && !resources ? "active" : ""}
              aria-current={!studio && !resources ? "page" : undefined}
            >
              AI 课堂
            </a>
            <a
              href={workbenchHref}
              className={studio ? "active" : ""}
              aria-current={studio ? "page" : undefined}
            >
              工作台
            </a>
            <a
              href={room ? `#/resources?classroom=${room.id}` : "#/resources"}
              className={resources ? "active" : ""}
              aria-current={resources ? "page" : undefined}
            >
              资源中心
            </a>
          </nav>
        )}
        <div className="sl-account">
          {review && <span className="sl-review-label">前端预览</span>}
          {!home && <span className="sl-preview-label">交互预览</span>}
          <button
            className="sl-avatar"
            aria-label="账户菜单"
            aria-expanded={account}
            onClick={() => setAccount(!account)}
          >
            {username.slice(0, 1).toUpperCase()}
          </button>
          {account && (
            <div className="sl-account-menu">
              <strong>{username}</strong>
              <small>
                {preview ? "开发预览身份 · 未登录" : "已登录"} ·{" "}
                {role === "teacher" ? "教师" : "学习者"}
              </small>
              <button
                onClick={() => {
                  setAccount(false);
                  onLogout();
                }}
              >
                退出{preview ? "预览" : "登录"}
              </button>
              <a href="?legacy=1">打开原版界面</a>
            </div>
          )}
        </div>
      </PageHeader>
      {storageError && (
        <div className="sl-storage-alert" role="alert">
          浏览器存储不可用，本次学习记录可能无法在刷新后保留。
        </div>
      )}
      {home ? (
        <Home
          rooms={state.rooms}
          shared={shared}
          canPublish={role === "teacher"}
          onCreate={(text) => {
            const value = createClassroom(text);
            setState((s) => addClassroom(s, value));
            location.hash = `/classroom/${value.id}`;
          }}
          onOpen={open}
          onPublish={() => setPublish(true)}
        />
      ) : room && !studio && !resources ? (
        <Classroom
          key={room.id}
          room={room}
          workbenchHref={workbenchHref}
          resourceId={query.get("resource") || undefined}
          setState={setState}
          onSelect={(id) => {
            location.hash = `/classroom/${room.id}?resource=${id}`;
          }}
        />
      ) : studio ? (
        workbenchRoom ? <WorkbenchRedirect href={workbenchHref} /> : <Empty title="先选择一堂课" text="工作台会沿用课堂的资料和知识点。" action={<a className="sl-primary" href="#/">返回首页</a>} />
      ) : resources ? (
        <ResourceCenter
          key={query.get("resource") || "library"}
          classroomId={room?.id}
          room={room}
          workbenchHref={workbenchHref}
          workbenchForResource={id => workbenchRoom ? reviewWorkbenchHref(workbenchRoom, id, workbenchSession) : "#/"}
          onAddToLearning={(resource, chapterId) => {
            if (room) setState(s => addToLearning(s, room.id, chapterId, resource));
          }}
          onPin={(id) => setState(s => ({ ...s, resources: s.resources.map(r => r.id === id ? { ...r, pinned: !r.pinned } : r) }))}
          resources={state.resources}
          resourceId={query.get("resource") || undefined}
          onRename={(id, title) =>
            setState((s) => ({
              ...s,
              resources: s.resources.map((r) =>
                r.id === id ? { ...r, title } : r,
              ),
            }))
          }
          onRemove={(id) => {
            setState((s) => ({
              ...s,
              resources: s.resources.filter((r) => r.id !== id),
            }));
            setNotice("已删除本地示例作品，课堂资源未受影响。");
          }}
        />
      ) : (
        <Empty
          title="这段学习旅程还未找到"
          text="课堂可能属于其他账户，或链接来自原版系统。新版目前使用独立的本地演示数据。"
          action={
            <a className="sl-primary" href="#/">
              返回首页
            </a>
          }
        />
      )}
      {publish && role === "teacher" && (
        <PublishDialog
          publisher={username}
          onClose={() => setPublish(false)}
          onPublish={(value) => {
            setShared((s) => [value, ...s]);
            setPublish(false);
            setNotice("已发布到本浏览器的共享课堂；尚未上传服务器。");
          }}
        />
      )}
      {notice && (
        <div className="sl-toast" role="status">
          <Icon name="check" size={18} />
          {notice}
        </div>
      )}
    </div>
  );
}
function WorkbenchRedirect({ href }: { href: string }) {
  useEffect(() => { location.replace(href); }, [href]);
  return <p role="status">正在打开工作台…</p>;
}
const LiveApp = lazy(() => import("../liveLearning/LiveApp"));

function AuthenticatedEntry() {
  const { user, authReady, login } = useAuth();
  if (!authReady)
    return (
      <div className="sl-auth-loading" role="status">
        <Brand />
        <p>正在恢复登录…</p>
      </div>
    );
  if (user) return <Suspense fallback={<p role="status">正在打开学习空间…</p>}><LiveApp key={user.username} /></Suspense>;
  return <LoginPage onLogin={async ({ username, password }) => {
    await login(username.trim(), password);
  }} />;
}
export default function SelfLearningEntry() {
  if (reviewEnabled()) return <LearningApp
    key={reviewRole()}
    username={reviewRole() === "teacher" ? "预览教师" : "探索者"}
    role={reviewRole()}
    preview
    review
    onLogout={() => location.assign(location.pathname)}
  />;
  const preview = import.meta.env.DEV
    ? new URLSearchParams(location.search).get("preview")
    : null;
  if (preview === "student" || preview === "teacher")
    return (
      <LearningApp
        key={preview}
        username={preview === "teacher" ? "预览教师" : "探索者"}
        role={preview}
        preview
        onLogout={() => location.assign(location.pathname)}
      />
    );
  return (
    <AuthProvider>
      <AuthenticatedEntry />
    </AuthProvider>
  );
}
