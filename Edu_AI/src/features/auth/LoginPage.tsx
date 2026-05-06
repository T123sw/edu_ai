import { useEffect, useState } from "react";
import { Button, Card, Checkbox, Form, Input, Typography, message } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import "./LoginPage.css";

const { Title } = Typography;

const REMEMBER_USER_KEY = "edu-ai-remember-user";
const REMEMBERED_USERNAME_KEY = "edu-ai-remembered-username";

export function LoginPage({
  onLogin,
}: {
  onLogin: (payload: { username: string; password: string }) => Promise<void>;
}) {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    const remembered = localStorage.getItem(REMEMBER_USER_KEY) === "true";
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
      await onLogin({ username: values.username, password: values.password });

      if (values.rememberMe) {
        localStorage.setItem(REMEMBER_USER_KEY, "true");
        localStorage.setItem(REMEMBERED_USERNAME_KEY, values.username);
      } else {
        localStorage.removeItem(REMEMBER_USER_KEY);
        localStorage.removeItem(REMEMBERED_USERNAME_KEY);
      }

      message.success("登录成功");
    } catch (error) {
      const err = error as Error;
      message.error(err.message || "登录失败，请稍后重试");
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
            大模型驱动的智能教学平台
          </Title>
          <p className="login-slogan">融合前沿 AI 技术，赋能教育创新</p>
        </div>
        <div className="login-features">
          <div className="login-feature-item">
            <div className="login-feature-icon">🧠</div>
            <div className="login-feature-text">智能问答</div>
          </div>
          <div className="login-feature-item">
            <div className="login-feature-icon">📚</div>
            <div className="login-feature-text">知识库管理</div>
          </div>
          <div className="login-feature-item">
            <div className="login-feature-icon">🎓</div>
            <div className="login-feature-text">教学工具</div>
          </div>
        </div>
      </div>

      <Card className="login-card">
        <div className="login-form-wrapper">
          <div className="login-form-header">
            <Title level={3} className="login-form-title">
              欢迎登录
            </Title>
            <p className="login-form-desc">使用您的账号开始创建专属智能课堂体验</p>
          </div>

          <Form layout="vertical" form={form} onFinish={onFinish}>
            <Form.Item name="username" label="账号" rules={[{ required: true, message: "请输入账号" }]}>
              <Input size="large" prefix={<UserOutlined />} placeholder="请输入账号" />
            </Form.Item>

            <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
              <Input.Password size="large" prefix={<LockOutlined />} placeholder="请输入密码" />
            </Form.Item>

            <Form.Item name="rememberMe" valuePropName="checked" style={{ marginBottom: 20 }}>
              <Checkbox>记住我</Checkbox>
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
