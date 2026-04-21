import { Button, Form, Input, message } from 'antd';
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  KeyOutlined,
  LogoutOutlined,
  ReloadOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './UserCenterPage.css';

interface UserProfile {
  username: string;
  email: string;
  phone: string;
  nickname: string;
  department: string;
  role: string;
  bio: string;
  avatar?: string;
}

const PROFILE_STORAGE_KEY = 'user-profile';

const defaultProfile = (username = ''): UserProfile => ({
  username,
  nickname: username || '用户',
  email: 'lin.zhixia@edu-ai.local',
  phone: '+86 138 0000 1024',
  department: '课程研发中心',
  role: '课程主理人 / 教学设计师',
  bio: '负责课程结构设计、知识图谱维护与教师问答工作流配置。当前个人主页为新版展示页，用于展示基础账号信息、头像入口与密码设置入口。',
});

const accountFields = [
  ['用户名', 'username'],
  ['邮箱', 'email'],
  ['手机号', 'phone'],
  ['所属部门', 'department'],
] as const;

const quickLinks = [
  { title: '我的课程', subtitle: '跳转查看课程与工作区', href: '/welcome', icon: 'grid' },
  { title: '问答助手', subtitle: '进入教师 AI 工作台', href: '/course-management', icon: 'chat' },
  { title: '知识库', subtitle: '维护课程资料与知识源', href: '/global-resources', icon: 'book' },
];

