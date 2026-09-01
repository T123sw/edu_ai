import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ClassroomSceneRenderer } from "../../../openmaic/ClassroomSceneRenderer";
import { ResourceLearningTracker } from "../../../openmaic/resourceLearningTracker";
import type { QuizAnswers } from "../../../openmaic/quizScene";
import { ClassroomVideoExportButton } from "../../../openmaic/ClassroomVideoExportButton";
import {
  getClassroomScenePresentation,
  type ClassroomScenePresentation,
} from "../../../openmaic/classroomScene";
import {
  createRendererManagedPagePlaybackController,
  ManagedPagePlaybackController,
  type PagePlaybackSnapshot,
} from "../../../openmaic/pagePlaybackController";
import { PptxExportButton } from "../../../openmaic/PptxExportButton";
import type { PptxExportScene } from "../../../openmaic/pptxExporter";
import { getClassroom } from "../../api/classroom";
import {
  endResourceLearningSession,
  getMyResourceLearningProgress,
  sendResourceLearningEvents,
  startResourceLearningSession,
  submitResourceQuestions,
} from "../../api/resourceLearning";
import type {
  ClassroomMaterial,
  ClassroomScene,
  ResourceLearningProgress as ResourceLearningProgressRecord,
} from "../../api/types";
import { useAuthSession } from "../../authSession";
import { MaterialIcon } from "../../shared";
import { useCourseRoute } from "../CourseRouteProvider";
import { canCourse } from "../coursePermissions";
import { completeAndAdvance } from "../../classroomQa/classroomAutoplay";
import { useClassroomInterruption } from "../../classroomQa/useClassroomInterruption";
import { shouldTrackResourceLearning } from "../../pages/classroomResourceLearning";
import type { WorkspaceQaRegistration } from "./workspaceQaBinding";

export type ClassroomQaBinding = WorkspaceQaRegistration & {
  kind: "classroom" | "personal_classroom";
  version: number | null;
};

export type ClassroomPlaybackSurfaceProps = {
  courseId: string;
  classroomId: string;
  resourceVersion?: number;
  mode: "manage" | "learn";
  catalogNodeId?: string | null;
  catalogResourceId?: string | null;
  kind?: "classroom" | "personal_classroom";
  qaTargetKey?: string;
  onQaControllerChange?: (targetKey: string, binding: ClassroomQaBinding | null) => void;
};

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

function newIdempotencyKey(sceneId: string): string {
  const random = globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
  return `classroom-quiz-${sceneId}-${random}`;
}

