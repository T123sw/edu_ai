import { useEffect, useState } from "react";
import { Button, Card, Checkbox, Form, Input } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import "./LoginPage.css";

const REMEMBER_USER_KEY = "edu-ai-remember-user";
const REMEMBERED_USERNAME_KEY = "edu-ai-remembered-username";

export function LoginPage({ onLogin }: { onLogin: (payload: { username: string; password: string }) => Promise<void> }) {
  const [loading, setLoading] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [form] = Form.useForm();
  const showDemoAccount = import.meta.env.VITE_SHOW_DEMO_ACCOUNT === "true";

  useEffect(() => {
    const username = localStorage.getItem(REMEMBERED_USERNAME_KEY);
    if (localStorage.getItem(REMEMBER_USER_KEY) === "true" && username) {
      form.setFieldsValue({ username, rememberMe: true });
    }
  }, [form]);

  async function onFinish(values: { username: string; password: string; rememberMe?: boolean }) {
    setLoading(true);
    setLoginError(null);
    try {
      await onLogin({ username: values.username, password: values.password });
      if (values.rememberMe) {
        localStorage.setItem(REMEMBER_USER_KEY, "true");
        localStorage.setItem(REMEMBERED_USERNAME_KEY, values.username);
      } else {
        localStorage.removeItem(REMEMBER_USER_KEY);
        localStorage.removeItem(REMEMBERED_USERNAME_KEY);
      }
    } catch (reason) {
      setLoginError(reason instanceof Error ? reason.message : "登录失败，请检查账号、密码和服务状态。" );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-left-content" aria-label="平台介绍">
        <div className="login-brand">
          <div className="login-logo-circle" aria-hidden="true">
            <div className="login-logo-mark">
              <span className="login-logo-main">AI</span>
              <span className="login-logo-sub">EDU</span>
            </div>
          </div>
          <h1 className="login-main-title">知学启思</h1>
          <h2 className="login-sub-title">大模型驱动的智能教学平台</h2>
          <p className="login-slogan">融合前沿 AI 技术，赋能课程建设与教学创新</p>
        </div>
        <div className="login-features" aria-label="平台能力">
          <div className="login-feature-item"><span className="login-feature-icon" aria-hidden="true">🧠</span><span className="login-feature-text">智能问答</span></div>
          <div className="login-feature-item"><span className="login-feature-icon" aria-hidden="true">📚</span><span className="login-feature-text">课程知识</span></div>
          <div className="login-feature-item"><span className="login-feature-icon" aria-hidden="true">🎓</span><span className="login-feature-text">教学工具</span></div>
        </div>
      </section>

      <Card className="login-card">
        <div className="login-form-wrapper">
          <div className="login-form-header">
            <p className="login-form-kicker">教师账号</p>
            <h2 id="login-title" className="login-form-title">登录 Edu AI</h2>
            <p className="login-form-desc">使用系统分配的账号进入你有权访问的全部课程</p>
          </div>
          {loginError ? <div className="login-error" role="alert"><strong>未能登录</strong><span>{loginError}</span></div> : null}
          <Form layout="vertical" form={form} onFinish={onFinish} requiredMark={false} aria-labelledby="login-title">
            <Form.Item name="username" label="账号" rules={[{ required: true, message: "请输入账号" }]}>
              <Input size="large" prefix={<UserOutlined />} placeholder="请输入账号" autoComplete="username" />
            </Form.Item>
            <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
              <Input.Password size="large" prefix={<LockOutlined />} placeholder="请输入密码" autoComplete="current-password" />
            </Form.Item>
            <div className="login-form-options">
              <Form.Item name="rememberMe" valuePropName="checked" noStyle><Checkbox>记住账号</Checkbox></Form.Item>
              <span>账号或权限有问题，请联系系统管理员</span>
            </div>
            <Button type="primary" htmlType="submit" block size="large" loading={loading}>登录</Button>
          </Form>
          {showDemoAccount ? <p className="login-demo-hint">开发演示账号已启用，请使用项目运行配置中提供的测试账号。</p> : null}
        </div>
      </Card>
    </main>
  );
}
