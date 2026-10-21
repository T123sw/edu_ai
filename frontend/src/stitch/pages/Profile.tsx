import { useEffect, useRef, useState } from "react";
import Alert from "antd/es/alert";
import Button from "antd/es/button";
import Form from "antd/es/form";
import Input from "antd/es/input";
import Modal from "antd/es/modal";
import Skeleton from "antd/es/skeleton";
import message from "antd/es/message";
import {
  changeUserPassword,
  getUserProfile,
  loadUserAvatar,
  updateUserProfile,
  uploadUserAvatar,
  type UserProfile,
  type UserProfileUpdate,
} from "../api/profile";
import { listCourses } from "../api/courses";
import { useAuthSession } from "../authSession";
import { AppSurface, routeHref, routes, useAppShell } from "../shared";
import { homeHashForRole } from "../shared/routes/roleCourseRouteResolver";
import { presentAccessibleCourseCount } from "./profilePresentation";

import ArrowLeftOutlined from "@ant-design/icons/es/icons/ArrowLeftOutlined.js";
import ArrowRightOutlined from "@ant-design/icons/es/icons/ArrowRightOutlined.js";
import CameraOutlined from "@ant-design/icons/es/icons/CameraOutlined.js";
import EditOutlined from "@ant-design/icons/es/icons/EditOutlined.js";
import LogoutOutlined from "@ant-design/icons/es/icons/LogoutOutlined.js";
import LockOutlined from "@ant-design/icons/es/icons/LockOutlined.js";
import BookOutlined from "@ant-design/icons/es/icons/BookOutlined.js";
import ApiOutlined from "@ant-design/icons/es/icons/ApiOutlined.js";
import "./profile.css";

function formatDate(value: string) {
  if (!value) return "尚未更新";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "尚未更新" : date.toLocaleString("zh-CN");
}

