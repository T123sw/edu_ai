import { 
  Card, 
  Row, 
  Col, 
  Typography, 
  Avatar, 
  Form, 
  Input, 
  Button, 
  Divider, 
  Space, 
  message, 
  Tabs, 
  Statistic,
  Descriptions,
  Tag
} from 'antd';
import {
  UserOutlined,
  LockOutlined,
  SafetyOutlined,
  EditOutlined,
  SaveOutlined,
  BarChartOutlined
} from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import './UserCenterPage.css';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

interface UserProfile {
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  bio?: string;
}

interface UserStats {
  totalChats: number;
  totalMessages: number;
  totalDocs: number;
  lastLogin: string;
}

export default function UserCenterPage() {
  const { user, logout } = useAuth();
  const [profileForm] = Form.useForm();
  const [passwordForm] = Form.useForm();
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);

  // 模拟用户数据
  const [userProfile, setUserProfile] = useState<UserProfile>({
    username: user?.username || '',
    email: 'user@example.com',
    phone: '138****8888',
    nickname: user?.username || '',
    bio: '这个人很懒，什么都没有留下~'
  });

  const [userStats, setUserStats] = useState<UserStats>({
    totalChats: 42,
    totalMessages: 156,
    totalDocs: 8,
    lastLogin: new Date().toLocaleString('zh-CN')
  });

  useEffect(() => {
    // 从 localStorage 加载用户资料
    const savedProfile = localStorage.getItem('user-profile');
    if (savedProfile) {
      try {
        const profile = JSON.parse(savedProfile);
        setUserProfile(profile);
        profileForm.setFieldsValue(profile);
      } catch (e) {
        console.error('加载资料失败:', e);
      }
    } else {
      profileForm.setFieldsValue(userProfile);
    }
  }, [user, profileForm]);

  // 保存个人信息
  const handleSaveProfile = async (values: UserProfile) => {
    try {
      setLoading(true);
      // 模拟保存延迟
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const updatedProfile = { ...userProfile, ...values };
      setUserProfile(updatedProfile);
      localStorage.setItem('user-profile', JSON.stringify(updatedProfile));
      setEditing(false);
      message.success('个人信息保存成功');
    } catch (e) {
      message.error('保存失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 修改密码
  const handleChangePassword = async (values: { oldPassword: string; newPassword: string; confirmPassword: string }) => {
    try {
      if (values.newPassword !== values.confirmPassword) {
        message.error('两次输入的密码不一致');
        return;
      }

      if (values.newPassword.length < 6) {
        message.error('密码长度至少为6位');
        return;
      }

      setLoading(true);
      // 模拟修改密码延迟
      await new Promise(resolve => setTimeout(resolve, 500));
      
      passwordForm.resetFields();
      message.success('密码修改成功');
    } catch (e) {
      message.error('密码修改失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="user-center-page">
      <Row gutter={[24, 24]}>
        {/* 左侧：用户信息卡片 */}
        <Col xs={24} lg={8}>
          <Card className="profile-card">
            <div className="profile-header">
              <Avatar 
                size={80} 
                style={{ 
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  fontSize: 32
                }}
              >
                {userProfile.nickname?.[0]?.toUpperCase() || userProfile.username?.[0]?.toUpperCase() || 'U'}
              </Avatar>
              <Title level={4} className="profile-name">
                {userProfile.nickname || userProfile.username}
              </Title>
              <Text type="secondary" className="profile-username">
                @{userProfile.username}
              </Text>
              {userProfile.bio && (
                <Text type="secondary" className="profile-bio">
                  {userProfile.bio}
                </Text>
              )}
            </div>
            <Divider />
            <Descriptions column={1} size="small">
              <Descriptions.Item label="邮箱">
                {userProfile.email || '未设置'}
              </Descriptions.Item>
              <Descriptions.Item label="手机">
                {userProfile.phone || '未设置'}
              </Descriptions.Item>
              <Descriptions.Item label="注册时间">
                2024-01-01
              </Descriptions.Item>
              <Descriptions.Item label="账户状态">
                <Tag color="success">正常</Tag>
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 使用统计 */}
          <Card className="stats-card" style={{ marginTop: 24 }}>
            <Title level={5}>
              <BarChartOutlined style={{ marginRight: 8 }} />
              使用统计
            </Title>
            <Row gutter={16} style={{ marginTop: 16 }}>
              <Col span={12}>
                <Statistic 
                  title="对话数" 
                  value={userStats.totalChats} 
                  valueStyle={{ fontSize: 20 }}
                />
              </Col>
              <Col span={12}>
                <Statistic 
                  title="消息数" 
                  value={userStats.totalMessages} 
                  valueStyle={{ fontSize: 20 }}
                />
              </Col>
              <Col span={12} style={{ marginTop: 16 }}>
                <Statistic 
                  title="文档数" 
                  value={userStats.totalDocs} 
                  valueStyle={{ fontSize: 20 }}
                />
              </Col>
              <Col span={12} style={{ marginTop: 16 }}>
                <div style={{ textAlign: 'center' }}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>最后登录</Text>
                  <Text style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                    {userStats.lastLogin.split(' ')[0]}
                  </Text>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 右侧：设置内容 */}
        <Col xs={24} lg={16}>
          <Card>
            <Tabs defaultActiveKey="profile" size="large">
              {/* 个人信息 */}
              <TabPane 
                tab={
                  <span>
                    <UserOutlined />
                    个人信息
                  </span>
                } 
                key="profile"
              >
                <Form
                  form={profileForm}
                  layout="vertical"
                  onFinish={handleSaveProfile}
                  disabled={!editing}
                >
                  <Form.Item name="nickname" label="昵称">
                    <Input prefix={<UserOutlined />} placeholder="请输入昵称" />
                  </Form.Item>
                  <Form.Item name="email" label="邮箱">
                    <Input type="email" placeholder="请输入邮箱地址" />
                  </Form.Item>
                  <Form.Item name="phone" label="手机号">
                    <Input placeholder="请输入手机号" />
                  </Form.Item>
                  <Form.Item name="bio" label="个人简介">
                    <Input.TextArea 
                      rows={4} 
                      placeholder="介绍一下自己吧~" 
                      maxLength={200}
                      showCount
                    />
                  </Form.Item>
                  <Form.Item>
                    <Space>
                      {editing ? (
                        <>
                          <Button 
                            type="primary" 
                            htmlType="submit" 
                            icon={<SaveOutlined />}
                            loading={loading}
                          >
                            保存
                          </Button>
                          <Button onClick={() => {
                            setEditing(false);
                            profileForm.resetFields();
                            profileForm.setFieldsValue(userProfile);
                          }}>
                            取消
                          </Button>
                        </>
                      ) : (
                        <Button 
                          type="primary" 
                          icon={<EditOutlined />}
                          onClick={() => setEditing(true)}
                        >
                          编辑
                        </Button>
                      )}
                    </Space>
                  </Form.Item>
                </Form>
              </TabPane>

              {/* 账户安全 */}
              <TabPane 
                tab={
                  <span>
                    <SafetyOutlined />
                    账户安全
                  </span>
                } 
                key="security"
              >
                <Form
                  form={passwordForm}
                  layout="vertical"
                  onFinish={handleChangePassword}
                >
                  <Form.Item 
                    name="oldPassword" 
                    label="当前密码"
                    rules={[{ required: true, message: '请输入当前密码' }]}
                  >
                    <Input.Password 
                      prefix={<LockOutlined />} 
                      placeholder="请输入当前密码" 
                    />
                  </Form.Item>
                  <Form.Item 
                    name="newPassword" 
                    label="新密码"
                    rules={[
                      { required: true, message: '请输入新密码' },
                      { min: 6, message: '密码长度至少为6位' }
                    ]}
                  >
                    <Input.Password 
                      prefix={<LockOutlined />} 
                      placeholder="请输入新密码（至少6位）" 
                    />
                  </Form.Item>
                  <Form.Item 
                    name="confirmPassword" 
                    label="确认新密码"
                    dependencies={['newPassword']}
                    rules={[
                      { required: true, message: '请确认新密码' },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue('newPassword') === value) {
                            return Promise.resolve();
                          }
                          return Promise.reject(new Error('两次输入的密码不一致'));
                        },
                      }),
                    ]}
                  >
                    <Input.Password 
                      prefix={<LockOutlined />} 
                      placeholder="请再次输入新密码" 
                    />
                  </Form.Item>
                  <Form.Item>
                    <Button 
                      type="primary" 
                      htmlType="submit" 
                      loading={loading}
                    >
                      修改密码
                    </Button>
                  </Form.Item>
                </Form>
              </TabPane>
            </Tabs>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

