import React, { useState } from 'react';
import { Layout, Menu } from 'antd';
import { HomeOutlined, AppstoreOutlined, DatabaseOutlined, ReadOutlined, SearchOutlined } from '@ant-design/icons';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import SharedHeader from './SharedHeader';
import './GlobalLayout.css';

const { Sider, Content } = Layout;

const GlobalLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isTeacher = user?.role === 'teacher';

  const teacherMenuItems = [
    { key: '/welcome', icon: <HomeOutlined />, label: '课程首页' },
    { key: '/course-management', icon: <AppstoreOutlined />, label: '课程管理' },
    { key: '/global-resources', icon: <DatabaseOutlined />, label: '公共资源' },
    { key: '/deep-search', icon: <SearchOutlined />, label: '深度检索' },
  ];

  const studentMenuItems = [
    { key: '/welcome', icon: <HomeOutlined />, label: '我的课程' },
    { key: '/learning-record', icon: <ReadOutlined />, label: '学习记录' },
  ];

  const menuItems = isTeacher ? teacherMenuItems : studentMenuItems;

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const selectedKey = '/' + location.pathname.split('/')[1];
  const isInCourse = location.pathname.startsWith('/course/');

  if (isInCourse) {
    return <Outlet />;
  }

  return (
    <Layout className="global-layout" style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} width={232} theme="dark">
        <div className="logo">
          <span>{collapsed ? 'AI' : 'Edu-AI'}</span>
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[selectedKey]} items={menuItems} onClick={handleMenuClick} />
      </Sider>
      <Layout className="global-layout-main">
        <SharedHeader />
        <Content className="global-layout-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default GlobalLayout;
