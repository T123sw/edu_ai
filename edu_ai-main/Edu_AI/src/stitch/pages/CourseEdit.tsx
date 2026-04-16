import { useEffect, useMemo, useState } from "react";
import {
  AppSurface,
  GlassPanel,
  MaterialIcon,
  SidebarBackLink,
  SidebarDock,
  SidebarNav,
  defaultCourse,
  routeHref,
  routes,
  useAppShell,
} from "../shared";
import { useCourseStore } from "../../store/course/useCourseStore";

type CourseFormState = {
  title: string;
  description: string;
  objectives: string;
  knowledgeGraph: string;
};

export function CourseEditPage() {
  const { selectedCourse } = useAppShell();
  const shellCourse = selectedCourse ?? defaultCourse;
  const { courses, loadCoursesFromBackend, updateCourse } = useCourseStore();

  const [saving, setSaving] = useState(false);
  const [formState, setFormState] = useState<CourseFormState>({
    title: "",
    description: "",
    objectives: "",
    knowledgeGraph: "",
  });

  useEffect(() => {
    if (!courses.length) {
      void loadCoursesFromBackend();
    }
  }, [courses.length, loadCoursesFromBackend]);

  const course = useMemo(() => {
    return (
      courses.find((item) => item.id === shellCourse.id) ?? {
        id: shellCourse.id,
        title: shellCourse.title,
        description: shellCourse.summary,
        icon: "book",
        color: shellCourse.accent,
        objectives: [],
        knowledgeGraph: "",
        masterKnowledgeBase: [],
      }
    );
  }, [courses, shellCourse]);

  useEffect(() => {
    setFormState({
      title: course.title || "",
      description: course.description || "",
      objectives: Array.isArray(course.objectives) ? course.objectives.join("\n") : "",
      knowledgeGraph: course.knowledgeGraph || "",
    });
  }, [course]);
  const updateField = (field: keyof CourseFormState, value: string) => {
    setFormState((current) => ({ ...current, [field]: value }));
  };

  const handleSave = async () => {
    if (!formState.title.trim()) {
      return;
    }

    setSaving(true);
    try {
      await updateCourse(course.id, {
        title: formState.title.trim(),
        description: formState.description.trim(),
        objectives: formState.objectives
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        knowledgeGraph: formState.knowledgeGraph.trim(),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppSurface className="flex min-h-screen">
      <SidebarDock className="h-screen gap-3 bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="mb-2 px-2 py-4">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-[var(--accent-strong)]">{course.title}</h1>
          <p className="mt-1 text-sm text-[var(--muted-text)]">详情编辑</p>
        </div>
        <SidebarNav activeRoute={routes.edit} />
      </SidebarDock>

      <main className="flex flex-1 flex-col">
        <header className="sticky top-0 z-40 border-b border-[var(--shell-border)] bg-[var(--app-bg)]/88 px-6 py-4 backdrop-blur-xl sm:px-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--accent-strong)]">Course Edit</p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-[var(--accent-strong)] sm:text-4xl">
                {course.title}
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted-text)]">
                保留当前 stitch 页面视觉，只将编辑与知识库管理逻辑接入课程详情使用的课程接口。
              </p>
            </div>

            <div className="flex gap-3">
              <a
                href={routeHref(routes.course)}
                className="inline-flex items-center gap-2 rounded-full border border-[var(--shell-border)] bg-white px-4 py-2.5 text-sm font-semibold text-[var(--accent-strong)]"
              >
                <MaterialIcon name="arrow_back" className="text-sm" />
                返回课程详情
              </a>
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-full bg-[var(--accent)] px-5 py-2.5 text-sm font-bold text-white disabled:opacity-60"
              >
                <MaterialIcon name="check_circle" className="text-sm" />
                {saving ? "保存中..." : "保存更改"}
              </button>
            </div>
          </div>
        </header>

        <div className="flex-1 p-6 sm:p-8">
          <div className="mx-auto max-w-5xl">
            <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-6 sm:p-7">
              <div className="mb-6 flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">基本信息</p>
                  <h2 className="mt-2 text-2xl font-black text-[var(--accent-strong)]">课程内容编辑</h2>
                </div>
                <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[var(--accent-soft)] text-[var(--accent)]">
                  <MaterialIcon name="edit_note" className="text-xl" />
                </div>
              </div>

              <div className="space-y-5">
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-[var(--app-text)]">课程名称</span>
                  <input
                    value={formState.title}
                    onChange={(event) => updateField("title", event.target.value)}
                    className="w-full rounded-[20px] border border-[var(--shell-border)] bg-[var(--input-surface)] px-4 py-3 text-sm text-[var(--app-text)] outline-none"
                    placeholder="请输入课程名称"
                  />
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-[var(--app-text)]">课程简介</span>
                  <textarea
                    value={formState.description}
                    onChange={(event) => updateField("description", event.target.value)}
                    className="min-h-[112px] w-full rounded-[20px] border border-[var(--shell-border)] bg-[var(--input-surface)] px-4 py-3 text-sm leading-7 text-[var(--app-text)] outline-none"
                    placeholder="请输入课程简介"
                  />
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-[var(--app-text)]">教学目标</span>
                  <textarea
                    value={formState.objectives}
                    onChange={(event) => updateField("objectives", event.target.value)}
                    className="min-h-[160px] w-full rounded-[20px] border border-[var(--shell-border)] bg-[var(--input-surface)] px-4 py-3 text-sm leading-7 text-[var(--app-text)] outline-none"
                    placeholder={"请输入教学目标，每行一个\n例如：\n理解计算思维的核心概念和方法\n掌握问题分解和模式识别的技巧"}
                  />
                  <p className="mt-2 text-xs text-[var(--muted-text)]">每行一个教学目标，保存时会自动转换为数组。</p>
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-[var(--app-text)]">课程知识图谱</span>
                  <textarea
                    value={formState.knowledgeGraph}
                    onChange={(event) => updateField("knowledgeGraph", event.target.value)}
                    className="min-h-[180px] w-full rounded-[20px] border border-[var(--shell-border)] bg-[var(--input-surface)] px-4 py-3 text-sm leading-7 text-[var(--app-text)] outline-none"
                    placeholder="请输入课程知识图谱（JSON 格式）或 URL 链接"
                  />
                </label>
              </div>
            </GlassPanel>
          </div>
        </div>
      </main>
    </AppSurface>
  );
}
