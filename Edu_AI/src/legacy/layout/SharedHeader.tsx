import React from 'react';
import { Layout, Avatar, Dropdown, Space } from 'antd';
import type { MenuProps } from 'antd';
import { SettingOutlined, UserOutlined, LogoutOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const { Header } = Layout;

const SharedHeader: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleUserMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key === 'logout') {
      logout();
      navigate('/login');
      return;
    }
    navigate(String(key));
  };

  const userMenuItems: MenuProps['items'] = [
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '个人中心',
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
    },
  ];

  return (
    <Header className="global-shared-header">
      <Dropdown menu={{ items: userMenuItems, onClick: handleUserMenuClick }} placement="bottomRight" trigger={['click']}>
        <a className="global-user-trigger" onClick={(event) => event.preventDefault()}>
          <Space size={10}>
            <Avatar icon={<UserOutlined />} size="small" />
            <span>{user?.username || '用户'}</span>
          </Space>
        </a>
      </Dropdown>
    </Header>
  );
};

export default SharedHeader;
