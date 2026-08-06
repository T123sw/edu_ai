import { useEffect, useRef, useState, type ReactNode } from "react";

import { updateCourse } from "../api/courses";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { canCourse } from "../course/coursePermissions";
import {
  AppSurface,
  GlassPanel,
  MaterialIcon,
  SidebarBackLink,
  SidebarDock,
  SidebarNav,
  routes,
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
  const canEdit = canCourse(courseRole, "edit");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [formState, setFormState] = useState<CourseFormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

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
    if (!course || !canEdit || !formState.title.trim()) return;
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
      setFeedback("课程信息已保存，其他协作教师刷新后可立即看到更新。");
    } catch (reason) {
      const status =
        typeof reason === "object" && reason !== null && "status" in reason
          ? Number(reason.status)
          : 0;
      if (status === 409) {
        await reload();
        setFeedback("课程刚刚被其他教师更新，已载入最新版本，请确认后重新保存。");
      } else {
        setFeedback(reason instanceof Error ? reason.message : "保存失败");
      }
    } finally {
      setSaving(false);
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
    <AppSurface className="flex min-h-screen">
      <SidebarDock className="h-screen gap-3 bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="mb-2 px-2 py-4">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-(--accent-strong)">
            {course.title}
          </h1>
          <p className="mt-1 text-sm text-(--muted-text)">
            {canEdit ? "课程设置" : "课程信息"}
          </p>
        </div>
        <SidebarNav activeRoute={routes.edit} />
      </SidebarDock>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 border-b border-(--shell-border) bg-(--app-bg)/88 px-6 py-4 backdrop-blur-xl sm:px-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-(--accent)">
                {canEdit ? "Course settings" : "Read only"}
              </p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-(--accent-strong)">
                {course.title}
              </h1>
            </div>
            {canEdit ? (
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving || uploadingImage}
                className="inline-flex items-center gap-2 rounded-full bg-(--accent) px-5 py-2.5 text-sm font-bold text-white disabled:opacity-60"
              >
                <MaterialIcon name="check_circle" className="text-sm" />
                {saving ? "保存中…" : "保存更改"}
              </button>
            ) : null}
          </div>
        </header>

        <div className="flex-1 p-6 sm:p-8">
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

          <GlassPanel className="border border-(--shell-border) bg-white/90 p-6 sm:p-7">
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
