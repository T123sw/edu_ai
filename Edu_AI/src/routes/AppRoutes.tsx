import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import LoginPage from '../pages/LoginPage';
import WelcomePage from '../pages/WelcomePage';
import DocsPage from '../pages/DocsPage';
import TeacherCourseManagementPage from '../pages/teacher/CourseManagementPage';
import TeacherCourseDetailPage from '../pages/teacher/CourseDetailPage';
import TeacherToolsPage from '../pages/teacher/TeacherToolsPage';
import StudentToolsPage from '../pages/student/TeacherToolsPage';
import StudentCoursePage from '../pages/student/CoursePage';
import StudentCourseManagementPage from '../pages/student/CourseManagementPage';
import StudentCourseDetailPage from '../pages/student/CourseDetailPage';
import StudentCourseMaterialsPage from '../pages/student/CourseMaterialsPage';
import StudentLearningRecordPage from '../pages/student/LearningRecordPage';
import DataPipelinePage from '../pages/DataPipelinePage';
import UserCenterPage from '../pages/UserCenterPage';
import KnowledgeBasePage from '../pages/KnowledgeBasePage';
import DeepSearchPage from '../pages/DeepSearchPage';
import ProtectedRoute from '../components/ProtectedRoute';
import GlobalLayout from '../layout/GlobalLayout';
import CourseContextLayout from '../layout/CourseContextLayout';

// Teacher - Refactored Pages
import AiStudioPage from '../pages/teacher/AiStudioPage';
import AiCourseIntroPage from '../pages/teacher/AiCourseIntroPage';
import AiCourseResourcesPage from '../pages/teacher/AiCourseResourcesPage';
import KnowledgeGraphPage from '../pages/teacher/KnowledgeGraphPage'; // Import the new page

// Student - Refactored Pages
import AiStudentStudioPage from '../pages/student/AiStudentStudioPage';
import AiStudentCourseIntroPage from '../pages/student/AiStudentCourseIntroPage';

function RootRedirect() {
  const { token } = useAuth();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <Navigate to="/welcome" replace />;
}

function RedirectToCourseIntro() {
  const { courseId } = useParams();
  return <Navigate to={`/course/${courseId}/intro`} replace />;
}

function RedirectToCourseStudio() {
  const { courseId } = useParams();
  return <Navigate to={`/course/${courseId}/studio`} replace />;
}

export default function AppRoutes() {
  const { user } = useAuth();
  const isTeacher = user?.role === 'teacher';

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RootRedirect />} />

      <Route
        element={(
          <ProtectedRoute>
            <GlobalLayout />
          </ProtectedRoute>
        )}
      >
        {/* --- 一级导航 --- */}
        <Route path="/welcome" element={<WelcomePage />} />
        <Route path="/settings" element={<UserCenterPage />} />

        {/* 教师专属一级导航 */}
        {isTeacher && (
          <>
            <Route path="/course-management" element={<TeacherCourseManagementPage />} />
            <Route path="/course-management/:courseId" element={<TeacherCourseDetailPage />} />
            <Route path="/global-resources" element={<KnowledgeBasePage />} />
            <Route path="/deep-search" element={<DeepSearchPage />} />
          </>
        )}

        {/* 学生专属一级导航 */}
        {!isTeacher && (
          <>
            <Route path="/learning-record" element={<StudentLearningRecordPage />} />
          </>
        )}

        {/* --- 二级导航：课程上下文 --- */}
        <Route path="/course/:courseId" element={<CourseContextLayout />}>
          {isTeacher ? (
            <>
              <Route path="intro" element={<AiCourseIntroPage />} />
              <Route path="studio" element={<AiStudioPage />} />
              <Route path="knowledge-graph" element={<KnowledgeGraphPage />} />
              <Route path="data-pipeline" element={<DataPipelinePage />} />
              <Route path="resources" element={<AiCourseResourcesPage />} />
              <Route path="analytics" element={<div>学习情况页面（待实现）</div>} />
              <Route index element={<Navigate to="studio" replace />} />
            </>
          ) : (
            <>
              <Route path="intro" element={<AiStudentCourseIntroPage />} />
              <Route path="studio" element={<AiStudentStudioPage />} />
              <Route path="materials" element={<StudentCourseMaterialsPage />} />
              <Route index element={<Navigate to="studio" replace />} />
            </>
          )}
        </Route>

        {/* --- 旧路由兼容重定向 --- */}
        <Route path="/teacher/course/:courseId/intro" element={<RedirectToCourseIntro />} />
        <Route path="/teacher/course/:courseId/studio" element={<RedirectToCourseStudio />} />
        <Route path="/student/course/:courseId/intro" element={<RedirectToCourseIntro />} />
        <Route path="/student/course/:courseId/studio" element={<RedirectToCourseStudio />} />

        {/* --- 暂时保留的独立页面 --- */}
        <Route path="/docs" element={<DocsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
