import { Button, Card, Checkbox, Form, Input, Typography, message } from 'antd';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

const { Title } = Typography;

const REMEMBER_USER_KEY = 'edu-ai-remember-user';
const REMEMBERED_USERNAME_KEY = 'edu-ai-remembered-username';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login: loginAuth, token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    if (token) {
      const state = location.state as { from?: { pathname?: string } } | null;
      if (state?.from?.pathname) {
        navigate(state.from.pathname, { replace: true });
      } else {
        navigate('/welcome', { replace: true });
      }
    }
  }, [token, navigate, location]);

  useEffect(() => {
    const remembered = localStorage.getItem(REMEMBER_USER_KEY) === 'true';
    const rememberedUsername = localStorage.getItem(REMEMBERED_USERNAME_KEY);

    if (remembered && rememberedUsername) {
      form.setFieldsValue({
        username: rememberedUsername,
        rememberMe: true,
      });
    }
  }, [form]);

  const onFinish = async (values: { username: string; password: string; rememberMe?: boolean }) => {
    try {
      setLoading(true);
      await loginAuth(values.username, values.password);

      if (values.rememberMe) {
        localStorage.setItem(REMEMBER_USER_KEY, 'true');
        localStorage.setItem(REMEMBERED_USERNAME_KEY, values.username);
      } else {
        localStorage.removeItem(REMEMBER_USER_KEY);
        localStorage.removeItem(REMEMBERED_USERNAME_KEY);
      }

      message.success('登录成功');

      setTimeout(() => {
        const state = location.state as { from?: { pathname?: string } } | null;
        if (state?.from?.pathname) {
          navigate(state.from.pathname, { replace: true });
        } else {
          navigate('/welcome', { replace: true });
        }
      }, 100);
    } catch (e) {
      const err = e as Error;
      message.error(err.message || '登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-left-content">
        <div className="login-brand">
          <div className="login-logo-circle">
            <div className="login-logo-mark">
              <span className="login-logo-main">AI</span>
              <span className="login-logo-sub">EDU</span>
            </div>
          </div>
          <Title level={1} className="login-main-title">
            知学启思
          </Title>
          <Title level={3} className="login-sub-title">
            智能课程创作与教学工作台
          </Title>
          <p className="login-slogan">
            统一管理课程、知识图谱、资源与智能问答，让教学流程更顺滑。
          </p>
        </div>

        <div className="login-features">
          <div className="login-feature-item">
            <div className="login-feature-icon">智</div>
            <div className="login-feature-text">智能问答协作</div>
          </div>
          <div className="login-feature-item">
            <div className="login-feature-icon">图</div>
            <div className="login-feature-text">知识图谱贯通</div>
          </div>
          <div className="login-feature-item">
            <div className="login-feature-icon">课</div>
            <div className="login-feature-text">课程资源整合</div>
          </div>
        </div>
      </div>

      <Card className="login-card">
        <div className="login-form-wrapper">
          <div className="login-form-header">
            <Title level={3} className="login-form-title">
              欢迎登录
            </Title>
            <p className="login-form-desc">输入账号信息后即可进入新的 知学启思 前端界面。</p>
          </div>

          <Form layout="vertical" form={form} onFinish={onFinish}>
            <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
              <Input size="large" prefix={<UserOutlined />} placeholder="请输入用户名" />
            </Form.Item>
            <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password size="large" prefix={<LockOutlined />} placeholder="请输入密码" />
            </Form.Item>
            <Form.Item name="rememberMe" valuePropName="checked" style={{ marginBottom: 20 }}>
              <Checkbox>记住用户名</Checkbox>
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" block size="large" loading={loading}>
                登录
              </Button>
            </Form.Item>
          </Form>
        </div>
      </Card>
    </div>
  );
}
