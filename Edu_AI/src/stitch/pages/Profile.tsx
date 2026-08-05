import { useEffect, useRef, useState } from "react";
import { Alert, Button, Form, Input, Modal, Skeleton, Tag, message } from "antd";
import {
  changeUserPassword,
  getUserProfile,
  loadUserAvatar,
  updateUserProfile,
  uploadUserAvatar,
  type UserProfile,
  type UserProfileUpdate,
} from "../api/profile";
import { AppSurface, GlassPanel, MaterialIcon, routeHref, routes, useAppShell } from "../shared";

const quickLinks = [
  { title: "AI 服务配置", subtitle: "配置模型、语音、搜索与解析服务", href: routeHref(routes.settings), icon: "settings_suggest" },
  { title: "我的课程", subtitle: "继续查看课程与工作区", href: routeHref(routes.course), icon: "dashboard" },
  { title: "问答助手", subtitle: "进入教师 AI 工作台", href: routeHref(routes.ai), icon: "forum" },
  { title: "知识图谱", subtitle: "维护节点与课程关系", href: routeHref(routes.graph), icon: "hub" },
];

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
  const { logout } = useAppShell();
  const [profile, setProfile] = useState<UserProfile | null>(null);
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

  async function refreshProfile() {
    setLoading(true);
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
    ["用户名", profile?.username || "—"],
    ["邮箱", profile?.email || "未填写"],
    ["手机号", profile?.phone || "未填写"],
    ["所属部门", profile?.department || "未填写"],
  ];

  return (
    <AppSurface className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(191,219,254,0.72),transparent_24%),linear-gradient(180deg,#f4f8ff_0%,#e7eefc_100%)]">
      <main className="mx-auto w-full max-w-[1500px] px-5 py-7 sm:px-8 lg:px-10">
        <div className="mb-7 flex items-center justify-between gap-4">
          <a href={routeHref(routes.home)} className="inline-flex items-center gap-2 rounded-full border border-[#c6d4ef] bg-white px-4 py-2 text-sm font-semibold text-[#17304a] shadow-sm">
            <MaterialIcon name="arrow_back" />
            返回首页
          </a>
          <Tag color="blue">真实账户资料</Tag>
        </div>

        {loading && !profile ? (
          <GlassPanel className="border border-[#d6dfef] bg-white p-10"><Skeleton active avatar paragraph={{ rows: 6 }} /></GlassPanel>
        ) : !profile ? (
          <Alert type="error" showIcon message="个人资料暂时无法加载" action={<Button onClick={() => void refreshProfile()}>重试</Button>} />
        ) : (
          <>
            <section className="overflow-hidden rounded-[34px] border border-[#d4ddf3] bg-[linear-gradient(135deg,#0f172a_0%,#163a80_46%,#2563eb_100%)] text-white shadow-[0_28px_72px_rgba(15,23,42,0.22)]">
              <div className="grid lg:grid-cols-[1.2fr_0.8fr]">
                <div className="p-8 lg:p-12">
                  <p className="text-xs font-bold uppercase tracking-[0.34em] text-white/80">Account Center</p>
                  <h1 className="mt-5 text-4xl font-black tracking-tight sm:text-5xl">{displayName}</h1>
                  <p className="mt-3 text-lg font-semibold">{roleLabels[profile.role] || profile.role}</p>
                  <p className="mt-7 max-w-2xl text-base leading-8 text-white/90">
                    {profile.bio || "补充个人简介，让账号中心更容易识别你的教学职责。"}
                  </p>
                  <div className="mt-8 flex flex-wrap gap-3">
                    <Button onClick={openProfileEditor} icon={<MaterialIcon name="manage_accounts" />}>编辑资料</Button>
                    <Button onClick={() => setPasswordOpen(true)}>修改密码</Button>
                    <Button danger onClick={logout}>退出登录</Button>
                  </div>
                </div>
                <div className="relative flex items-center justify-center bg-white/10 p-8">
                  <div className="text-center">
                    <button
                      type="button"
                      onClick={() => avatarInput.current?.click()}
                      className="mx-auto grid h-40 w-40 overflow-hidden rounded-[38px] border border-white/35 bg-white/20 text-4xl font-black shadow-xl"
                      aria-label="更换头像"
                    >
                      {avatarUrl ? <img src={avatarUrl} alt={`${displayName}的头像`} className="h-full w-full object-cover" /> : <span className="self-center">{initials}</span>}
                    </button>
                    <button type="button" onClick={() => avatarInput.current?.click()} className="mt-4 text-sm font-semibold text-white">
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
                </div>
              </div>
            </section>

            <div className="mt-7 grid gap-7 lg:grid-cols-[1.1fr_0.9fr]">
              <GlassPanel className="border border-[#d6dfef] bg-white p-7 shadow-[0_20px_44px_rgba(15,23,42,0.08)]">
                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#5b6f8d]">Profile Details</p>
                    <h2 className="mt-1 text-2xl font-black text-[#17304a]">个人资料</h2>
                  </div>
                  <Button onClick={openProfileEditor}>编辑</Button>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  {accountFields.map(([label, value]) => (
                    <div key={label} className="rounded-[22px] border border-[#dde6f5] bg-[#f8fbff] p-5">
                      <p className="text-xs font-bold text-[#60738f]">{label}</p>
                      <p className="mt-2 break-words text-base font-bold text-[#17304a]">{value}</p>
                    </div>
                  ))}
                </div>
              </GlassPanel>

              <div className="space-y-7">
                <GlassPanel className="border border-[#d6dfef] bg-white p-7 shadow-[0_20px_44px_rgba(15,23,42,0.08)]">
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#5b6f8d]">Security</p>
                  <h2 className="mt-1 text-2xl font-black text-[#17304a]">账号安全</h2>
                  <div className="mt-5 space-y-3">
                    <div className="rounded-[20px] bg-[#f8fbff] p-4">
                      <p className="font-bold text-[#17304a]">登录密码</p>
                      <p className="mt-1 text-sm text-[#5f7088]">最近更新：{formatDate(profile.password_updated_at)}</p>
                    </div>
                    <div className="rounded-[20px] bg-[#f8fbff] p-4">
                      <p className="font-bold text-[#17304a]">账号状态</p>
                      <p className="mt-1 text-sm text-[#5f7088]">正常 · {roleLabels[profile.role] || profile.role}</p>
                    </div>
                  </div>
                </GlassPanel>

                <GlassPanel className="border border-[#d6dfef] bg-white p-7 shadow-[0_20px_44px_rgba(15,23,42,0.08)]">
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#5b6f8d]">Quick Access</p>
                  <h2 className="mt-1 text-2xl font-black text-[#17304a]">快捷入口</h2>
                  <div className="mt-5 space-y-3">
                    {quickLinks.map((item) => (
                      <a key={item.title} href={item.href} className="flex items-center justify-between rounded-[20px] border border-[#dde6f5] bg-[#f8fbff] px-5 py-4 transition hover:border-[#9cb9f2] hover:bg-white">
                        <div className="flex items-center gap-3">
                          <span className="grid h-10 w-10 place-items-center rounded-xl bg-[#eaf1ff] text-[#2357b8]"><MaterialIcon name={item.icon} /></span>
                          <span><span className="block text-sm font-bold text-[#17304a]">{item.title}</span><span className="mt-1 block text-xs text-[#5f7088]">{item.subtitle}</span></span>
                        </div>
                        <MaterialIcon name="arrow_forward" className="text-[#2357b8]" />
                      </a>
                    ))}
                  </div>
                </GlassPanel>
              </div>
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
