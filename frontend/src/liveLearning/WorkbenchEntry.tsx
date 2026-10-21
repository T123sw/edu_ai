import { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { AuthSessionProvider } from '../stitch/authSession';
import { AppShellProvider, UnifiedCourseShellProvider } from '../stitch/shared';
import { CourseRouteProvider } from '../stitch/course/CourseRouteProvider';
import { AIWorkspacePage } from '../stitch/pages/AIWorkspace';
import { getCourse, getCourseMaterial, backendCourseToSummary } from '../stitch/api/courses';
import { createRevisionIntent, dispatchRevisionIntent } from '../stitch/artifactRevision/intent';
import { Brand } from '../selfLearning/ui';
import { GlobalJobManager } from '../jobs/GlobalJobManager';
import { JobCenterTrigger } from '../jobs/JobCenterDrawer';
import '../stitch/styles.css';
import '../selfLearning/workspace.css';
import '../frontendReview/workbench.css';

document.documentElement.dataset.learningWorkspace = 'true';
function Workspace() {
  const { user, authReady, logout } = useAuth();
  const query = new URLSearchParams(location.hash.split('?')[1] || '');
  const courseId = query.get('course_id') || '';
  const [course, setCourse] = useState<ReturnType<typeof backendCourseToSummary>>();
  const [error, setError] = useState('');
  useEffect(() => {
    if (!user || !courseId) return;
    let active = true;
    void getCourse(courseId).then(c => { if (active) setCourse(backendCourseToSummary(c)); }).catch(e => active && setError(e.message));
    return () => { active = false; };
  }, [user, courseId]);
  useEffect(() => {
    if (!course || !user) return;
    let active = true;
    const params = new URLSearchParams(location.hash.split('?')[1] || '');
    const reference = params.get('reference'), kind = params.get('material_type');
    if (reference && kind) void getCourseMaterial(courseId, kind, reference).then(material => {
      const intent = createRevisionIntent(material, user.username);
      if (active && intent) dispatchRevisionIntent(intent);
    }).catch(e => active && setError(e.message));
    return () => { active = false; };
  }, [course, courseId, user]);
  if (!authReady) return <p>正在恢复登录…</p>;
  if (!user) return <main><p>请先登录，再打开工作台。</p><a href="/">前往登录</a></main>;
  if (error) return <main role="alert"><p>{error}</p><a href="/">返回首页</a></main>;
  if (!course) return <p>正在读取课堂…</p>;
  return <AuthSessionProvider user={{ ...user, role: user.role === 'teacher' || user.role === 'admin' ? user.role : 'student' }} authenticated><AppShellProvider selectedCourse={course} setSelectedCourse={() => undefined} theme="ocean" setTheme={() => undefined} logout={logout}><CourseRouteProvider enabled><UnifiedCourseShellProvider>
    <div className="course-shell review-workbench"><header className="course-shell__workbar">
      <a className="course-shell__brand" href="/" aria-label="返回首页"><Brand /></a><span className="course-shell__course-name">{course.title}</span>
      <nav className="course-navigation course-navigation--desktop" aria-label="主导航">
        <a className="course-navigation__link" href={`/#/classroom/${courseId}`}><strong>AI 课堂</strong></a>
        <a className="course-navigation__link is-active" href={location.hash} aria-current="page"><strong>工作台</strong></a>
        <a className="course-navigation__link" href={`/#/resources?classroom=${courseId}`}><strong>资源中心</strong></a>
      </nav><JobCenterTrigger placement="inline" courseId={courseId} /><a className="course-shell__profile" aria-label="个人中心" href="?account=1#profile" title={user.username}>{user.username[0]}</a>
    </header><AIWorkspacePage /></div>
    <GlobalJobManager enabled showLauncher={false} currentCourseId={courseId} currentCourseTitle={course.title} />
  </UnifiedCourseShellProvider></CourseRouteProvider></AppShellProvider></AuthSessionProvider>;
}
export default function WorkbenchEntry() { return <AuthProvider><Workspace /></AuthProvider>; }
