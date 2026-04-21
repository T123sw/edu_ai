import React from 'react';
import { Layout, Menu, Button, Tooltip } from 'antd';
import {
  InfoCircleOutlined,
  RobotOutlined,
  ApartmentOutlined,
  CloudDownloadOutlined,
  FolderOutlined,
  BarChartOutlined,
  ArrowLeftOutlined,
  ReadOutlined,
  LaptopOutlined,
} from '@ant-design/icons';
import { Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useCourseStore } from '../store/course/useCourseStore';
import { useAuth } from '../context/AuthContext';
import SharedHeader from './SharedHeader';
import './GlobalLayout.css';

const { Sider, Content } = Layout;

const CourseContextLayout: React.FC = () => {
  const { courseId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { courses, setCurrentCourse, loadCoursesFromBackend } = useCourseStore();
  const isTeacher = user?.role === 'teacher';

  const basePath = `/course/${courseId}`;

  React.useEffect(() => {
    const ensureCourse = async () => {
      if (!courseId) return;
      if (!courses || courses.length === 0) {
        await loadCoursesFromBackend();
      }
      setCurrentCourse(courseId);
    };
    void ensureCourse();
  }, [courseId, courses?.length, loadCoursesFromBackend, setCurrentCourse]);

  const teacherMenuItems = [
    { key: `${basePath}/intro`, icon: <InfoCircleOutlined />, label: '课程简介' },
    { key: `${basePath}/studio`, icon: <RobotOutlined />, label: '问答工作台' },
    { key: `${basePath}/knowledge-graph`, icon: <ApartmentOutlined />, label: '知识图谱' },
    { key: `${basePath}/data-pipeline`, icon: <CloudDownloadOutlined />, label: '数据管线' },
    { key: `${basePath}/resources`, icon: <FolderOutlined />, label: '课程资源' },
    { key: `${basePath}/analytics`, icon: <BarChartOutlined />, label: '数据分析' },
  ];

  const studentMenuItems = [
    { key: `${basePath}/intro`, icon: <InfoCircleOutlined />, label: '课程简介' },
    { key: `${basePath}/studio`, icon: <LaptopOutlined />, label: '学习工作台' },
    { key: `${basePath}/materials`, icon: <ReadOutlined />, label: '课程资料' },
  ];

  const menuItems = isTeacher ? teacherMenuItems : studentMenuItems;

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  return (
    <Layout className="global-layout global-layout--course" style={{ minHeight: '100vh' }}>
      <Sider width={232} theme="dark">
        <div className="logo course-layout-back">
          <Tooltip title="返回课程首页">
            <Button ghost icon={<ArrowLeftOutlined />} onClick={() => navigate('/welcome')} style={{ width: '100%' }}>
              返回课程首页
            </Button>
          </Tooltip>
        </div>

        <Menu theme="dark" mode="inline" selectedKeys={[location.pathname]} items={menuItems} onClick={handleMenuClick} />
      </Sider>

      <Layout className="global-layout-main">
        <SharedHeader />
        <Content className="global-layout-content global-layout-content--course">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default CourseContextLayout;
