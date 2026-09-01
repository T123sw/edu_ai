import { useEffect, useState } from "react";

import {
  addCourseMember,
  listCourseMembers,
  removeCourseMember,
  updateCourseMember,
} from "../api/courses";
import type { BackendCourse, CourseMember } from "../api/types";
import { MaterialIcon } from "../shared";

export function CourseMembersPanel({ course }: { course: BackendCourse }) {
  const [members, setMembers] = useState<CourseMember[]>([]);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<CourseMember["role"]>("viewer");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  async function reload() {
    setMembers(await listCourseMembers(course.id));
  }

  useEffect(() => {
    let cancelled = false;
    listCourseMembers(course.id)
      .then((items) => { if (!cancelled) setMembers(items); })
      .catch((reason) => { if (!cancelled) setFeedback(reason instanceof Error ? reason.message : "成员列表加载失败"); });
    return () => { cancelled = true; };
  }, [course.id]);

  async function handleAdd() {
    if (!userId.trim()) return;
    setBusy(true);
    setFeedback(null);
    try {
      await addCourseMember(course.id, { user_id: userId.trim(), role });
      setUserId("");
      await reload();
      setFeedback("成员已加入课程。");
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "添加成员失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRoleChange(member: CourseMember, nextRole: CourseMember["role"]) {
    setBusy(true);
    setFeedback(null);
    try {
      await updateCourseMember(course.id, member.user_id, nextRole);
      await reload();
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "更新成员角色失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(member: CourseMember) {
    if (!window.confirm(`确定将 ${member.username} 移出课程吗？`)) return;
    setBusy(true);
    setFeedback(null);
    try {
      await removeCourseMember(course.id, member.user_id);
      await reload();
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "移除成员失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-6 rounded-[28px] border border-(--shell-border) bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-600">课程成员</p>
          <h3 className="mt-1 text-xl font-bold text-(--app-text)">统一管理教师与学生</h3>
          <p className="mt-1 text-sm text-(--muted-text)">学生可自行使用课程码加入；也可以在这里按用户名添加成员。</p>
        </div>
        <div className="rounded-2xl bg-blue-50 px-4 py-3 text-right">
          <span className="block text-xs text-blue-700">学生加入课程码</span>
          <strong className="font-mono text-2xl tracking-[0.2em] text-blue-950">{course.course_code || "未生成"}</strong>
          {course.course_code ? (
            <button type="button" className="ml-3 text-xs font-bold text-blue-700" onClick={() => void navigator.clipboard.writeText(course.course_code || "")}>复制</button>
          ) : null}
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-[1fr_160px_auto]">
        <input className="rounded-xl border border-(--shell-border) px-4 py-3 text-sm" value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="输入用户名" />
        <select className="rounded-xl border border-(--shell-border) px-3 py-3 text-sm" value={role} onChange={(event) => setRole(event.target.value as CourseMember["role"])}>
          <option value="viewer">学生</option>
          <option value="editor">协作教师</option>
          <option value="owner">负责人</option>
        </select>
        <button type="button" className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white disabled:opacity-50" disabled={busy || !userId.trim()} onClick={() => void handleAdd()}><MaterialIcon name="person_add" /> 添加</button>
      </div>
      {feedback ? <p className="mt-3 text-sm text-(--muted-text)" role="status">{feedback}</p> : null}

      <div className="mt-5 divide-y divide-(--shell-border) rounded-2xl border border-(--shell-border)">
        {members.map((member) => (
          <div key={member.user_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <span className="grid size-9 place-items-center rounded-full bg-slate-100"><MaterialIcon name={member.system_role === "student" ? "school" : "person"} /></span>
            <div className="min-w-0 flex-1"><strong className="block truncate text-sm">{member.username}</strong><small className="text-(--muted-text)">{member.system_role === "student" ? "学生账号" : "教师账号"}</small></div>
            <select disabled={busy} className="rounded-lg border border-(--shell-border) px-3 py-2 text-sm" value={member.role} onChange={(event) => void handleRoleChange(member, event.target.value as CourseMember["role"])}>
              <option value="owner">负责人</option><option value="editor">协作教师</option><option value="viewer">学生</option>
            </select>
            <button type="button" disabled={busy} className="rounded-lg px-3 py-2 text-sm font-semibold text-red-600" onClick={() => void handleRemove(member)}>移除</button>
          </div>
        ))}
      </div>
    </section>
  );
}
