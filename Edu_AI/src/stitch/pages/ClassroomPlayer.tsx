import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ClassroomSceneRenderer } from "../../openmaic/ClassroomSceneRenderer";
import { ClassroomVideoExportButton } from "../../openmaic/ClassroomVideoExportButton";
import {
  getClassroomScenePresentation,
  type ClassroomScenePresentation,
} from "../../openmaic/classroomScene";
import {
  createRendererManagedPagePlaybackController,
  ManagedPagePlaybackController,
  type PagePlaybackSnapshot,
} from "../../openmaic/pagePlaybackController";
import { PptxExportButton } from "../../openmaic/PptxExportButton";
import type { PptxExportScene } from "../../openmaic/pptxExporter";
import { getClassroom } from "../api/classroom";
import type { ClassroomMaterial, ClassroomScene } from "../api/types";
import { AppSurface, MaterialIcon } from "../shared";
import { buildTeacherCourseHash } from "../teacherRoutes";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { canCourse } from "../course/coursePermissions";
import { ClassroomQaPanel } from "../classroomQa/ClassroomQaPanel";
import { useClassroomInterruption } from "../classroomQa/useClassroomInterruption";

function getQueryParams(): { courseId: string | null; classroomId: string | null } {
  const query = window.location.hash.split("?")[1] ?? "";
  const params = new URLSearchParams(query);
  return {
    courseId: params.get("course_id"),
    classroomId: params.get("classroom_id"),
  };
}

const INITIAL_PLAYBACK: PagePlaybackSnapshot = {
  sceneIndex: -1,
  status: "idle",
  revision: 0,
};

function playbackLabel(
  presentation: ClassroomScenePresentation | undefined,
  snapshot: PagePlaybackSnapshot,
): string {
  if (!presentation?.hasPlayback) return "当前页无讲解";
  if (snapshot.status === "interrupted") return "问答中";
  if (snapshot.status === "playing") return "暂停";
  if (snapshot.status === "completed") return "重播当前页";
  if (snapshot.status === "paused") return "重新播放当前页";
  return "播放当前页";
}

