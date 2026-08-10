import { useEffect, useRef, useState } from "react";
import { Alert, Button, Form, Input, Modal, Skeleton, message } from "antd";
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
import { AppSurface, GlassPanel, MaterialIcon, routeHref, routes, useAppShell } from "../shared";
import { homeHashForRole } from "../shared/routes/roleCourseRouteResolver";
import { presentAccessibleCourseCount } from "./profilePresentation";

const roleLabels: Record<string, string> = {
  admin: "系统管理员",
  teacher: "教师",
  student: "学生",
};

function formatDate(value: string) {
  if (!value) return "尚未更新";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "尚未更新" : date.toLocaleString("zh-CN");
}

export function ProfilePage() {
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
    ["用户名", profile?.username || "—", "👤"],
    ["邮箱", profile?.email || "未填写", "✉"],
    ["手机号", profile?.phone || "未填写", "☎"],
    ["所属部门", profile?.department || "未填写", "▦"],
    ["可访问课程", presentAccessibleCourseCount(accessibleCourseCount), "☰"],
    ["系统角色", profile ? (roleLabels[profile.role] || profile.role) : "—", "🎓"],
  ];

  return (
    <AppSurface className="min-h-screen bg-[radial-gradient(circle_at_top_left,var(--accent-soft),transparent_26%),var(--app-bg)]">
      <main className="mx-auto w-full max-w-[1280px] px-5 py-7 sm:px-8 lg:px-10 lg:py-10">
        <div className="mb-6 flex items-center justify-between gap-4">
          <a href={homeHashForRole(user?.role)} className="inline-flex items-center gap-2 rounded-full border border-(--shell-border) bg-white/90 px-4 py-2.5 text-sm font-semibold text-(--accent-strong) shadow-sm transition hover:border-(--accent-border) hover:bg-white">
            <MaterialIcon name="arrow_back" />
            返回首页
          </a>
          <span className="hidden text-sm text-(--muted-text) sm:inline">个人账号与服务设置</span>
        </div>

        {loading && !profile ? (
          <GlassPanel className="border border-[#d6dfef] bg-white p-10"><Skeleton active avatar paragraph={{ rows: 6 }} /></GlassPanel>
        ) : !profile ? (
          <Alert type="error" showIcon message="个人资料暂时无法加载" action={<Button onClick={() => void refreshProfile()}>重试</Button>} />
        ) : (
          <>
            <section className="relative overflow-hidden rounded-[30px] border border-(--accent-border) bg-[linear-gradient(135deg,var(--accent-strong)_0%,var(--accent)_100%)] text-white shadow-[0_24px_64px_var(--accent-shadow)]">
              <div className="absolute -right-16 -top-28 h-72 w-72 rounded-full border border-white/15 bg-white/8" aria-hidden="true" />
              <div className="relative flex flex-col gap-7 p-7 sm:p-9 lg:flex-row lg:items-center lg:justify-between lg:px-11 lg:py-10">
                <div className="flex min-w-0 flex-col gap-6 sm:flex-row sm:items-center">
                  <div className="shrink-0 text-center">
                    <button
                      type="button"
                      onClick={() => avatarInput.current?.click()}
                      className="group relative mx-auto grid h-28 w-28 overflow-hidden rounded-[28px] border border-white/35 bg-white/15 text-3xl font-black shadow-[0_14px_32px_rgba(15,23,42,0.2)] transition hover:bg-white/20"
                      aria-label="更换头像"
                    >
                      {avatarUrl ? <img src={avatarUrl} alt={`${displayName}的头像`} className="h-full w-full object-cover" /> : <span className="self-center">{initials}</span>}
                      <span className="absolute inset-x-0 bottom-0 bg-slate-950/55 py-1.5 text-[11px] font-semibold opacity-0 transition group-hover:opacity-100">更换头像</span>
                    </button>
                    <button type="button" onClick={() => avatarInput.current?.click()} className="mt-2 text-xs font-semibold text-white/75 transition hover:text-white">
                      点击更换头像
                    </button>
                    <input
                      ref={avatarInput}
                      className="hidden"
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={(event) => void handleAvatar(event.target.files?.[0])}
                    />
                  </div>
                  <div className="min-w-0 text-center sm:text-left">
                    <p className="text-[11px] font-bold uppercase tracking-[0.28em] text-white/70">Account Center</p>
                    <div className="mt-3 flex flex-wrap items-center justify-center gap-3 sm:justify-start">
                      <h1 className="truncate text-3xl font-black tracking-tight sm:text-4xl">{displayName}</h1>
                      <span className="rounded-full border border-white/20 bg-white/12 px-3 py-1 text-xs font-bold">
                        {roleLabels[profile.role] || profile.role}
                      </span>
                    </div>
                    <p className="mt-4 max-w-2xl text-sm leading-7 text-white/82 sm:text-base">
                      {profile.bio || "补充个人简介，让账号中心更容易识别你的教学职责。"}
                    </p>
                  </div>
                </div>
                <Button danger ghost onClick={logout} className="self-center border-white/45! text-white! hover:border-white! hover:bg-white/10! lg:self-auto">
                  退出登录
                </Button>
              </div>
            </section>

            <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1.08fr_0.92fr]">
              <GlassPanel className="border border-(--shell-border) bg-white/92 p-6 shadow-[0_16px_40px_var(--panel-shadow)] sm:p-7">
                <div className="mb-5 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-(--muted-text)">Profile Details</p>
                    <h2 className="mt-1 text-2xl font-black text-(--accent-strong)">个人资料</h2>
                  </div>
                  <Button type="primary" onClick={openProfileEditor} icon={<MaterialIcon name="edit_note" />}>编辑资料</Button>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {accountFields.map(([label, value, icon]) => (
                    <div key={label} className="flex min-w-0 items-center gap-3 rounded-[18px] border border-(--shell-border) bg-(--surface-subtle) p-4">
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] bg-(--accent-soft) text-(--accent)">
                        {icon}
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-(--muted-text)">{label}</p>
                        <p className="mt-1 truncate text-sm font-bold text-(--app-text)" title={value}>{value}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </GlassPanel>

              <GlassPanel className="border border-(--shell-border) bg-white/92 p-6 shadow-[0_16px_40px_var(--panel-shadow)] sm:p-7">
                <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-(--muted-text)">Account & Security</p>
                <h2 className="mt-1 text-2xl font-black text-(--accent-strong)">账号与服务</h2>
                <div className="mt-5 space-y-3">
                  <div className="flex items-center justify-between gap-4 rounded-[18px] border border-(--shell-border) bg-(--surface-subtle) p-4">
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] bg-(--accent-soft) text-(--accent)">🔒</span>
                      <span className="min-w-0">
                        <span className="block font-bold text-(--app-text)">登录密码</span>
                        <span className="mt-1 block truncate text-xs text-(--muted-text)">最近更新：{formatDate(profile.password_updated_at)}</span>
                      </span>
                    </span>
                    <Button size="small" onClick={() => setPasswordOpen(true)}>修改</Button>
                  </div>
                  <div className="flex items-center gap-3 rounded-[18px] border border-(--shell-border) bg-(--surface-subtle) p-4">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] bg-emerald-50 font-bold text-emerald-600">✓</span>
                    <span>
                      <span className="block font-bold text-(--app-text)">账号状态</span>
                      <span className="mt-1 block text-xs text-(--muted-text)">正常 · {roleLabels[profile.role] || profile.role}</span>
                    </span>
                  </div>
                  <a
                    href={routeHref(routes.settings)}
                    className="group flex items-center justify-between gap-4 rounded-[18px] border border-(--shell-border) bg-(--surface-subtle) p-4 transition hover:border-(--accent-border) hover:bg-(--accent-soft)"
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] bg-(--accent-soft) text-(--accent)"><MaterialIcon name="settings_suggest" /></span>
                      <span className="min-w-0">
                        <span className="block font-bold text-(--app-text)">AI 服务配置</span>
                        <span className="mt-1 block truncate text-xs text-(--muted-text)">配置对话、知识库、语音及外部服务</span>
                      </span>
                    </span>
                    <MaterialIcon name="arrow_forward" className="shrink-0 text-(--accent) transition group-hover:translate-x-1" />
                  </a>
                </div>
              </GlassPanel>
            </div>
          </>
        )}
      </main>

      <Modal title="编辑个人资料" open={editOpen} okText="保存" cancelText="取消" confirmLoading={saving} onOk={() => void saveProfile()} onCancel={() => setEditOpen(false)}>
        <Form form={profileForm} layout="vertical" requiredMark={false}>
          <Form.Item name="display_name" label="显示名称" rules={[{ required: true, message: "请填写显示名称" }]}><Input maxLength={80} /></Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ type: "email", message: "邮箱格式不正确" }]}><Input maxLength={160} /></Form.Item>
          <Form.Item name="phone" label="手机号"><Input maxLength={40} /></Form.Item>
          <Form.Item name="department" label="所属部门"><Input maxLength={120} /></Form.Item>
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
