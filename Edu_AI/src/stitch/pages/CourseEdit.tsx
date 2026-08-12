import { useEffect, useRef, useState, type ReactNode } from "react";

import { deleteCourse, updateCourse } from "../api/courses";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { canCourse } from "../course/coursePermissions";
import { CourseMembersPanel } from "../course/CourseMembersPanel";
import {
  AppSurface,
  GlassPanel,
  MaterialIcon,
  useAppShell,
} from "../shared";

type CourseFormState = {
  title: string;
  description: string;
  objectives: string;
  coverImage: string;
};

const EMPTY_FORM: CourseFormState = {
  title: "",
  description: "",
  objectives: "",
  coverImage: "",
};

function readFileAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () =>
      resolve(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => reject(new Error("读取本地图片失败"));
    reader.readAsDataURL(file);
  });
}

export function CourseEditPage() {
  const { course, courseRole, loading, error, reload } = useCourseRoute();
  const { setSelectedCourse } = useAppShell();
  const canEdit = canCourse(courseRole, "edit");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [formState, setFormState] = useState<CourseFormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [conflictDraft, setConflictDraft] = useState<CourseFormState | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");

  useEffect(() => {
    if (!course) {
      setFormState(EMPTY_FORM);
      return;
    }
    setFormState({
      title: course.title || "",
      description: course.description || "",
      objectives: Array.isArray(course.objectives)
        ? course.objectives.join("\n")
        : "",
      coverImage: course.knowledgeGraph || "",
    });
    setFeedback(null);
  }, [course, courseRole]);

  function updateField(field: keyof CourseFormState, value: string) {
    setFormState((current) => ({ ...current, [field]: value }));
  }

  async function handleLocalImageSelection(files: FileList | null) {
    const file = files?.[0];
    if (!file || !canEdit) return;
    setUploadingImage(true);
    setFeedback(null);
    try {
      updateField("coverImage", await readFileAsDataUrl(file));
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "读取图片失败");
    } finally {
      setUploadingImage(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleSave() {
    if (!course || !canEdit) return;
    if (!formState.title.trim()) {
      setFeedback("请填写课程名称后再保存。");
      return;
    }
    setSaving(true);
    setFeedback(null);
    try {
      await updateCourse(course.id, {
        title: formState.title.trim(),
        description: formState.description.trim(),
        icon: course.icon,
        color: course.color,
        objectives: formState.objectives
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        knowledgeGraph: formState.coverImage.trim(),
        expected_revision: course.revision,
      });
      await reload();
      setConflictDraft(null);
      setFeedback("课程信息已保存，其他协作教师刷新后可立即看到更新。");
    } catch (reason) {
      const status =
        typeof reason === "object" && reason !== null && "status" in reason
          ? Number(reason.status)
          : 0;
      if (status === 409) {
        setConflictDraft(formState);
        await reload();
        setFeedback("课程刚刚被其他教师更新。系统已保护你的修改，并载入服务器上的最新版本。");
      } else {
        setFeedback(
          status === 0
            ? "暂时无法连接服务器，请检查服务后重试。"
            : "课程信息暂时无法保存，请稍后重试。",
        );
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteCourse() {
    if (!course || courseRole !== "owner" || deleteConfirmation !== course.title || deleting) return;
    setDeleting(true);
    setFeedback(null);
    try {
      await deleteCourse(course.id);
      window.localStorage.removeItem(`edu-ai:course-kb-build:${course.id}`);
      setSelectedCourse(null);
      window.location.hash = "#home";
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "课程删除失败，请稍后重试。");
      setDeleting(false);
    }
  }

  if (loading) {
    return <CourseStateCard message="正在加载课程信息…" />;
  }
  if (error || !course) {
    return (
      <CourseStateCard
        message={error?.message || "当前链接没有有效课程，请返回课程列表重新选择。"}
      />
    );
  }

  return (
    <AppSurface className="min-h-[calc(100vh-var(--course-header-height))]">
      <main className="course-settings">
        <section className="course-settings__toolbar">
          <div>
            <h2>{canEdit ? "维护课程信息" : "查看课程信息"}</h2>
            <p>{canEdit ? "名称、简介和教学目标保存后会同步到整个课程工作区。" : "当前账号只有查看权限。"}</p>
          </div>
          {canEdit ? (
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving || uploadingImage}
              className="course-settings__save"
            >
              <MaterialIcon name="check_circle" />
              {saving ? "保存中…" : "保存更改"}
            </button>
          ) : null}
        </section>

        <div className="course-settings__content">
          {!canEdit ? (
            <p className="mb-5 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
              课程信息仅供查看。如需修改，请联系课程负责人调整你的课程角色。
            </p>
          ) : null}
          {feedback ? (
            <p className="mb-5 rounded-2xl border border-(--shell-border) bg-white px-4 py-3 text-sm text-(--muted-text)">
              {feedback}
            </p>
          ) : null}
          {conflictDraft ? (
            <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950" role="alert">
              <strong className="block">发现协作编辑冲突</strong>
              <p className="mt-1 text-xs leading-6 text-amber-800">请先检查最新版本。你可以重新加载最新版本，或复制本次修改用于对照和合并。</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className="rounded-lg bg-amber-900 px-3 py-2 text-xs font-bold text-white" onClick={() => { setConflictDraft(null); void reload(); }}>
                  重新加载最新版本
                </button>
                <button type="button" className="rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-bold" onClick={() => void navigator.clipboard.writeText([
                  `课程名称：${conflictDraft.title}`,
                  `课程简介：${conflictDraft.description}`,
                  `教学目标：\n${conflictDraft.objectives}`,
                ].join("\n\n"))}>
                  复制我的修改
                </button>
              </div>
            </div>
          ) : null}

          <GlassPanel className="course-settings__form">
            {canEdit ? (
              <div className="space-y-5">
                <Field label="课程名称">
                  <input
                    value={formState.title}
                    onChange={(event) => updateField("title", event.target.value)}
                    className="w-full rounded-[20px] border border-(--shell-border) bg-(--input-surface) px-4 py-3 text-sm text-(--app-text) outline-hidden"
                  />
                </Field>
                <Field label="课程简介">
                  <textarea
                    value={formState.description}
                    onChange={(event) =>
                      updateField("description", event.target.value)
                    }
                    className="min-h-[112px] w-full rounded-[20px] border border-(--shell-border) bg-(--input-surface) px-4 py-3 text-sm leading-7 text-(--app-text) outline-hidden"
                  />
                </Field>
                <Field label="教学目标（每行一个）">
                  <textarea
                    value={formState.objectives}
                    onChange={(event) =>
                      updateField("objectives", event.target.value)
                    }
                    className="min-h-[160px] w-full rounded-[20px] border border-(--shell-border) bg-(--input-surface) px-4 py-3 text-sm leading-7 text-(--app-text) outline-hidden"
                  />
                </Field>
                <Field label="课程封面">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(event) =>
                      void handleLocalImageSelection(event.target.files)
                    }
                  />
                  <CoverPreview src={formState.coverImage} />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadingImage}
                    className="mt-3 rounded-full border border-(--shell-border) bg-white px-4 py-2 text-sm font-semibold text-(--accent-strong)"
                  >
                    {uploadingImage ? "读取图片中…" : "选择本地图片"}
                  </button>
                </Field>
              </div>
            ) : (
              <dl className="grid gap-6 sm:grid-cols-2">
                <ReadOnlyValue label="课程名称" value={course.title} />
                <ReadOnlyValue label="课程角色" value="查看者" />
                <ReadOnlyValue
                  label="课程简介"
                  value={course.description || "暂未填写"}
                  wide
                />
                <ReadOnlyValue
                  label="教学目标"
                  value={course.objectives?.join("\n") || "暂未填写"}
                  wide
                />
                <div className="sm:col-span-2">
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-(--muted-text)">
                    课程封面
                  </p>
                  <CoverPreview src={course.knowledgeGraph || ""} />
                </div>
              </dl>
            )}
          </GlassPanel>
          {courseRole === "owner" ? <CourseMembersPanel course={course} /> : null}
          {courseRole === "owner" ? (
            <GlassPanel className="mt-6 border-red-200 bg-red-50/80 p-6">
              <h3 className="text-lg font-bold text-red-900">删除课程</h3>
              <p className="mt-2 text-sm leading-6 text-red-800">这会永久删除课程、成员关系、课程知识库、生成资源、学习任务和相关后台记录。此操作不能撤销。</p>
              <label className="mt-4 block text-sm font-semibold text-red-900">
                输入课程名称“{course.title}”确认
                <input value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} className="mt-2 w-full rounded-xl border border-red-300 bg-white px-4 py-3 outline-none" aria-label="输入课程名称确认删除" />
              </label>
              <button type="button" disabled={deleting || deleteConfirmation !== course.title} onClick={() => void handleDeleteCourse()} className="mt-4 rounded-xl bg-red-700 px-5 py-3 text-sm font-bold text-white disabled:opacity-40">
                {deleting ? "正在删除课程…" : "永久删除课程"}
              </button>
            </GlassPanel>
          ) : null}
        </div>
      </main>
    </AppSurface>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-(--app-text)">
        {label}
      </span>
      {children}
    </label>
  );
}

function ReadOnlyValue({
  label,
  value,
  wide = false,
}: {
  label: string;
  value: string;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <dt className="text-xs font-bold uppercase tracking-[0.16em] text-(--muted-text)">
        {label}
      </dt>
      <dd className="mt-2 whitespace-pre-wrap text-sm leading-7 text-(--app-text)">
        {value}
      </dd>
    </div>
  );
}

function CoverPreview({ src }: { src: string }) {
  return (
    <div className="aspect-16/7 overflow-hidden rounded-[24px] border border-(--shell-border) bg-(--surface-subtle)">
      {src ? (
        <img src={src} alt="课程封面" className="h-full w-full object-cover" />
      ) : (
        <div className="grid h-full place-items-center text-sm text-(--muted-text)">
          暂无课程封面
        </div>
      )}
    </div>
  );
}

function CourseStateCard({ message }: { message: string }) {
  return (
    <AppSurface className="min-h-screen p-8">
      <GlassPanel className="border border-(--shell-border) bg-white/90 p-8 text-sm text-(--muted-text)">
        {message}
      </GlassPanel>
    </AppSurface>
  );
}