export function ProfilePage({ homeHref }: { homeHref?: string } = {}) {
  const { user } = useAuthSession();
  const { logout } = useAppShell();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [accessibleCourseCount, setAccessibleCourseCount] = useState<number | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState("");
  const avatarUrlRef = useRef("");
  const avatarInput = useRef<HTMLInputElement>(null);
  const [profileForm] = Form.useForm<UserProfileUpdate>();
  const [passwordForm] = Form.useForm<{
    currentPassword: string;
    newPassword: string;
    confirmPassword: string;
  }>();

  async function refreshAccessibleCourseCount() {
    setAccessibleCourseCount(undefined);
    try {
      const courses = await listCourses();
      setAccessibleCourseCount(courses.length);
    } catch {
      setAccessibleCourseCount(null);
    }
  }

  async function refreshProfile() {
    setLoading(true);
    void refreshAccessibleCourseCount();
    try {
      const next = await getUserProfile();
      setProfile(next);
      if (next.avatar_url) {
        const blob = await loadUserAvatar();
        setAvatarUrl((previous) => {
          if (previous) URL.revokeObjectURL(previous);
          const nextUrl = URL.createObjectURL(blob);
          avatarUrlRef.current = nextUrl;
          return nextUrl;
        });
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "个人资料加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshProfile();
    return () => {
      if (avatarUrlRef.current) URL.revokeObjectURL(avatarUrlRef.current);
    };
  }, []);

  function openProfileEditor() {
    if (!profile) return;
    profileForm.setFieldsValue({
      display_name: profile.display_name,
      email: profile.email,
      phone: profile.phone,
      department: profile.department,
      bio: profile.bio,
    });
    setEditOpen(true);
  }

  async function saveProfile() {
    const values = await profileForm.validateFields();
    setSaving(true);
    try {
      setProfile(await updateUserProfile(values));
      setEditOpen(false);
      message.success("个人资料已更新");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function savePassword() {
    const values = await passwordForm.validateFields();
    setSaving(true);
    try {
      await changeUserPassword(values.currentPassword, values.newPassword);
      passwordForm.resetFields();
      setPasswordOpen(false);
      message.success("密码已更新，下次登录请使用新密码");
      await refreshProfile();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "密码修改失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleAvatar(file?: File) {
    if (!file) return;
    setSaving(true);
    try {
      const updated = await uploadUserAvatar(file);
      setProfile(updated);
      const blob = await loadUserAvatar();
      setAvatarUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        const nextUrl = URL.createObjectURL(blob);
        avatarUrlRef.current = nextUrl;
        return nextUrl;
      });
      message.success("头像已更新");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "头像上传失败");
    } finally {
      setSaving(false);
      if (avatarInput.current) avatarInput.current.value = "";
    }
  }

  const displayName = profile?.display_name || profile?.username || "用户";
  const initials = displayName.slice(0, 2).toUpperCase();
  const accountFields = [
    ["显示名称", displayName],
    ["用户名", profile?.username || "—"],
    ["邮箱", profile?.email || "未填写"],
    ["手机号", profile?.phone || "未填写"],
  ];

  return (
    <AppSurface className="edu-profile">
      <main className="profile-page">
        <header className="profile-topbar">
          <a href={homeHref ?? homeHashForRole(user?.role)} className="profile-back"><ArrowLeftOutlined /> 返回首页</a>
          <div className="profile-wordmark"><span className="profile-brand-symbol" aria-hidden="true">e</span>Edu AI<span className="profile-breadcrumb" aria-hidden="true">/</span><h1>个人中心</h1></div>
        </header>

        {loading && !profile ? (
          <section className="profile-sheet profile-loading"><Skeleton active avatar paragraph={{ rows: 6 }} /></section>
        ) : !profile ? (
          <Alert type="error" showIcon message="个人资料暂时无法加载" action={<Button onClick={() => void refreshProfile()}>重试</Button>} />
        ) : (
          <div className="profile-sheet">
            <div className="profile-cover" aria-hidden="true">
              <svg viewBox="0 0 1200 200" preserveAspectRatio="xMidYMid slice">
                <path className="profile-cover-ribbon" d="M-80 230C160 240 280 10 520 60S840 300 1280 50L1280 270H-80Z" />
                <path className="profile-cover-ribbon secondary" d="M-80 260C160 220 330 30 570 90S880 280 1280 90L1280 270H-80Z" />
                <g className="profile-cover-lines" fill="none">
                  <path d="M460-90C400 0 700 50 830 160S1080 290 1290 120" />
                  <path d="M490-90C430 0 730 50 860 160S1110 290 1320 120" />
                  <path d="M520-90C460 0 760 50 890 160S1140 290 1350 120" />
                  <path d="M550-90C490 0 790 50 920 160S1170 290 1380 120" />
                  <path d="M580-90C520 0 820 50 950 160S1200 290 1410 120" />
                </g>
              </svg>
            </div>
            <div className="profile-identity">
              <button type="button" onClick={() => avatarInput.current?.click()} disabled={saving} className="profile-avatar" aria-label="更换头像">
                {avatarUrl ? <img src={avatarUrl} alt={`${displayName}的头像`} /> : <span>{initials}</span>}
                <span className="profile-avatar-camera"><CameraOutlined /></span>
              </button>
              <input ref={avatarInput} className="hidden" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void handleAvatar(event.target.files?.[0])} />
              <div className="profile-identity-copy">
                <h2>{displayName}</h2>
                <div className="profile-identity-meta"><span className="profile-course-count"><BookOutlined /><strong>{presentAccessibleCourseCount(accessibleCourseCount)}</strong> 门可访问课程</span></div>
              </div>
              <Button className="profile-edit" onClick={openProfileEditor} icon={<EditOutlined />}>编辑资料</Button>
            </div>

            <section className="profile-body" aria-labelledby="profile-details-title">
              <div className="profile-section-heading"><h2 id="profile-details-title">账号资料</h2></div>
              <dl className="profile-details">
                {accountFields.map(([label, value]) => (
                  <div key={label}><dt>{label}</dt><dd className={value === "未填写" ? "is-empty" : undefined}>{value}</dd></div>
                ))}
                {profile.bio && <div className="profile-bio"><dt>个人简介</dt><dd>{profile.bio}</dd></div>}
              </dl>
              <div className="profile-setting-row">
                <span className="profile-setting-icon"><LockOutlined /></span>
                <div><h3>登录密码</h3><p>{profile.password_updated_at ? `更新于 ${formatDate(profile.password_updated_at)}` : "使用独立密码保护你的账号"}</p></div>
                <Button onClick={() => setPasswordOpen(true)}>修改密码</Button>
              </div>
              <a href={routeHref(routes.settings)} className="profile-setting-row profile-service-link" aria-label="AI 服务配置">
                <span className="profile-setting-icon"><ApiOutlined /></span>
                <div><h3>AI 服务配置</h3><p>管理模型与服务连接</p></div>
                <ArrowRightOutlined className="profile-setting-arrow" />
              </a>
            </section>
            <footer className="profile-footer"><button type="button" onClick={logout}><LogoutOutlined />退出登录</button></footer>
          </div>
        )}
      </main>

      <Modal title="编辑个人资料" open={editOpen} okText="保存" cancelText="取消" confirmLoading={saving} onOk={() => void saveProfile()} onCancel={() => setEditOpen(false)}>
        <Form form={profileForm} layout="vertical" requiredMark={false}>
          <Form.Item name="display_name" label="显示名称" rules={[{ required: true, message: "请填写显示名称" }]}><Input maxLength={80} /></Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ type: "email", message: "邮箱格式不正确" }]}><Input maxLength={160} /></Form.Item>
          <Form.Item name="phone" label="手机号"><Input maxLength={40} /></Form.Item>
          <Form.Item name="bio" label="个人简介"><Input.TextArea rows={4} maxLength={600} showCount /></Form.Item>
        </Form>
      </Modal>

      <Modal title="修改登录密码" open={passwordOpen} okText="确认修改" cancelText="取消" confirmLoading={saving} onOk={() => void savePassword()} onCancel={() => { setPasswordOpen(false); passwordForm.resetFields(); }}>
        <Form form={passwordForm} layout="vertical" requiredMark={false}>
          <Form.Item name="currentPassword" label="当前密码" rules={[{ required: true, message: "请输入当前密码" }]}><Input.Password autoComplete="current-password" /></Form.Item>
          <Form.Item name="newPassword" label="新密码" rules={[{ required: true, min: 8, message: "新密码至少 8 位" }]}><Input.Password autoComplete="new-password" /></Form.Item>
          <Form.Item name="confirmPassword" label="确认新密码" dependencies={["newPassword"]} rules={[{ required: true, message: "请再次输入新密码" }, ({ getFieldValue }) => ({ validator(_, value) { return !value || getFieldValue("newPassword") === value ? Promise.resolve() : Promise.reject(new Error("两次输入的密码不一致")); } })]}><Input.Password autoComplete="new-password" /></Form.Item>
        </Form>
      </Modal>
    </AppSurface>
  );
}