export default function UserCenterPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const avatarInputRef = useRef<HTMLInputElement | null>(null);
  const [passwordForm] = Form.useForm();
  const [profile, setProfile] = useState<UserProfile>(() => defaultProfile(user?.username || ''));
  const [showPasswordPanel, setShowPasswordPanel] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    const fallback = defaultProfile(user?.username || '');
    const raw = localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) {
      setProfile(fallback);
      return;
    }

    try {
      setProfile({ ...fallback, ...(JSON.parse(raw) as Partial<UserProfile>) });
    } catch {
      setProfile(fallback);
    }
  }, [user?.username]);

  const initials = useMemo(() => {
    const source = profile.nickname || profile.username || 'U';
    return source.slice(0, 2).toUpperCase();
  }, [profile.nickname, profile.username]);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const persistProfile = (nextProfile: UserProfile) => {
    setProfile(nextProfile);
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(nextProfile));
  };

  const handleAvatarChange = (fileList: FileList | null) => {
    const file = fileList?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      message.error('请选择图片文件作为头像');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      persistProfile({ ...profile, avatar: String(reader.result || '') });
      message.success('头像已更新');
    };
    reader.onerror = () => message.error('头像读取失败，请重试');
    reader.readAsDataURL(file);
  };

  const handleResetAvatar = () => {
    const { avatar, ...rest } = profile;
    persistProfile(rest);
    message.success('已恢复默认头像');
  };

  const handleResetPassword = async (values: {
    currentPassword: string;
    newPassword: string;
    confirmPassword: string;
  }) => {
    if (values.newPassword !== values.confirmPassword) {
      message.error('两次输入的新密码不一致');
      return;
    }
    if (values.newPassword.length < 6) {
      message.error('新密码至少需要 6 位');
      return;
    }

    setSavingPassword(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 500));
      passwordForm.resetFields();
      setShowPasswordPanel(false);
      message.success('密码已重置');
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <div className="profile-replace-page">
      <div className="profile-topbar">
        <button type="button" className="profile-back-button" onClick={() => navigate('/welcome')}>
          <ArrowLeftOutlined />
          返回首页
        </button>
        <span className="profile-page-pill">Personal Home</span>
      </div>

      <section className="profile-hero-card">
        <div className="profile-hero-copy">
          <span className="profile-eyebrow">Account Center</span>
          <h1>{profile.nickname || profile.username}</h1>
          <strong>{profile.role}</strong>
          <p>{profile.bio}</p>
          <div className="profile-hero-actions">
            <Button type="primary" icon={<ReloadOutlined />} onClick={() => setShowPasswordPanel((value) => !value)}>
              重置密码
            </Button>
            <Button icon={<UploadOutlined />} onClick={() => avatarInputRef.current?.click()}>
              更换头像
            </Button>
            <Button icon={<LogoutOutlined />} onClick={handleLogout}>
              退出登录
            </Button>
          </div>
        </div>

        <div className="profile-avatar-stage">
          <div className="profile-avatar-box">
            {profile.avatar ? <img src={profile.avatar} alt="当前头像" /> : <span>{initials}</span>}
          </div>
          <button type="button" className="profile-avatar-label" onClick={handleResetAvatar}>
            当前头像
          </button>
          <input
            ref={avatarInputRef}
            type="file"
            accept="image/*"
            className="profile-hidden-input"
            onChange={(event) => handleAvatarChange(event.target.files)}
          />
        </div>
      </section>

      <main className="profile-content-grid">
        <section className="profile-panel profile-details-panel">
          <div className="profile-panel-heading">
            <span className="profile-panel-icon">◎</span>
            <div>
              <small>Profile Details</small>
              <h2>个人资料</h2>
            </div>
          </div>
          <div className="profile-fields-grid">
            {accountFields.map(([label, key]) => (
              <div key={key} className="profile-field-card">
                <span>{label}</span>
                <strong>{profile[key]}</strong>
              </div>
            ))}
          </div>
        </section>

        <aside className="profile-side-stack">
          <section className="profile-panel">
            <div className="profile-panel-heading">
              <span className="profile-panel-icon">⚙</span>
              <div>
                <small>Security</small>
                <h2>账号安全</h2>
              </div>
            </div>
            <div className="profile-security-list">
              <div>
                <strong>登录密码</strong>
                <span>上次更新于 2025-02-18</span>
              </div>
              <div>
                <strong>账号状态</strong>
                <span>正常，可访问全部教师页面</span>
              </div>
              <div>
                <strong>头像设置</strong>
                <span>{profile.avatar ? '已使用自定义头像' : '当前使用静态默认头像'}</span>
              </div>
            </div>

            {showPasswordPanel ? (
              <Form form={passwordForm} layout="vertical" className="profile-password-form" onFinish={handleResetPassword}>
                <Form.Item name="currentPassword" label="当前密码" rules={[{ required: true, message: '请输入当前密码' }]}>
                  <Input.Password prefix={<KeyOutlined />} placeholder="输入当前密码" />
                </Form.Item>
                <Form.Item name="newPassword" label="新密码" rules={[{ required: true, message: '请输入新密码' }]}>
                  <Input.Password prefix={<KeyOutlined />} placeholder="至少 6 位" />
                </Form.Item>
                <Form.Item name="confirmPassword" label="确认新密码" rules={[{ required: true, message: '请再次输入新密码' }]}>
                  <Input.Password prefix={<KeyOutlined />} placeholder="再次输入新密码" />
                </Form.Item>
                <div className="profile-password-actions">
                  <Button onClick={() => setShowPasswordPanel(false)}>取消</Button>
                  <Button type="primary" htmlType="submit" loading={savingPassword}>
                    保存密码
                  </Button>
                </div>
              </Form>
            ) : null}
          </section>

          <section className="profile-panel">
            <div className="profile-panel-heading">
              <span className="profile-panel-icon">▦</span>
              <div>
                <small>Quick Access</small>
                <h2>快捷入口</h2>
              </div>
            </div>
            <div className="profile-quick-list">
              {quickLinks.map((item) => (
                <button key={item.href} type="button" onClick={() => navigate(item.href)}>
                  <span className={`profile-quick-icon is-${item.icon}`} />
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.subtitle}</small>
                  </span>
                  <ArrowRightOutlined />
                </button>
              ))}
            </div>
          </section>
        </aside>
      </main>
    </div>
  );
}
