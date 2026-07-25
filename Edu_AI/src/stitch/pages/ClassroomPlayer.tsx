import { useEffect, useMemo, useState } from "react";
import type { Slide } from "@openmaic/renderer";
import { getClassroom } from "../api/classroom";
import type { ClassroomMaterial, ClassroomScene } from "../api/types";
import { AppSurface, GlassPanel, MaterialIcon, routeHref, routes } from "../shared";
import { SlidePlayer } from "../../openmaic/SlidePlayer";
import { PptxExportButton } from "../../openmaic/PptxExportButton";
import type { PptxExportScene } from "../../openmaic/pptxExporter";
import { ClassroomVideoExportButton } from "../../openmaic/ClassroomVideoExportButton";

/**
 * 播放一份真实的、由 `classroom_service.generate_classroom_for_course` 生成
 * 并落库的课件（SPEC-04/ACC-08 AC-08-3）。逐 scene 播放，`slide` 类型走
 * SlidePlayer；其余类型（如 `interactive`）暂不支持播放，优雅降级不崩溃
 * （P3-1 范围边界，见 SPEC-08）。
 *
 * 通过 `#classroom-player?course_id=...&classroom_id=...` 到达——用 hash
 * query 而不是 `useAppShell().selectedCourse`，因为这里同时需要
 * course_id + classroom_id 两个值，单一课程 context 装不下。
 */

function getQueryParams(): { courseId: string | null; classroomId: string | null } {
  const query = window.location.hash.split("?")[1] ?? "";
  const params = new URLSearchParams(query);
  return { courseId: params.get("course_id"), classroomId: params.get("classroom_id") };
}

export function ClassroomPlayerPage() {
  const { courseId, classroomId } = useMemo(getQueryParams, []);
  const [material, setMaterial] = useState<ClassroomMaterial | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sceneIndex, setSceneIndex] = useState(0);

  useEffect(() => {
    if (!courseId || !classroomId) {
      setError("缺少 course_id / classroom_id，请从课程详情页的课件列表进入");
      return;
    }
    let cancelled = false;
    getClassroom(courseId, classroomId)
      .then((data) => {
        if (!cancelled) setMaterial(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "课件加载失败");
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, classroomId]);

  const scenes: ClassroomScene[] = useMemo(() => material?.scenes ?? [], [material]);
  const exportScenes = useMemo(
    () =>
      scenes.map((scene, order) => ({
        ...scene,
        order,
      })) as unknown as PptxExportScene[],
    [scenes],
  );
  const currentScene = scenes[sceneIndex];
  const slideCount = scenes.filter((s) => s.content?.type === "slide" && s.content.canvas).length;

  return (
    <AppSurface className="min-h-screen">
      <main className="w-full px-8 py-10">
        <div className="mb-8 flex items-center justify-between gap-4">
          <a
            href={courseId ? `${routeHref(routes.classroomStudio)}` : routeHref(routes.course)}
            className="inline-flex items-center gap-2 rounded-full border border-(--shell-border) bg-white px-4 py-2.5 text-sm font-semibold text-(--accent-strong)"
          >
            <MaterialIcon name="arrow_back" className="text-sm" />
            返回课件列表
          </a>
          <div className="flex items-center gap-5">
            {material ? (
              <div className="flex items-center gap-3">
                {courseId && classroomId ? (
                  <ClassroomVideoExportButton
                    courseId={courseId}
                    classroomId={classroomId}
                    title={material.title || "课堂视频"}
                  />
                ) : null}
                <PptxExportButton
                title={material.title || "课堂课件"}
                  scenes={exportScenes}
                />
              </div>
            ) : null}
            <div className="text-right">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-(--accent-strong)">课件播放</p>
              {material ? (
                <h2 className="mt-1 text-xl font-black text-(--app-text)">{material.title}</h2>
              ) : null}
            </div>
          </div>
        </div>

        {error ? (
          <GlassPanel className="border border-(--shell-border) bg-white/85 p-8 text-sm text-rose-600">
            {error}
          </GlassPanel>
        ) : !material ? (
          <GlassPanel className="border border-(--shell-border) bg-white/85 p-8 text-sm text-(--muted-text)">
            加载中...
          </GlassPanel>
        ) : (
          <GlassPanel className="border border-(--shell-border) bg-white/88 p-6">
            <p className="mb-4 text-sm text-(--muted-text)">
              共 {scenes.length} 个 scene（{slideCount} 个 slide 类型）—— 当前 scene {sceneIndex + 1}/
              {scenes.length}：{currentScene?.id}（type={currentScene?.type}）
            </p>

            {currentScene?.content?.type === "slide" && currentScene.content.canvas ? (
              <div className="mx-auto" style={{ width: 960, height: 540, border: "1px solid var(--shell-border)" }}>
                <SlidePlayer
                  key={currentScene.id}
                  slide={currentScene.content.canvas as unknown as Slide}
                  actions={currentScene.actions as never}
                  sceneId={currentScene.id}
                  onComplete={() => setSceneIndex((i) => Math.min(i + 1, scenes.length - 1))}
                />
              </div>
            ) : currentScene ? (
              <div
                className="mx-auto flex items-center justify-center rounded-2xl border border-(--shell-border) bg-(--surface-subtle) p-10 text-sm text-(--muted-text)"
                style={{ width: 960, height: 540 }}
              >
                scene 类型 "{currentScene.type}" 暂不支持播放（P3-1 只接了 slide 类型的渲染）
              </div>
            ) : null}

            <div className="mt-4 flex items-center justify-center gap-3">
              <button
                type="button"
                disabled={sceneIndex === 0}
                onClick={() => setSceneIndex((i) => Math.max(i - 1, 0))}
                className="rounded-full border border-(--shell-border) bg-white px-4 py-2 text-sm font-semibold text-(--accent-strong) disabled:opacity-40"
              >
                上一个
              </button>
              <button
                type="button"
                disabled={sceneIndex >= scenes.length - 1}
                onClick={() => setSceneIndex((i) => Math.min(i + 1, scenes.length - 1))}
                className="rounded-full border border-(--shell-border) bg-white px-4 py-2 text-sm font-semibold text-(--accent-strong) disabled:opacity-40"
              >
                下一个
              </button>
            </div>
          </GlassPanel>
        )}
      </main>
    </AppSurface>
  );
}
