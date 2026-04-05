import React from 'react';
import { Layout, Avatar, Dropdown, Space, Menu } from 'antd';
import {
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const { Header } = Layout;

const SharedHeader: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      logout();
      navigate('/login');
    } else {
      navigate(key);
    }
  };

  const userMenu = (
    <Menu onClick={handleUserMenuClick}>
      <Menu.Item key="/settings" icon={<SettingOutlined />}>
        个人设置
      </Menu.Item>
      <Menu.Divider />
      <Menu.Item key="logout" icon={<LogoutOutlined />}>
        退出登录
      </Menu.Item>
    </Menu>
  );

  return (
    <Header
      style={{
        padding: '0 24px',
        background: '#fff',
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        borderBottom: '1px solid var(--color-border)',
        height: 48,
        lineHeight: '48px',
      }}
    >
      <Dropdown overlay={userMenu} placement="bottomRight" trigger={['click']}>
        <a onClick={(e) => e.preventDefault()}>
          <Space>
            <Avatar icon={<UserOutlined />} size="small" />
            {user?.username || '用户'}
          </Space>
        </a>
      </Dropdown>
    </Header>
  );
};

export default SharedHeader;