export function ClassroomPlaybackSurface({
  courseId,
  classroomId,
  resourceVersion,
  mode,
  kind = "classroom",
  qaTargetKey,
  onQaControllerChange,
}: ClassroomPlaybackSurfaceProps) {
  const { user } = useAuthSession();
  const { courseRole } = useCourseRoute();
  const canGenerate = mode === "manage" && canCourse(courseRole, "generate");
  const tracksResourceLearning = shouldTrackResourceLearning({
    role: user?.role,
    courseRole,
    resourceVersion,
  });
  const [material, setMaterial] = useState<ClassroomMaterial | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadToken, setLoadToken] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [playback, setPlayback] =
    useState<PagePlaybackSnapshot>(INITIAL_PLAYBACK);
  const [fullscreen, setFullscreen] = useState(false);
  const consoleRef = useRef<HTMLElement | null>(null);
  const controllerRef = useRef<ManagedPagePlaybackController | null>(null);
  const learningTrackerRef = useRef<ResourceLearningTracker | null>(null);
  const learningAttemptRef = useRef(
    new Map<string, { fingerprint: string; idempotencyKey: string }>(),
  );
  const [learningSessionId, setLearningSessionId] = useState<string | null>(null);
  const [learningProgress, setLearningProgress] =
    useState<ResourceLearningProgressRecord | null>(null);
  const [, setLearningSyncState] = useState<
    "idle" | "syncing" | "synced" | "failed"
  >("idle");

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
    getClassroom(courseId, classroomId, resourceVersion ?? undefined)
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
  }, [classroomId, courseId, loadToken, resourceVersion]);

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
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  const currentIndex = playback.sceneIndex;
  const currentScene = currentIndex >= 0 ? scenes[currentIndex] : undefined;
  const currentPresentation =
    currentIndex >= 0 ? scenePresentations[currentIndex] : undefined;
  const canAsk = playback.status === "playing" && Boolean(currentPresentation?.hasPlayback);

  useEffect(() => {
    const targetKey = qaTargetKey ?? `${kind}:${classroomId}:v${resourceVersion ?? "none"}`;
    if (!material) {
      onQaControllerChange?.(targetKey, null);
      return;
    }
    onQaControllerChange?.(targetKey, {
      key: targetKey,
      controller: qaController,
      canAsk,
      title: material.title || "AI 课堂",
      kind,
      kindLabel: kind === "personal_classroom" ? "个人课堂" : "AI 课堂",
      scopeLabel: "已读取完整课堂",
      resourceId: classroomId,
      resourceVersion: material.version ?? resourceVersion ?? null,
      version: material.version ?? resourceVersion ?? null,
    });
    return () => onQaControllerChange?.(targetKey, null);
  }, [canAsk, classroomId, kind, material, onQaControllerChange, qaController, qaTargetKey, resourceVersion]);
  const learningManifestScene = useMemo(
    () =>
      learningProgress?.manifest?.scenes.find(
        (scene) => scene.scene_id === currentScene?.id,
      ),
    [currentScene?.id, learningProgress?.manifest],
  );
  const currentLearningSceneId = currentScene?.id;
  const currentLearningSceneKind = learningManifestScene?.kind;
  const currentLearningSceneDuration = learningManifestScene?.expected_duration_ms;

  useEffect(() => {
    if (
      !tracksResourceLearning ||
      !courseId ||
      !classroomId ||
      !resourceVersion ||
      material?.version !== resourceVersion
    ) {
      return;
    }

    let cancelled = false;
    let tracker: ResourceLearningTracker | null = null;
    let startedSessionId: string | null = null;
    let flushTimer: number | undefined;

    void (async () => {
      try {
        setLearningSyncState("syncing");
        const session = await startResourceLearningSession(
          courseId,
          classroomId,
          resourceVersion,
        );
        startedSessionId = session.session_id;
        if (cancelled) {
          await endResourceLearningSession(
            courseId,
            classroomId,
            resourceVersion,
            session.session_id,
          );
          return;
        }

        const initialProgress = await getMyResourceLearningProgress(
          courseId,
          classroomId,
          resourceVersion,
        );
        if (cancelled) {
          await endResourceLearningSession(
            courseId,
            classroomId,
            resourceVersion,
            session.session_id,
          );
          return;
        }

        tracker = new ResourceLearningTracker({
          outboxKey: `${courseId}:${classroomId}:${resourceVersion}:${session.session_id}`,
          send: async (events) => {
            if (!cancelled) setLearningSyncState("syncing");
            try {
              const progress = await sendResourceLearningEvents(
                courseId,
                classroomId,
                resourceVersion,
                session.session_id,
                events,
              );
              if (!cancelled) {
                setLearningProgress(progress);
                setLearningSyncState("synced");
              }
              return progress;
            } catch (error) {
              if (!cancelled) setLearningSyncState("failed");
              throw error;
            }
          },
        });
        learningTrackerRef.current = tracker;
        setLearningProgress(initialProgress);
        setLearningSessionId(session.session_id);
        setLearningSyncState("synced");
        flushTimer = window.setInterval(() => {
          void tracker?.flush().catch(() => undefined);
        }, tracker.heartbeatMs);
      } catch {
        if (!cancelled) setLearningSyncState("failed");
        if (startedSessionId) {
          void endResourceLearningSession(
            courseId,
            classroomId,
            resourceVersion,
            startedSessionId,
          ).catch(() => undefined);
        }
      }
    })();

    return () => {
      cancelled = true;
      if (flushTimer !== undefined) window.clearInterval(flushTimer);
      if (learningTrackerRef.current === tracker) {
        learningTrackerRef.current = null;
      }
      setLearningSessionId(null);
      if (tracker && startedSessionId) {
        void tracker
          .dispose()
          .then(() =>
            endResourceLearningSession(
              courseId,
              classroomId,
              resourceVersion,
              startedSessionId!,
            ),
          )
          .catch(() => undefined);
      }
    };
  }, [
    classroomId,
    courseId,
    material?.content_hash,
    material?.version,
    resourceVersion,
    tracksResourceLearning,
  ]);

  useEffect(() => {
    const tracker = learningTrackerRef.current;
    if (!tracker || !learningSessionId || !currentLearningSceneId || !currentLearningSceneKind) {
      return;
    }
    if (currentLearningSceneKind === "explanation") {
      tracker.enterExplanation(
        currentLearningSceneId,
        currentLearningSceneDuration ?? 0,
      );
    } else if (currentLearningSceneKind === "exercise") {
      tracker.enterExercise(currentLearningSceneId);
    } else {
      tracker.enterDemo(currentLearningSceneId);
    }
  }, [
    currentLearningSceneDuration,
    currentLearningSceneId,
    currentLearningSceneKind,
    learningSessionId,
    playback.revision,
  ]);

  useEffect(() => {
    const tracker = learningTrackerRef.current;
    if (!tracker || !learningSessionId || !currentLearningSceneId) return;
    if (playback.status === "playing") {
      tracker.play();
      return;
    }
    if (playback.status === "interrupted") tracker.interrupt();
    else tracker.pause();
    void tracker.flush().catch(() => undefined);
  }, [currentLearningSceneId, learningSessionId, playback.status]);

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

  const submitCurrentQuiz = async (answers: QuizAnswers) => {
    if (
      !courseId ||
      !classroomId ||
      !resourceVersion ||
      !learningSessionId ||
      !currentScene ||
      learningManifestScene?.kind !== "exercise"
    ) {
      throw new Error("学习记录尚未就绪，请稍后重试");
    }
    const fingerprint = JSON.stringify(answers);
    const previousAttempt = learningAttemptRef.current.get(currentScene.id);
    const idempotencyKey =
      previousAttempt?.fingerprint === fingerprint
        ? previousAttempt.idempotencyKey
        : newIdempotencyKey(currentScene.id);
    learningAttemptRef.current.set(currentScene.id, {
      fingerprint,
      idempotencyKey,
    });
    setLearningSyncState("syncing");
    try {
      const progress = await submitResourceQuestions(
        courseId,
        classroomId,
        resourceVersion,
        idempotencyKey,
        answers,
      );
      learningAttemptRef.current.delete(currentScene.id);
      setLearningProgress(progress);
      setLearningSyncState("synced");
    } catch (error) {
      setLearningSyncState("failed");
      throw error;
    }
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

  return (
    <main
      ref={consoleRef}
      className="classroom-console classroom-playback-surface"
    >
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
              <section className="classroom-console__stage-column" aria-label="课堂舞台">
                <div className="classroom-stage-shell">
                  {currentScene && courseId && classroomId ? (
                    <ClassroomSceneRenderer
                      key={`${currentScene.id}:${playback.revision}`}
                      scene={currentScene}
                      courseId={courseId}
                      classroomId={classroomId}
                      autoPlay={playback.status === "playing"}
                      onComplete={() => {
                        learningTrackerRef.current?.completeScene();
                        void learningTrackerRef.current
                          ?.flush()
                          .catch(() => undefined);
                        void completeAndAdvance({
                          controller,
                          sceneIndex: currentIndex,
                          revision: playback.revision,
                          sceneCount: scenes.length,
                        });
                      }}
                      onQuizSubmitAnswers={
                        tracksResourceLearning ? submitCurrentQuiz : undefined
                      }
                      onDemoInteraction={(actionId) => {
                        learningTrackerRef.current?.demoInteracted(actionId);
                      }}
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
                  {currentPresentation?.narration.length &&
                  playback.status === "playing" ? (
                    <div className="classroom-subtitle" aria-live="polite">
                      {currentPresentation.narration.join(" ")}
                    </div>
                  ) : null}
                </div>
              </section>
            </div>

            <footer className="classroom-console__controls" data-testid="classroom-core-controls">
              <div className="classroom-console__export-controls">
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
              </div>
              <div className="classroom-console__playback-controls">
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
                <span className="classroom-page-count">
                  {currentIndex + 1} / {scenes.length}
                </span>
                <button
                  type="button"
                  onClick={() => goTo(currentIndex + 1)}
                  disabled={qaLocksPlayback || currentIndex >= scenes.length - 1}
                  className="classroom-control-button"
                >
                  <span className="classroom-control-label">下一页</span>
                  <MaterialIcon name="skip_next" />
                </button>
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
              </div>
            </footer>
          </>
        )}
    </main>
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