export function ClassroomPlayerPage() {
  const { courseId, classroomId } = useMemo(getQueryParams, []);
  const { courseRole } = useCourseRoute();
  const canGenerate = canCourse(courseRole, "generate");
  const [material, setMaterial] = useState<ClassroomMaterial | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadToken, setLoadToken] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [playback, setPlayback] =
    useState<PagePlaybackSnapshot>(INITIAL_PLAYBACK);
  const [presentationMode, setPresentationMode] = useState(false);
  const [subtitlesVisible, setSubtitlesVisible] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const consoleRef = useRef<HTMLElement | null>(null);
  const controllerRef = useRef<ManagedPagePlaybackController | null>(null);

  if (!controllerRef.current) {
    controllerRef.current =
      createRendererManagedPagePlaybackController(setPlayback);
  }
  const controller = controllerRef.current;
  const qaController = useClassroomInterruption({
    courseId: courseId ?? "",
    classroomId: classroomId ?? "",
    playback: controller,
    pageRevision: playback.revision,
    enabled: Boolean(courseId && classroomId && material),
  });
  const qaLocksPlayback = playback.status === "interrupted";

  useEffect(() => {
    if (!courseId || !classroomId) {
      setError("缺少课程或课堂信息，请从 AI 课堂列表重新进入。");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getClassroom(courseId, classroomId)
      .then((data) => {
        if (!cancelled) setMaterial(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "课堂加载失败");
          setMaterial(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [classroomId, courseId, loadToken]);

  const scenes: ClassroomScene[] = useMemo(() => material?.scenes ?? [], [material]);
  const scenePresentations = useMemo(
    () => scenes.map(getClassroomScenePresentation),
    [scenes],
  );
  const exportScenes = useMemo(
    () =>
      scenes.map((scene, order) => ({
        ...scene,
        order,
      })) as unknown as PptxExportScene[],
    [scenes],
  );

  useEffect(() => {
    if (scenes.length > 0) void controller.enter(0);
    else controller.leave();
  }, [controller, scenes]);

  useEffect(() => () => controller.leave(), [controller]);

  useEffect(() => {
    const onFullscreenChange = () => {
      const active = document.fullscreenElement === consoleRef.current;
      setFullscreen(active);
      if (!active) setPresentationMode(false);
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  const currentIndex = playback.sceneIndex;
  const currentScene = currentIndex >= 0 ? scenes[currentIndex] : undefined;
  const currentPresentation =
    currentIndex >= 0 ? scenePresentations[currentIndex] : undefined;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target?.isContentEditable ||
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT"
      ) {
        return;
      }
      if (qaLocksPlayback) return;
      if (event.key === "ArrowLeft" && currentIndex > 0) {
        event.preventDefault();
        void controller.enter(currentIndex - 1);
      }
      if (event.key === "ArrowRight" && currentIndex < scenes.length - 1) {
        event.preventDefault();
        void controller.enter(currentIndex + 1);
      }
      if (event.key === " " && currentPresentation?.hasPlayback) {
        event.preventDefault();
        if (playback.status === "playing") controller.pause();
        else if (playback.status === "completed") void controller.replay();
        else void controller.play();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    controller,
    currentIndex,
    currentPresentation?.hasPlayback,
    playback.status,
    qaLocksPlayback,
    scenes.length,
  ]);

  const goTo = (nextIndex: number) => {
    if (
      qaLocksPlayback ||
      nextIndex < 0 ||
      nextIndex >= scenes.length ||
      nextIndex === currentIndex
    ) return;
    void controller.enter(nextIndex);
  };

  const togglePlayback = () => {
    if (qaLocksPlayback || !currentPresentation?.hasPlayback) return;
    if (playback.status === "playing") controller.pause();
    else if (playback.status === "completed") void controller.replay();
    else void controller.play();
  };

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await consoleRef.current?.requestFullscreen();
    } catch {
      setFullscreen(false);
    }
  };

  const enterPresentation = async () => {
    setPresentationMode(true);
    try {
      await consoleRef.current?.requestFullscreen();
    } catch {
      // Presentation layout remains useful when fullscreen permission is unavailable.
    }
  };

  return (
    <AppSurface className="min-h-screen">
      <main
        ref={consoleRef}
        className={`classroom-console ${presentationMode ? "is-presenting" : ""}`}
      >
        <header className="classroom-console__header">
          <div className="flex min-w-0 items-center gap-3">
            <a
              href={buildTeacherCourseHash("classroom-studio", courseId)}
              className="classroom-icon-button"
              aria-label="返回 AI 课堂列表"
              title="返回 AI 课堂列表"
            >
              <MaterialIcon name="arrow_back" />
            </a>
            <div className="min-w-0">
              <p className="classroom-console__eyebrow">AI 课堂</p>
              <h1 className="truncate text-lg font-black text-(--app-text)">
                {material?.title || "课堂预览"}
              </h1>
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            {material && !presentationMode ? (
              <button
                type="button"
                className="classroom-secondary-toggle classroom-icon-button"
                aria-label="打开课堂目录"
                aria-expanded={catalogOpen}
                onClick={() => setCatalogOpen((value) => !value)}
              >
                <span>目录</span>
              </button>
            ) : null}
            {material && !presentationMode ? (
              <>
                {courseId && classroomId && canGenerate ? (
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
              </>
            ) : null}
            {material ? (
              <button
                type="button"
                onClick={
                  presentationMode
                    ? async () => {
                        if (document.fullscreenElement) await document.exitFullscreen();
                        else setPresentationMode(false);
                      }
                    : enterPresentation
                }
                className="classroom-primary-button"
              >
                <MaterialIcon name={presentationMode ? "close_fullscreen" : "present_to_all"} />
                {presentationMode ? "退出演示" : "进入演示"}
              </button>
            ) : null}
          </div>
        </header>

        {loading ? (
          <ClassroomState
            icon="hourglass_top"
            title="正在准备课堂"
            detail="正在加载课件页面与互动内容…"
          />
        ) : error ? (
          <ClassroomState
            icon="error_outline"
            title="课堂加载失败"
            detail={error}
            action={
              courseId && classroomId ? (
                <button
                  type="button"
                  onClick={() => setLoadToken((value) => value + 1)}
                  className="classroom-primary-button"
                >
                  <MaterialIcon name="refresh" />
                  重新加载
                </button>
              ) : undefined
            }
          />
        ) : !material || scenes.length === 0 ? (
          <ClassroomState
            icon="view_carousel"
            title="这份课堂还没有可播放页面"
            detail="请返回生成列表重新生成，或检查课堂内容是否完整。"
          />
        ) : (
          <>
            <div className="classroom-console__workspace">
              {!presentationMode ? (
                <aside className={`classroom-console__catalog ${catalogOpen ? "is-open" : ""}`} aria-label="课堂页面目录">
                  <div className="classroom-panel-heading">
                    <div>
                      <p className="font-bold text-(--app-text)">课堂目录</p>
                      <p className="mt-0.5 text-xs text-(--muted-text)">
                        共 {scenes.length} 页
                      </p>
                    </div>
                  </div>
                  <nav className="classroom-scene-list">
                    {scenePresentations.map((item, index) => (
                      <button
                        key={scenes[index].id}
                        type="button"
                        onClick={() => goTo(index)}
                        className={`classroom-scene-item ${
                          index === currentIndex ? "is-active" : ""
                        }`}
                        aria-current={index === currentIndex ? "page" : undefined}
                      >
                        <span className="classroom-scene-item__number">{index + 1}</span>
                        <span className="min-w-0">
                          <span className="block truncate font-semibold">{item.title}</span>
                          <span className="mt-0.5 block text-xs opacity-65">
                            {item.kindLabel}
                          </span>
                        </span>
                        {item.hasPlayback ? (
                          <MaterialIcon name="graphic_eq" className="ml-auto shrink-0 text-sm" />
                        ) : null}
                      </button>
                    ))}
                  </nav>
                </aside>
              ) : null}

              <section className="classroom-console__stage-column" aria-label="课堂舞台">
                <div className="classroom-stage-shell">
                  {currentScene && courseId && classroomId ? (
                    <ClassroomSceneRenderer
                      key={`${currentScene.id}:${playback.revision}`}
                      scene={currentScene}
                      courseId={courseId}
                      classroomId={classroomId}
                      autoPlay={playback.status === "playing"}
                      onComplete={() =>
                        controller.complete(currentIndex, playback.revision)
                      }
                      onRuntimeReady={(runtime) => {
                        if (runtime) {
                          controller.bindRuntime(
                            currentIndex,
                            playback.revision,
                            runtime,
                          );
                        }
                      }}
                    />
                  ) : null}
                  {subtitlesVisible &&
                  currentPresentation?.narration.length &&
                  playback.status === "playing" ? (
                    <div className="classroom-subtitle" aria-live="polite">
                      {currentPresentation.narration.join(" ")}
                    </div>
                  ) : null}
                </div>
              </section>

              <ClassroomQaPanel
                controller={qaController}
                canAsk={
                  playback.status === "playing" &&
                  Boolean(currentPresentation?.hasPlayback)
                }
              />
            </div>

            <footer className="classroom-console__controls" data-testid="classroom-core-controls">
              <button
                type="button"
                onClick={() => goTo(currentIndex - 1)}
                disabled={qaLocksPlayback || currentIndex <= 0}
                className="classroom-control-button"
              >
                <MaterialIcon name="skip_previous" />
                <span className="classroom-control-label">上一页</span>
              </button>
              <button
                type="button"
                onClick={togglePlayback}
                disabled={qaLocksPlayback || !currentPresentation?.hasPlayback}
                className="classroom-play-button"
              >
                <MaterialIcon
                  name={
                    playback.status === "playing"
                      ? "pause"
                      : playback.status === "completed"
                        ? "replay"
                        : "play_arrow"
                  }
                />
                {playbackLabel(currentPresentation, playback)}
              </button>
              <span className="classroom-current-scene" title={currentPresentation?.title}>
                {currentPresentation?.title || `第 ${currentIndex + 1} 页`}
              </span>
              <button
                type="button"
                onClick={() => setSubtitlesVisible((value) => !value)}
                className={`classroom-control-button ${
                  subtitlesVisible ? "is-active" : ""
                }`}
                aria-pressed={subtitlesVisible}
              >
                <MaterialIcon name="subtitles" />
                <span className="classroom-control-label">字幕</span>
              </button>
              <span className="classroom-page-count">
                {currentIndex + 1} / {scenes.length}
              </span>
              <span className="classroom-voice-status" aria-label="语音状态">
                <MaterialIcon name={material.voice_status === "disabled" ? "volume_off" : "volume_up"} />
                {material.voice_status === "disabled" ? "语音关闭" : "语音可用"}
              </span>
              <button
                type="button"
                onClick={toggleFullscreen}
                className="classroom-control-button"
              >
                <MaterialIcon name={fullscreen ? "fullscreen_exit" : "fullscreen"} />
                <span className="classroom-control-label">
                  {fullscreen ? "退出全屏" : "全屏"}
                </span>
              </button>
              <button
                type="button"
                onClick={() => goTo(currentIndex + 1)}
                disabled={qaLocksPlayback || currentIndex >= scenes.length - 1}
                className="classroom-control-button"
              >
                <span className="classroom-control-label">下一页</span>
                <MaterialIcon name="skip_next" />
              </button>
            </footer>
          </>
        )}
      </main>
    </AppSurface>
  );
}

function ClassroomState({
  icon,
  title,
  detail,
  action,
}: {
  icon: string;
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <section className="classroom-console__state" role="status">
      <span className="classroom-state-icon">
        <MaterialIcon name={icon} />
      </span>
      <h2 className="mt-5 text-xl font-black text-(--app-text)">{title}</h2>
      <p className="mt-2 max-w-lg text-center text-sm leading-6 text-(--muted-text)">
        {detail}
      </p>
      {action ? <div className="mt-5">{action}</div> : null}
    </section>
  );
}
