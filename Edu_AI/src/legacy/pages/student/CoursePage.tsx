import { useParams, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import TeacherStudioPage from './TeacherStudioPage';
import CourseIntroPage from './CourseIntroPage';

// 课程ID到课程名的映射
const courseNameMap: Record<string, string> = {
  'computational-thinking': '计算思维',
  'data-structures': '数据结构',
  'operating-systems': '操作系统',
  'computer-networks': '计算机网络',
  'computer-organization': '计算机组成原理',
  'database-principles': '数据库原理',
};

export default function CoursePage() {
  const { courseId } = useParams<{ courseId: string }>();
  const location = useLocation();
  const { user } = useAuth();
  const courseName = courseId ? courseNameMap[courseId] || courseId : '未知课程';

  // 根据用户角色显示不同的课程界面
  const userRole = user?.role || 'student';
  
  // 根据路径判断显示哪个页面
  if (location.pathname.includes('/intro')) {
    // 显示课程介绍页面
    return <CourseIntroPage />;
  }
  
  // 显示三栏式交互界面
  if (userRole === 'teacher') {
    // 教师端：显示模型交互界面（TeacherStudioPage）
    return <TeacherStudioPage courseId={courseId} courseName={courseName} />;
  } else {
    // 学生端：显示学习界面
    return <TeacherStudioPage courseId={courseId} courseName={courseName} />;
  }
}
