import { useEffect, useMemo, useState } from "react";

import { API_BASE_URL } from "../api/client";
import { courseMaterialToMarkdown, getCourseMaterials } from "../api/courses";
import { getAiLecturerVideoUrl } from "../api/video";
import type { CourseMaterial } from "../api/types";
import { MarkdownPreview } from "../components/MarkdownPreview";
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

const typeLabels: Record<string, string> = {
  ai_lecture_session: "AI lecture session",
  blog: "Blog",
  lesson_plan: "Lesson plan",
  ppt: "PPT",
  quiz: "Quiz",
  report: "Report",
};

function materialContent(material: CourseMaterial | null) {
  const content = (material as { content?: unknown } | null)?.content;
  return content && typeof content === "object" ? (content as Record<string, unknown>) : {};
}

function materialGenerationState(material: CourseMaterial | null) {
  const state = (material as { generation_state?: unknown } | null)?.generation_state;
  return state && typeof state === "object" ? (state as Record<string, unknown>) : {};
}

function playbackUrl(url: string) {
  if (!url) return "";
  if (/^https?:\/\//.test(url)) return url;
  if (url.startsWith("/api/")) return `${API_BASE_URL}${url}`;
  return getAiLecturerVideoUrl(url);
}

export function CourseResourcesPage() {
  const { selectedCourse } = useAppShell();
  const course = selectedCourse ?? defaultCourse;
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setLoading(true);
        setError(null);
        const data = await getCourseMaterials(course.id);
        const preferredId = window.localStorage.getItem("stitch-ai-lecture-session-id");
        window.localStorage.removeItem("stitch-ai-lecture-session-id");
        if (!cancelled) {
          setMaterials(data);
          setActiveId(
            preferredId && data.some((item) => item.material_id === preferredId)
              ? preferredId
              : data[0]?.material_id ?? null,
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load course resources.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [course.id]);

  const grouped = useMemo(() => {
    return materials.reduce<Record<string, CourseMaterial[]>>((acc, item) => {
      const key = item.material_type || "other";
      acc[key] = acc[key] || [];
      acc[key].push(item);
      return acc;
    }, {});
  }, [materials]);

  const activeMaterial = materials.find((item) => item.material_id === activeId) ?? materials[0] ?? null;
  const activeContent = materialContent(activeMaterial);
  const activeState = materialGenerationState(activeMaterial);
  const recordingUrl = String(activeContent.recording_url || "");
  const canContinueInteractive = Boolean(activeContent.can_continue_interactive);
  const isAiLectureSession = activeMaterial?.material_type === "ai_lecture_session";
  const markdown = activeMaterial ? courseMaterialToMarkdown(activeMaterial) : "";

  function openInAiLecturer() {
    if (activeMaterial?.material_id) {
      window.localStorage.setItem("stitch-ai-lecture-session-id", activeMaterial.material_id);
    }
    window.location.hash = routeHref(routes.video);
  }

  return (
    <AppSurface className="flex min-h-screen">
      <SidebarDock className="h-screen gap-3 bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="mb-2 px-2 py-4">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-[var(--accent-strong)]">{course.title}</h1>
          <p className="mt-1 text-sm text-[var(--muted-text)]">Course resources</p>
        </div>
        <SidebarNav activeRoute={routes.resources} />
        <div className="rounded-[24px] bg-[var(--accent-soft)] p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">Resource summary</p>
          <div className="mt-3 space-y-2 text-sm text-[var(--accent-strong)]">
            <div className="flex items-center justify-between rounded-2xl bg-white px-4 py-3">
              <span>Total</span>
              <span className="font-bold">{materials.length}</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border border-[var(--shell-border)] px-4 py-3">
              <span>AI sessions</span>
              <span className="font-bold">{grouped.ai_lecture_session?.length || 0}</span>
            </div>
          </div>
        </div>
      </SidebarDock>

      <main className="flex flex-1 flex-col">
        <header className="sticky top-0 z-40 border-b border-[var(--shell-border)] bg-[var(--app-bg)]/88 px-6 py-4 backdrop-blur-xl sm:px-8">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--accent-strong)]">{course.module}</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-[var(--accent-strong)] sm:text-4xl">Course Resources</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted-text)]">
            Generated teaching assets live here. AI lecture sessions show their saved classroom recording when available.
          </p>
        </header>

        <div className="grid flex-1 gap-6 p-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <section className="space-y-4">
            {loading ? (
              <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-6 text-sm text-[var(--muted-text)]">Loading resources...</GlassPanel>
            ) : error ? (
              <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-6 text-sm text-rose-600">{error}</GlassPanel>
            ) : materials.length === 0 ? (
              <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-6 text-sm text-[var(--muted-text)]">No generated resources yet.</GlassPanel>
            ) : (
              Object.entries(grouped).map(([type, items]) => (
                <GlassPanel key={type} className="border border-[var(--shell-border)] bg-white/90 p-5">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">{type}</p>
                      <h3 className="mt-2 text-xl font-black text-[var(--accent-strong)]">{typeLabels[type] || type}</h3>
                    </div>
                    <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-xs font-bold text-[var(--accent-strong)]">
                      {items.length}
                    </span>
                  </div>
                  <div className="space-y-3">
                    {items.map((item) => {
                      const active = item.material_id === activeMaterial?.material_id;
                      const itemContent = materialContent(item);
                      const itemRecordingUrl = String(itemContent.recording_url || "");
                      return (
                        <button
                          key={item.material_id}
                          type="button"
                          onClick={() => setActiveId(item.material_id)}
                          className={`w-full rounded-[22px] border px-4 py-4 text-left transition ${
                            active
                              ? "border-[var(--accent-border)] bg-[var(--accent-soft)]"
                              : "border-[var(--shell-border)] bg-[var(--surface-subtle)] hover:border-[var(--accent-border)] hover:bg-white"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <h4 className="truncate text-sm font-bold text-[var(--app-text)]">
                                {item.title || item.topic || item.material_id}
                              </h4>
                              <p className="mt-2 line-clamp-2 text-sm text-[var(--muted-text)]">
                                {item.summary || (item.material_type === "ai_lecture_session" ? "Realtime AI lecture session" : "Generated course material")}
                              </p>
                              {item.material_type === "ai_lecture_session" ? (
                                <p className="mt-3 text-xs font-bold text-[var(--accent-strong)]">
                                  {itemRecordingUrl ? "Recording ready" : "Interactive session"}
                                </p>
                              ) : null}
                            </div>
                            {item.is_pinned ? (
                              <span className="rounded-full bg-white px-3 py-1 text-[10px] font-bold text-[var(--accent-strong)]">Pinned</span>
                            ) : null}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </GlassPanel>
              ))
            )}
          </section>

          <section className="min-w-0">
            <GlassPanel className="h-full border border-[var(--shell-border)] bg-white/90 p-6">
              {activeMaterial ? (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--shell-border)] pb-4">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">
                        {typeLabels[activeMaterial.material_type] || activeMaterial.material_type}
                      </p>
                      <h2 className="mt-2 text-3xl font-black text-[var(--accent-strong)]">
                        {activeMaterial.title || activeMaterial.topic || activeMaterial.material_id}
                      </h2>
                    </div>
                    <button
                      type="button"
                      onClick={openInAiLecturer}
                      className="inline-flex items-center gap-2 rounded-full bg-[var(--accent)] px-5 py-3 text-sm font-bold text-white"
                    >
                      <MaterialIcon name="play_circle" className="text-base" />
                      {isAiLectureSession ? "Open AI lecturer" : "Open player"}
                    </button>
                  </div>

                  {isAiLectureSession ? (
                    <div className="mt-6 space-y-5">
                      {recordingUrl ? (
                        <video controls className="aspect-video w-full rounded-[24px] bg-black" src={playbackUrl(recordingUrl)} />
                      ) : (
                        <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-6 text-sm leading-7 text-[var(--muted-text)]">
                          This AI lecture session has no saved recording yet. Open the AI lecturer to continue the interactive class and save it.
                        </div>
                      )}
                      <div className="grid gap-3 text-sm text-[var(--muted-text)] sm:grid-cols-3">
                        <div className="rounded-[18px] bg-[var(--surface-subtle)] p-4">
                          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">Status</p>
                          <p className="mt-2">{String(activeState.status || "created")}</p>
                        </div>
                        <div className="rounded-[18px] bg-[var(--surface-subtle)] p-4">
                          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">Recording</p>
                          <p className="mt-2">{recordingUrl ? "Ready" : "Not saved"}</p>
                        </div>
                        <div className="rounded-[18px] bg-[var(--surface-subtle)] p-4">
                          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">Interactive</p>
                          <p className="mt-2">{canContinueInteractive ? "Can continue" : "View only"}</p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-6 max-h-[calc(100vh-220px)] overflow-y-auto pr-2">
                      <MarkdownPreview content={markdown} />
                    </div>
                  )}
                </>
              ) : (
                <div className="text-sm text-[var(--muted-text)]">Select a resource to preview it.</div>
              )}
            </GlassPanel>
          </section>
        </div>
      </main>
    </AppSurface>
  );
}
