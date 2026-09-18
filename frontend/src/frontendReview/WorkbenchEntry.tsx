import { useEffect, useState } from "react";
import { PreviewAuthProvider } from "../context/AuthContext";
import { AuthSessionProvider } from "../stitch/authSession";
import { AppShellProvider, UnifiedCourseShellProvider } from "../stitch/shared";
import { CourseRouteProvider } from "../stitch/course/CourseRouteProvider";
import { AIWorkspacePage } from "../stitch/pages/AIWorkspace";
import { useStore } from "../store/teacher/useStore";
import { dispatchRevisionIntent } from "../stitch/artifactRevision/intent";
import { readReviewState, reviewOwner, reviewPageHref, reviewRole } from "../selfLearning/review";
import { Brand } from "../selfLearning/ui";
import { installReviewApi } from "./api";
import "../stitch/styles.css";
import "../selfLearning/workspace.css";
import "./workbench.css";

installReviewApi();
document.documentElement.dataset.learningWorkspace = "true";
useStore.persist.setOptions({ name: `edu-review-workbench-ui:${reviewOwner().replace(/^review:/, "")}` });
useStore.setState(useStore.getInitialState(), true);
void useStore.persist.rehydrate();

// Only an explicit personal-work action carries a reference into the existing composer.
const incoming = new URLSearchParams(location.hash.split("?")[1] || "");
const personalWork = readReviewState().resources.find(r => r.id === incoming.get("reference") && (!r.courseId || r.courseId === incoming.get("course_id")));


export default function WorkbenchReviewEntry() {
  useEffect(() => {
    const timer = setTimeout(() => {
    if (personalWork && incoming.get("course_id")) dispatchRevisionIntent({
  ownerUserId: reviewRole() === "teacher" ? "预览教师" : "探索者",
  reference: { artifact_id: personalWork.id, artifact_type: "report", title: personalWork.title,
    version_id: `v${personalWork.version || 1}`, source_course_id: incoming.get("course_id")! },
});
    }, 0);
    return () => clearTimeout(timer);
  }, []);
  const [state, setState] = useState(readReviewState);
  const [hash, setHash] = useState(location.hash);
  const query = new URLSearchParams(hash.split("?")[1] || "");
  const room = state.rooms.find(r => r.id === query.get("course_id"));
  const role = reviewRole();
  const user = { username: role === "teacher" ? "预览教师" : "探索者", role };
  const [createdId, setCreatedId] = useState<string | null>(null);
  useEffect(() => {
    const refresh = (event: Event) => { setState(readReviewState()); if ((event as CustomEvent<string>).detail) setCreatedId((event as CustomEvent<string>).detail); };
    const route = () => setHash(location.hash);
    window.addEventListener("review-materials-changed", refresh);
    window.addEventListener("hashchange", route);
    return () => { window.removeEventListener("review-materials-changed", refresh); window.removeEventListener("hashchange", route); };
  }, []);
  if (!room) return <main className="review-missing"><h1>请先选择一间课堂</h1><a href={reviewPageHref("home")}>返回首页</a></main>;
  const course = { id: room.id, title: room.title, summary: room.goal, module: "", uppercaseTitle: room.title, instructor: "", progress: 0, image: "", accent: "" };
  return <PreviewAuthProvider user={user}><AuthSessionProvider user={user} authenticated><AppShellProvider selectedCourse={course} setSelectedCourse={() => undefined} theme="ocean" setTheme={() => undefined} logout={() => location.assign(reviewPageHref("home"))}><CourseRouteProvider enabled><UnifiedCourseShellProvider>
    <div className="course-shell review-workbench">
      <header className="course-shell__workbar">
        <a className="course-shell__brand" aria-label="返回首页" href={reviewPageHref("home")}><Brand /></a>
        <span className="course-shell__course-name">{room.title}</span>
        <nav className="course-navigation course-navigation--desktop" aria-label="主导航">
          <a className="course-navigation__link" href={reviewPageHref("classroom", room.id)}><strong>AI 课堂</strong></a>
          <a className="course-navigation__link is-active" href={`#${role === "student" ? "student-ai" : "ai"}?${query}`} aria-current="page"><strong>工作台</strong></a>
          <a className="course-navigation__link" href={reviewPageHref("resources", room.id)}><strong>资源中心</strong></a>
        </nav>
        <div className="course-shell__actions"><span className="review-label">前端预览</span><a className="course-shell__profile" href={reviewPageHref("home")} aria-label="返回学习空间">{user.username[0]}</a></div>
      </header>
      <AIWorkspacePage />
      {createdId && <div className="review-completed" role="status"><span>示例资源已准备好</span><a href={reviewPageHref("resources", room.id, createdId)}>到资源中心查看 →</a><button aria-label="关闭完成提示" onClick={() => setCreatedId(null)}>×</button></div>}
    </div>
  </UnifiedCourseShellProvider></CourseRouteProvider></AppShellProvider></AuthSessionProvider></PreviewAuthProvider>;
}
