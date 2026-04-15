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
import SharedHeader from './SharedHeader'; // 引入共享的 Header
import './GlobalLayout.css'; // 复用一级导航的样式

const { Sider, Content } = Layout;

const CourseContextLayout: React.FC = () => {
  const { courseId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { courses, currentCourse, setCurrentCourse, loadCoursesFromBackend } = useCourseStore();
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
    ensureCourse();
  }, [courseId, courses?.length, loadCoursesFromBackend, setCurrentCourse]);

  const teacherMenuItems = [
    { key: `${basePath}/intro`, icon: <InfoCircleOutlined />, label: '课程介绍' },
    { key: `${basePath}/studio`, icon: <RobotOutlined />, label: '问答助手' },
    { key: `${basePath}/knowledge-graph`, icon: <ApartmentOutlined />, label: '知识图谱' },
    { key: `${basePath}/data-pipeline`, icon: <CloudDownloadOutlined />, label: '数据采集' },
    { key: `${basePath}/resources`, icon: <FolderOutlined />, label: '教学资源' },
    { key: `${basePath}/analytics`, icon: <BarChartOutlined />, label: '学习情况' },
  ];

  const studentMenuItems = [
    { key: `${basePath}/intro`, icon: <InfoCircleOutlined />, label: '课程介绍' },
    { key: `${basePath}/studio`, icon: <LaptopOutlined />, label: '开始学习' },
    { key: `${basePath}/materials`, icon: <ReadOutlined />, label: '课程资料' },
  ];

  const menuItems = isTeacher ? teacherMenuItems : studentMenuItems;

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const selectedKey = location.pathname;

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider width={200} theme="dark">
        <div className="logo" style={{ height: 'auto', padding: '16px', textAlign: 'center' }}>
          <Tooltip title="返回课程列表">
            <Button
              ghost
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/welcome')}
              style={{ width: '100%' }}
            >
              退出课程
            </Button>
          </Tooltip>
        </div>

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>

      <Layout>
        <SharedHeader />
        <Content style={{ height: 'calc(100vh - 48px)', overflow: 'hidden' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default CourseContextLayout;
