import { useEffect, useState } from "react";
import { Button, Checkbox, Form, Input } from "antd";
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
      <section className="login-introduction">
        <a className="login-wordmark" href="#home">Edu AI</a>
        <div>
          <p className="login-kicker">课程中心 · 教师工作台</p>
          <h1>让课程资料、AI 生成与教学成果保持在同一个上下文中</h1>
          <p className="login-lead">教师进入课程后，可以共同维护资料和知识结构，并在同一课程空间中完成问答、资源生成与课堂制作。</p>
          <ul className="login-capabilities">
            <li><strong>以课程组织</strong><span>课程成员看到同一份信息和资源</span></li>
            <li><strong>教师工作流</strong><span>从资料准备到成果发布保持连续</span></li>
            <li><strong>可恢复任务</strong><span>生成过程进入后台任务中心</span></li>
          </ul>
        </div>
      </section>

      <section className="login-card" aria-labelledby="login-title">
        <div className="login-form-header">
          <p>教师账号</p>
          <h2 id="login-title">登录 Edu AI</h2>
          <span>使用系统分配的账号进入你有权访问的全部课程。</span>
        </div>
        {loginError ? <div className="login-error" role="alert"><strong>未能登录</strong><span>{loginError}</span></div> : null}
        <Form layout="vertical" form={form} onFinish={onFinish} requiredMark={false}>
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
      </section>
    </main>
  );
}
