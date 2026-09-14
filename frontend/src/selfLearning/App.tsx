import { useEffect, useState } from "react";
import { AuthProvider, useAuth } from "../context/AuthContext";
import { Home } from "./Home";
import { Classroom } from "./Classroom";
import { Studio } from "./Studio";
import { Resources } from "./Resources";
import { PublishDialog } from "./PublishDialog";
import {
  addClassroom,
  createClassroom,
  startShared,
  type Classroom as Room,
} from "./model";
import { useLearningStore } from "./store";
import { Brand, Empty, Icon } from "./ui";
import "./styles.css";

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
  onLogout,
}: {
  username: string;
  role?: string;
  preview?: boolean;
  onLogout: () => void;
}) {
  // Separate showcase storage preserves any progress in the original preview.
  const showcase =
    !!preview && new URLSearchParams(location.search).get("demo") === "1";
  const { state, setState, shared, setShared, storageError } = useLearningStore(
    `${preview ? "preview" : "user"}:${username}${showcase ? ":showcase" : ""}`,
    showcase,
  );
  const { path, query } = useRoute();
  const [publish, setPublish] = useState(false);
  const [account, setAccount] = useState(false);
  const [notice, setNotice] = useState("");
  const roomId = path.startsWith("/classroom/")
    ? path.slice("/classroom/".length)
    : "";
  const room = state.rooms.find((r) => r.id === roomId);
  const home = path === "/";
  const studio = path === "/studio";
  const resources = path === "/resources";
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(timer);
  }, [notice]);
  function open(value: Room, isShared?: boolean) {
    if (isShared) {
      const [next, copy] = startShared(state, value);
      setState(next);
      location.hash = `/classroom/${copy.id}`;
    } else location.hash = `/classroom/${value.id}`;
  }
  return (
    <div className={`sl-app ${room ? "in-classroom" : ""}`}>
      <header className="sl-header">
        <a className="sl-home-link" href="#/" aria-label="Edu AI 首页">
          <Brand />
        </a>
        {room ? (
          <div className="sl-class-title">
            <a href="#/" aria-label="返回首页">
              <Icon name="back" size={17} />
            </a>
            <span>{room.title}</span>
            <small>自主学习课堂</small>
          </div>
        ) : (
          <nav className="sl-main-nav" aria-label="主导航">
            <a
              href="#/"
              className={home ? "active" : ""}
              aria-current={home ? "page" : undefined}
            >
              课堂
            </a>
            <a
              href="#/studio"
              className={studio ? "active" : ""}
              aria-current={studio ? "page" : undefined}
            >
              工作台
            </a>
            <a
              href="#/resources"
              className={resources ? "active" : ""}
              aria-current={resources ? "page" : undefined}
            >
              资源中心
            </a>
          </nav>
        )}
        <div className="sl-account">
          <span className="sl-preview-label">交互预览</span>
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
      </header>
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
      ) : room ? (
        <Classroom
          key={room.id}
          room={room}
          resourceId={query.get("resource") || undefined}
          setState={setState}
          onSelect={(id) => {
            location.hash = `/classroom/${room.id}?resource=${id}`;
          }}
        />
      ) : studio ? (
        <Studio
          state={state}
          setState={setState}
          classroomId={query.get("classroom") || undefined}
        />
      ) : resources ? (
        <Resources
          key={query.get("resource") || "library"}
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
function AuthenticatedEntry() {
  const { user, authReady, login, logout } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!authReady)
    return (
      <div className="sl-auth-loading" role="status">
        <Brand />
        <p>正在恢复登录…</p>
      </div>
    );
  if (user)
    return (
      <LearningApp
        key={user.username}
        username={user.username}
        role={user.role}
        onLogout={logout}
      />
    );
  return (
    <main className="sl-login">
      <a href="#/">
        <Brand />
      </a>
      <div className="sl-login-card">
        <span className="sl-eyebrow">YOUR NEXT CHAPTER STARTS HERE</span>
        <h1>欢迎回来，继续探索。</h1>
        <p>一份好奇，一个目标，一堂属于你的课。</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (busy) return;
            setBusy(true);
            setError("");
            try {
              await login(username.trim(), password);
            } catch (cause) {
              setError(
                cause instanceof Error ? cause.message : "登录失败，请稍后重试",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="sl-field">
            账号
            <input
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="输入你的账号"
            />
          </label>
          <label className="sl-field">
            密码
            <input
              autoComplete="current-password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="输入密码"
            />
          </label>
          {error && (
            <p className="sl-error" role="alert">
              {error}
            </p>
          )}
          <button
            className="sl-primary"
            disabled={busy || !username.trim() || !password}
          >
            {busy ? "正在登录…" : "进入学习空间"}
            <Icon name="arrow" size={17} />
          </button>
        </form>
        <p className="sl-login-caption">
          沿用现有账号登录 · 新版学习流程为本地交互预览
        </p>
        {import.meta.env.DEV && (
          <div className="sl-dev-links">
            <span>仅开发环境</span>
            <a href="?preview=student">预览学生界面</a>
            <a href="?preview=teacher">预览教师界面</a>
          </div>
        )}
        <a className="sl-text-button" href="?legacy=1">
          返回原版界面
        </a>
      </div>
    </main>
  );
}
export default function SelfLearningEntry() {
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
