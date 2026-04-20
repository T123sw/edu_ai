import { useEffect, useMemo, useRef, useState } from "react";

import { API_BASE_URL } from "../api/client";
import { courseMaterialToMarkdown, getCourseMaterials } from "../api/courses";
import {
  askAiLecturer,
  createAiLectureSession,
  createAiLecturerCourse,
  generateAiLecturerFullVideo,
  generateAiLecturerScript,
  getAiLectureSession,
  getAiLecturerDownloadUrl,
  getAiLecturerTaskStatus,
  getAiLecturerVideoUrl,
  patchAiLectureSessionSnapshot,
  speakAiLecturerSentence,
  startAiLectureSessionRecording,
  stopAiLectureSessionRecording,
  stopAiLecturerSpeaking,
} from "../api/video";
import { MarkdownPreview } from "../components/MarkdownPreview";
import { useAiLecturerWebRtc } from "../hooks/useAiLecturerWebRtc";
import type { CourseMaterial } from "../api/types";
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

type Slide = {
  title: string;
  content: string;
};

type AiLectureAutoStartRequest = {
  autoPlay?: boolean;
  courseId?: string;
  pptMaterialId?: string;
  pptTitle?: string;
  sessionId?: string;
};

const AI_LECTURE_AUTOSTART_REQUEST_KEY = "stitch-ai-lecture-autostart-request";
const AI_LECTURE_PREFERRED_SESSION_KEY = "stitch-ai-lecture-session-id";

function defaultMarkdown(courseTitle?: string) {
  return [
    `# ${courseTitle || "AI Lecture Course"}`,
    "",
    "## Overview",
    "- Explain the core concepts from the selected PPT.",
    "- Keep each slide concise and classroom friendly.",
    "",
    "## Interaction",
    "- Students can interrupt the AI lecturer at any time.",
    "- The realtime session can be recorded as a course resource.",
  ].join("\n");
}

function fileNameFromUrl(url: string) {
  const normalized = url.split("?")[0];
  return normalized.slice(normalized.lastIndexOf("/") + 1);
}

function playbackUrl(url: string) {
  if (!url) return "";
  if (/^https?:\/\//.test(url)) return url;
  if (url.startsWith("/api/")) return `${API_BASE_URL}${url}`;
  return getAiLecturerVideoUrl(url);
}

function materialContent(material: CourseMaterial | null) {
  const content = (material as { content?: unknown } | null)?.content;
  return content && typeof content === "object" ? (content as Record<string, unknown>) : {};
}

function materialGenerationState(material: CourseMaterial | null) {
  const state = (material as { generation_state?: unknown } | null)?.generation_state;
  return state && typeof state === "object" ? (state as Record<string, unknown>) : {};
}

function isPptMaterial(material: CourseMaterial) {
  return material.material_type === "ppt" || /\.pptx?$/i.test(material.title || "");
}

function readStoredJson<T>(key: string): T | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    window.localStorage.removeItem(key);
    return JSON.parse(raw) as T;
  } catch {
    window.localStorage.removeItem(key);
    return null;
  }
}

function readStoredString(key: string): string | null {
  if (typeof window === "undefined") return null;

  const raw = window.localStorage.getItem(key);
  if (!raw) return null;
  window.localStorage.removeItem(key);
  return raw;
}

export function VideoPlayerPage() {
  const { selectedCourse } = useAppShell();
  const course = selectedCourse ?? defaultCourse;
  const autoStartAttemptedRef = useRef(false);
  const [mode, setMode] = useState<"online" | "offline">("online");
  const [rawDocument, setRawDocument] = useState(defaultMarkdown(selectedCourse?.title));
  const [aiLecturerCourseId, setAiLecturerCourseId] = useState("");
  const [outline, setOutline] = useState<Slide[]>([]);
  const [activeSlideIndex, setActiveSlideIndex] = useState(0);
  const [scriptSentences, setScriptSentences] = useState<string[]>([]);
  const [currentSentence, setCurrentSentence] = useState("");
  const [studentQuestion, setStudentQuestion] = useState("");
  const [answerText, setAnswerText] = useState("");
  const [offlineTaskId, setOfflineTaskId] = useState("");
  const [offlineStatus, setOfflineStatus] = useState("");
  const [offlineVideoUrl, setOfflineVideoUrl] = useState("");
  const [offlineImageRoot, setOfflineImageRoot] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [materialsLoading, setMaterialsLoading] = useState(true);
  const [materialsError, setMaterialsError] = useState<string | null>(null);
  const [activeMaterialId, setActiveMaterialId] = useState<string | null>(null);
  const [aiLectureSessionId, setAiLectureSessionId] = useState<string | null>(null);
  const [recordingStatus, setRecordingStatus] = useState("not_started");
  const [recordingUrl, setRecordingUrl] = useState("");
  const [autoStartRequest, setAutoStartRequest] = useState<AiLectureAutoStartRequest | null>(() =>
    readStoredJson<AiLectureAutoStartRequest>(AI_LECTURE_AUTOSTART_REQUEST_KEY),
  );
  const [preferredSessionId] = useState<string | null>(() => readStoredString(AI_LECTURE_PREFERRED_SESSION_KEY));

  const {
    audioRef,
    error: webRtcError,
    livetalkingSessionId,
    start: startWebRtc,
    status: webRtcStatus,
    stop: stopWebRtc,
    videoRef,
  } = useAiLecturerWebRtc();

  const activeSlide = outline[activeSlideIndex] ?? null;
  const activeMaterial = materials.find((item) => item.material_id === activeMaterialId) ?? materials[0] ?? null;
  const activeMaterialMarkdown = activeMaterial ? courseMaterialToMarkdown(activeMaterial) : "";
  const activeMaterialContent = materialContent(activeMaterial);
  const activeMaterialState = materialGenerationState(activeMaterial);
  const selectedPptMaterial = useMemo(
    () => (activeMaterial && isPptMaterial(activeMaterial) ? activeMaterial : materials.find(isPptMaterial) ?? null),
    [activeMaterial, materials],
  );
  const persistedRecordingUrl = String(activeMaterialContent.recording_url || recordingUrl || "");

  useEffect(() => {
    setRawDocument(defaultMarkdown(selectedCourse?.title));
  }, [selectedCourse?.title]);

  useEffect(() => {
    let cancelled = false;

    async function loadMaterials() {
      try {
        setMaterialsLoading(true);
        setMaterialsError(null);
        const data = await getCourseMaterials(course.id);
        if (!cancelled) {
        setMaterials(data);
        setActiveMaterialId((current) =>
            current && data.some((item) => item.material_id === current)
              ? current
              : autoStartRequest?.sessionId && data.some((item) => item.material_id === autoStartRequest.sessionId)
                ? autoStartRequest.sessionId
                : preferredSessionId && data.some((item) => item.material_id === preferredSessionId)
                  ? preferredSessionId
                  : autoStartRequest?.pptMaterialId && data.some((item) => item.material_id === autoStartRequest.pptMaterialId)
                    ? autoStartRequest.pptMaterialId
                    : data[0]?.material_id ?? null,
          );
        }
      } catch (err) {
        if (!cancelled) {
          setMaterials([]);
          setActiveMaterialId(null);
          setMaterialsError(err instanceof Error ? err.message : "Failed to load course materials.");
        }
      } finally {
        if (!cancelled) {
          setMaterialsLoading(false);
        }
      }
    }

    void loadMaterials();

    return () => {
      cancelled = true;
    };
  }, [autoStartRequest?.pptMaterialId, autoStartRequest?.sessionId, course.id, preferredSessionId]);

  useEffect(() => {
    if (!offlineTaskId || offlineStatus === "success" || offlineStatus === "failed") return;

    const timer = window.setInterval(async () => {
      try {
        const result = await getAiLecturerTaskStatus(offlineTaskId);
        setOfflineStatus(result.status);
        if (result.status === "success" && result.video_url) {
          setOfflineVideoUrl(getAiLecturerVideoUrl(result.video_url));
        }
        if (result.status === "failed") {
          setError(result.error || "Offline video generation failed.");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to poll offline video status.");
      }
    }, 4000);

    return () => window.clearInterval(timer);
  }, [offlineStatus, offlineTaskId]);

  useEffect(() => {
    if (!activeMaterial || activeMaterial.material_type !== "ai_lecture_session") return;

    const sessionId = String(activeMaterialContent.session_snapshot_id || activeMaterial.material_id || "");
    if (!sessionId) return;
    setAiLectureSessionId(sessionId);
    setRecordingUrl(String(activeMaterialContent.recording_url || ""));
    setRecordingStatus(String(activeMaterialState.status || "completed"));
  }, [activeMaterial, activeMaterialContent.recording_url, activeMaterialContent.session_snapshot_id, activeMaterialState.status]);

  const onlineSummary = useMemo(() => {
    return `${outline.length} slides | slide ${outline.length ? activeSlideIndex + 1 : 0} | ${scriptSentences.length} script lines`;
  }, [activeSlideIndex, outline.length, scriptSentences.length]);

  async function withBusy(name: string, action: () => Promise<void>) {
    try {
      setBusy(name);
      setError(null);
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Operation failed.");
    } finally {
      setBusy("");
    }
  }

  async function refreshAiLectureSession(sessionId: string) {
    const detail = await getAiLectureSession(course.id, sessionId);
    const content = materialContent(detail.material);
    setRecordingStatus(String(detail.metadata.recording_status || "not_started"));
    setRecordingUrl(String(detail.metadata.recording_url || content.recording_url || ""));
  }

  async function handleCreateCourse() {
    await withBusy("create-course", async () => {
      const result = await createAiLecturerCourse({
        course_name: course.title || "AI Lecture Course",
        raw_document: rawDocument,
      });
      setAiLecturerCourseId(result.course_id);
      setOutline(result.pages || []);
      setActiveSlideIndex(0);
      setScriptSentences([]);
      setCurrentSentence("");
      setAnswerText("");
    });
  }

  async function startRealtimeSession(options?: { sessionId?: string | null; sourcePptMaterial?: CourseMaterial | null }) {
      const sourcePptMaterial = options?.sourcePptMaterial ?? selectedPptMaterial;
      if (!sourcePptMaterial) {
        throw new Error("Select or generate a PPT material before starting realtime playback.");
      }

      const sessionMaterial = options?.sessionId
        ? null
        : await createAiLectureSession(course.id, {
            source_ppt_material_id: sourcePptMaterial.material_id,
            title: `${sourcePptMaterial.title || course.title} - AI lecture session`,
          });
      const sessionId = options?.sessionId || aiLectureSessionId || String(materialContent(sessionMaterial).session_snapshot_id || sessionMaterial?.material_id || "");
      if (!sessionId) {
        throw new Error("AI lecture session id was not returned.");
      }

      setAiLectureSessionId(sessionId);
      const liveSessionId = await startWebRtc();
      if (!liveSessionId) {
        throw new Error("LiveTalking session was not connected.");
      }

      const metadata = await startAiLectureSessionRecording(course.id, sessionId, liveSessionId);
      setRecordingStatus(String(metadata.recording_status || "recording"));
      await patchAiLectureSessionSnapshot(course.id, sessionId, {
        events: [{ type: "session_started", livetalking_session_id: liveSessionId, created_at: new Date().toISOString() }],
        last_position: { page_index: activeSlideIndex, sentence_index: 0 },
      });
  }

  async function handleStartRealtimeSession() {
    await withBusy("start-session", async () => {
      await startRealtimeSession();
    });
  }

  useEffect(() => {
    if (!autoStartRequest?.autoPlay || materialsLoading || autoStartAttemptedRef.current) {
      return;
    }

    const sourcePptMaterial =
      materials.find((item) => item.material_id === autoStartRequest.pptMaterialId && isPptMaterial(item)) || null;
    if (!sourcePptMaterial) {
      setAutoStartRequest(null);
      return;
    }

    autoStartAttemptedRef.current = true;
    setMode("online");
    setActiveMaterialId(autoStartRequest.sessionId || sourcePptMaterial.material_id);

    void withBusy("start-session", async () => {
      await startRealtimeSession({
        sessionId: autoStartRequest.sessionId || null,
        sourcePptMaterial,
      });
      setAutoStartRequest(null);
    });
  }, [autoStartRequest, materials, materialsLoading]);

  async function handleGenerateScript() {
    if (!activeSlide || !outline.length) {
      setError("Create an AI lecturer course and select a slide first.");
      return;
    }

    await withBusy("generate-script", async () => {
      const result = await generateAiLecturerScript({
        course_title: course.title || "AI Lecture Course",
        current_slide_content: activeSlide.content,
        page_index: activeSlideIndex,
        total_pages: outline.length,
      });
      setScriptSentences(result.sentences || []);
      setCurrentSentence(result.sentences?.[0] || "");
    });
  }

  async function handleSpeak(sentence: string, sentenceIndex: number) {
    if (!livetalkingSessionId) {
      setError("Start realtime playback before sending speech.");
      return;
    }

    await withBusy("speak", async () => {
      await speakAiLecturerSentence({ text: sentence, session_id: livetalkingSessionId });
      setCurrentSentence(sentence);
      if (aiLectureSessionId) {
        await patchAiLectureSessionSnapshot(course.id, aiLectureSessionId, {
          events: [{ type: "speak", text: sentence, page_index: activeSlideIndex, sentence_index: sentenceIndex }],
          last_position: { page_index: activeSlideIndex, sentence_index: sentenceIndex },
        });
      }
    });
  }

  async function handleStopSpeaking() {
    if (!livetalkingSessionId) return;

    await withBusy("stop-speech", async () => {
      await stopAiLecturerSpeaking(livetalkingSessionId);
      if (aiLectureSessionId) {
        await patchAiLectureSessionSnapshot(course.id, aiLectureSessionId, {
          events: [{ type: "stop_speaking", page_index: activeSlideIndex }],
          last_position: { page_index: activeSlideIndex, sentence_index: Math.max(scriptSentences.indexOf(currentSentence), 0) },
        });
      }
    });
  }

  async function handleInterruptAsk() {
    if (!studentQuestion.trim()) {
      setError("Enter a student question first.");
      return;
    }
    if (!livetalkingSessionId) {
      setError("Start realtime playback before interrupting.");
      return;
    }

    await withBusy("ask", async () => {
      const question = studentQuestion.trim();
      const result = await askAiLecturer({
        question,
        slide_context: activeSlide?.content || "",
        interrupted_sentence: currentSentence || "",
        session_id: livetalkingSessionId,
      });
      setAnswerText(result.answer || "");
      if (aiLectureSessionId) {
        await patchAiLectureSessionSnapshot(course.id, aiLectureSessionId, {
          events: [{ type: "interrupt_ask", question, answer: result.answer || "", page_index: activeSlideIndex }],
          last_position: { page_index: activeSlideIndex, sentence_index: Math.max(scriptSentences.indexOf(currentSentence), 0) },
        });
      }
    });
  }

  async function handleStopRealtimeSession() {
    await withBusy("stop-session", async () => {
      if (aiLectureSessionId && livetalkingSessionId) {
        const metadata = await stopAiLectureSessionRecording(course.id, aiLectureSessionId, livetalkingSessionId);
        setRecordingStatus(String(metadata.recording_status || "completed"));
        setRecordingUrl(String(metadata.recording_url || ""));
        await refreshAiLectureSession(aiLectureSessionId);
      }
      stopWebRtc();
    });
  }

  async function handleGenerateOfflineVideo() {
    if (!outline.length) {
      setError("Create an AI lecturer course first.");
      return;
    }
    if (!offlineImageRoot.trim()) {
      setError("Enter the PPT image folder first.");
      return;
    }

    await withBusy("offline", async () => {
      const normalizedRoot = offlineImageRoot.replace(/[\\]+/g, "/").replace(/\/$/, "");
      const result = await generateAiLecturerFullVideo({
        course_title: course.title || "AI Lecture Course",
        pages: outline.map((item, index) => ({
          ppt_image_path: `${normalizedRoot}/slide${index + 1}.png`,
          content_text: item.content,
        })),
      });
      setOfflineTaskId(result.task_id);
      setOfflineStatus("processing");
      setOfflineVideoUrl("");
    });
  }

  return (
    <AppSurface className="flex h-screen overflow-hidden">
      <SidebarDock className="h-screen gap-6 overflow-hidden bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="px-2 py-4">
          <SidebarBackLink />
          <h2 className="text-xl font-extrabold tracking-tight text-[var(--accent-strong)]">{course.title}</h2>
          <p className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--muted-text)]">AI lecturer playback</p>
        </div>
        <SidebarNav activeRoute={routes.video} />
      </SidebarDock>

      <div className="grid min-w-0 flex-1 overflow-hidden lg:grid-cols-[340px_minmax(0,1fr)_360px]">
        <aside className="border-r border-[var(--shell-border)] bg-[var(--surface-subtle)] lg:h-screen lg:overflow-auto">
          <div className="border-b border-[var(--shell-border)] bg-[var(--surface-elevated)]/92 p-6 backdrop-blur-xl">
            <h3 className="text-lg font-bold text-[var(--accent-strong)]">Course Materials</h3>
            <p className="mt-1 text-xs uppercase tracking-[0.22em] text-[var(--muted-text)]">{course.id}</p>
          </div>
          <div className="space-y-5 p-4">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setMode("online")}
                className={`flex-1 rounded-full px-4 py-3 text-sm font-bold ${mode === "online" ? "bg-[var(--accent)] text-white" : "bg-white text-[var(--accent-strong)]"}`}
              >
                Realtime
              </button>
              <button
                type="button"
                onClick={() => setMode("offline")}
                className={`flex-1 rounded-full px-4 py-3 text-sm font-bold ${mode === "offline" ? "bg-[var(--accent)] text-white" : "bg-white text-[var(--accent-strong)]"}`}
              >
                Offline MP4
              </button>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-white p-4">
              <p className="text-sm font-bold text-[var(--accent-strong)]">Source Markdown</p>
              <textarea
                value={rawDocument}
                onChange={(event) => setRawDocument(event.target.value)}
                className="mt-3 min-h-[180px] w-full rounded-[18px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4 text-sm outline-none"
              />
              <button
                type="button"
                onClick={() => void handleCreateCourse()}
                disabled={busy === "create-course" || !rawDocument.trim()}
                className="mt-3 w-full rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
              >
                {busy === "create-course" ? "Creating..." : "Create AI Course Outline"}
              </button>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-white p-4">
              <p className="text-sm font-bold text-[var(--accent-strong)]">Persisted Materials</p>
              <div className="mt-3 space-y-3">
                {materialsLoading ? (
                  <div className="rounded-[18px] bg-[var(--surface-subtle)] p-4 text-sm text-[var(--muted-text)]">Loading...</div>
                ) : materialsError ? (
                  <div className="rounded-[18px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-600">{materialsError}</div>
                ) : materials.length ? (
                  materials.map((item) => (
                    <button
                      key={item.material_id}
                      type="button"
                      onClick={() => setActiveMaterialId(item.material_id)}
                      className={`w-full rounded-[18px] border p-4 text-left ${
                        item.material_id === activeMaterial?.material_id
                          ? "border-[var(--accent-border)] bg-[var(--accent-soft)]"
                          : "border-[var(--shell-border)] bg-[var(--surface-subtle)]"
                      }`}
                    >
                      <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">{item.material_type}</p>
                      <p className="mt-2 line-clamp-2 text-sm font-bold text-[var(--app-text)]">{item.title || item.topic || item.material_id}</p>
                    </button>
                  ))
                ) : (
                  <div className="rounded-[18px] bg-[var(--surface-subtle)] p-4 text-sm text-[var(--muted-text)]">No materials yet.</div>
                )}
              </div>
            </div>
          </div>
        </aside>

        <main className="min-w-0 overflow-y-auto bg-[var(--app-bg)] lg:h-screen">
          <header className="sticky top-0 z-40 border-b border-[var(--shell-border)] bg-[var(--app-bg)]/88 px-8 py-4 backdrop-blur-xl">
            <h1 className="text-xl font-extrabold tracking-tight text-[var(--accent-strong)]">AI Lecturer Video</h1>
            <p className="mt-1 text-sm text-[var(--muted-text)]">
              Realtime sessions use LiveTalking WebRTC. Saved recordings are persisted back into course resources.
            </p>
          </header>

          <div className="mx-auto w-full max-w-5xl px-6 py-6 xl:px-8">
            <GlassPanel className="overflow-hidden bg-[#020617]">
              {mode === "online" ? (
                <div className="relative aspect-video bg-black">
                  <video ref={videoRef} autoPlay playsInline muted className="h-full w-full bg-black object-contain" />
                  <audio ref={audioRef} autoPlay />
                  {webRtcStatus !== "connected" ? (
                    <div className="absolute inset-0 grid place-items-center bg-[radial-gradient(circle_at_35%_20%,rgba(56,189,248,0.28),transparent_32%),linear-gradient(135deg,#020617_0%,#0f172a_50%,#164e63_100%)]">
                      <div className="max-w-md rounded-[28px] border border-white/15 bg-white/10 p-6 text-center text-white backdrop-blur-xl">
                        <p className="text-sm font-bold uppercase tracking-[0.2em] text-cyan-100">LiveTalking</p>
                        <h2 className="mt-3 text-3xl font-black">Realtime AI lecture stream</h2>
                        <p className="mt-3 text-sm leading-6 text-cyan-50/80">Start a session to connect the remote digital lecturer.</p>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : offlineVideoUrl ? (
                <video controls className="aspect-video w-full bg-black" src={offlineVideoUrl} />
              ) : (
                <div className="aspect-video bg-[radial-gradient(circle_at_20%_20%,rgba(96,165,250,0.32),transparent_24%),radial-gradient(circle_at_75%_58%,rgba(14,165,233,0.22),transparent_30%),linear-gradient(135deg,#020617_0%,#0f172a_45%,#1d4ed8_100%)]" />
              )}
            </GlassPanel>

            {mode === "online" ? (
              <section className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h2 className="text-2xl font-black text-[var(--accent-strong)]">Realtime Session</h2>
                      <p className="mt-1 text-sm text-[var(--muted-text)]">
                        {aiLectureSessionId || "No persisted session yet"} | LiveTalking {livetalkingSessionId || "--"}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => void handleStartRealtimeSession()}
                        disabled={busy === "start-session" || webRtcStatus === "connected"}
                        className="rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                      >
                        {busy === "start-session" ? "Starting..." : "Start Session"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleStopRealtimeSession()}
                        disabled={busy === "stop-session" || webRtcStatus === "idle"}
                        className="rounded-full border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-bold text-rose-600 disabled:opacity-60"
                      >
                        {busy === "stop-session" ? "Saving..." : "Stop & Save"}
                      </button>
                    </div>
                  </div>

                  <div className="mt-5 rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4">
                    <p className="text-sm font-bold text-[var(--accent-strong)]">{activeSlide ? activeSlide.title : "No slide selected"}</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--muted-text)]">
                      {activeSlide?.content || "Create the AI course outline, then generate script for a slide."}
                    </p>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => void handleGenerateScript()}
                      disabled={busy === "generate-script"}
                      className="rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                    >
                      {busy === "generate-script" ? "Generating..." : "Generate Script"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleStopSpeaking()}
                      disabled={busy === "stop-speech" || !livetalkingSessionId}
                      className="rounded-full border border-[var(--shell-border)] bg-white px-4 py-3 text-sm font-bold text-[var(--accent-strong)] disabled:opacity-60"
                    >
                      Stop Speaking
                    </button>
                  </div>

                  <div className="mt-4 space-y-3">
                    {scriptSentences.map((sentence, index) => (
                      <button
                        key={`${index}-${sentence}`}
                        type="button"
                        onClick={() => void handleSpeak(sentence, index)}
                        className={`w-full rounded-[18px] border p-4 text-left ${
                          currentSentence === sentence ? "border-[var(--accent-border)] bg-[var(--accent-soft)]" : "border-[var(--shell-border)] bg-white"
                        }`}
                      >
                        <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">Sentence {index + 1}</p>
                        <p className="mt-2 text-sm leading-7 text-[var(--app-text)]">{sentence}</p>
                      </button>
                    ))}
                    {!scriptSentences.length ? <div className="text-sm text-[var(--muted-text)]">No script generated yet.</div> : null}
                  </div>
                </GlassPanel>

                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <h2 className="text-2xl font-black text-[var(--accent-strong)]">Interrupt & Ask</h2>
                  <textarea
                    value={studentQuestion}
                    onChange={(event) => setStudentQuestion(event.target.value)}
                    className="mt-4 min-h-[140px] w-full rounded-[20px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4 text-sm outline-none"
                    placeholder="Ask a question during the lecture..."
                  />
                  <button
                    type="button"
                    onClick={() => void handleInterruptAsk()}
                    disabled={busy === "ask" || !livetalkingSessionId}
                    className="mt-4 w-full rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                  >
                    {busy === "ask" ? "Asking..." : "Interrupt and Ask"}
                  </button>
                  <div className="mt-5 rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4">
                    <p className="text-sm font-bold text-[var(--accent-strong)]">AI Answer</p>
                    <div className="mt-3 text-sm leading-7 text-[var(--muted-text)]">
                      <MarkdownPreview content={answerText || "The answer will appear here."} />
                    </div>
                  </div>
                </GlassPanel>
              </section>
            ) : (
              <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_1fr]">
                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <h2 className="text-2xl font-black text-[var(--accent-strong)]">Offline MP4 Generation</h2>
                  <p className="mt-3 text-sm leading-7 text-[var(--muted-text)]">
                    Enter the folder containing slide1.png, slide2.png, and so on. This legacy path still generates a normal video file.
                  </p>
                  <input
                    value={offlineImageRoot}
                    onChange={(event) => setOfflineImageRoot(event.target.value)}
                    className="mt-4 h-12 w-full rounded-[18px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] px-4 text-sm outline-none"
                    placeholder="D:/AI_Lecturer/assets"
                  />
                  <button
                    type="button"
                    onClick={() => void handleGenerateOfflineVideo()}
                    disabled={busy === "offline"}
                    className="mt-4 w-full rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                  >
                    {busy === "offline" ? "Generating..." : "Generate Offline Video"}
                  </button>
                </GlassPanel>

                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <h2 className="text-2xl font-black text-[var(--accent-strong)]">Offline Status</h2>
                  <div className="mt-4 space-y-3 text-sm text-[var(--muted-text)]">
                    <p>Task ID: {offlineTaskId || "--"}</p>
                    <p>Status: {offlineStatus || "--"}</p>
                    <p>Video URL: {offlineVideoUrl || "--"}</p>
                  </div>
                  {offlineVideoUrl ? (
                    <div className="mt-5 flex gap-3">
                      <a
                        href={offlineVideoUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-1 rounded-full border border-[var(--shell-border)] bg-white px-4 py-3 text-center text-sm font-bold text-[var(--accent-strong)]"
                      >
                        Open
                      </a>
                      <a
                        href={getAiLecturerDownloadUrl(fileNameFromUrl(offlineVideoUrl))}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-1 rounded-full bg-[var(--accent)] px-4 py-3 text-center text-sm font-bold text-white"
                      >
                        Download
                      </a>
                    </div>
                  ) : null}
                </GlassPanel>
              </section>
            )}

            <section id="course-materials" className="mt-8">
              <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--shell-border)] pb-5">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">Session Resource</p>
                    <h2 className="mt-2 text-2xl font-black text-[var(--accent-strong)]">Course Resource Preview</h2>
                    <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--muted-text)]">
                      Select a PPT to start realtime playback, or select an AI lecture session to replay its saved recording.
                    </p>
                  </div>
                  <div className="rounded-[20px] border border-[var(--accent-border)] bg-[var(--accent-soft)] px-4 py-3 text-sm font-semibold text-[var(--accent-strong)]">
                    Recording: {recordingStatus}
                  </div>
                </div>

                {persistedRecordingUrl ? (
                  <video controls className="mt-6 aspect-video w-full rounded-[22px] bg-black" src={playbackUrl(persistedRecordingUrl)} />
                ) : (
                  <div className="mt-6 rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-5 text-sm text-[var(--muted-text)]">
                    No saved recording yet. Stop a realtime session to persist the teaching video.
                  </div>
                )}

                {activeMaterial ? (
                  <div className="mt-6 rounded-[24px] border border-[var(--shell-border)] bg-white/88 p-5">
                    <div className="border-b border-[var(--shell-border)] pb-4">
                      <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">
                        {activeMaterial.material_type || "content"}
                      </p>
                      <h3 className="mt-2 text-2xl font-black text-[var(--accent-strong)]">
                        {activeMaterial.title || activeMaterial.topic || activeMaterial.material_id}
                      </h3>
                    </div>
                    <div className="mt-5 max-h-[420px] overflow-y-auto pr-2">
                      <MarkdownPreview content={activeMaterialMarkdown} />
                    </div>
                  </div>
                ) : null}
              </GlassPanel>
            </section>

            {(error || webRtcError) ? (
              <div className="mt-6 rounded-[22px] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-600">
                {error || webRtcError}
              </div>
            ) : null}
          </div>
        </main>

        <aside className="flex flex-col border-l border-[var(--shell-border)] bg-[linear-gradient(180deg,rgba(246,249,255,0.94)_0%,rgba(239,245,253,0.96)_100%)] lg:h-screen lg:overflow-auto">
          <div className="border-b border-[var(--shell-border)] bg-[var(--surface-elevated)]/95 p-6 backdrop-blur-xl">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[var(--accent)] text-white">
                <MaterialIcon name="smart_toy" fill />
              </div>
              <div>
                <h4 className="font-bold text-[var(--accent-strong)]">Session Status</h4>
                <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-[#1b6d24]">{webRtcStatus}</p>
              </div>
            </div>
          </div>

          <div className="flex flex-1 flex-col gap-6 overflow-hidden p-6">
            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5 shadow-[0_14px_28px_rgba(15,23,42,0.05)]">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">Realtime Summary</p>
              <div className="mt-4 space-y-3 text-sm text-[var(--muted-text)]">
                <p>{onlineSummary}</p>
                <p>AI lecturer course: {aiLecturerCourseId || "--"}</p>
                <p>Persisted session: {aiLectureSessionId || "--"}</p>
                <p>LiveTalking session: {livetalkingSessionId || "--"}</p>
                <p>Current sentence: {currentSentence || "--"}</p>
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5 shadow-[0_14px_28px_rgba(15,23,42,0.05)]">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">Slides</p>
              <div className="mt-4 space-y-3">
                {outline.length ? (
                  outline.map((item, index) => (
                    <button
                      key={`${item.title}-${index}`}
                      type="button"
                      onClick={() => setActiveSlideIndex(index)}
                      className={`w-full rounded-[18px] border p-4 text-left ${
                        index === activeSlideIndex ? "border-[var(--accent-border)] bg-[var(--accent-soft)]" : "border-[var(--shell-border)] bg-[var(--surface-subtle)]"
                      }`}
                    >
                      <p className="text-sm font-bold text-[var(--app-text)]">Slide {index + 1}: {item.title}</p>
                      <p className="mt-2 line-clamp-3 text-xs leading-6 text-[var(--muted-text)]">{item.content}</p>
                    </button>
                  ))
                ) : (
                  <div className="rounded-[18px] bg-[var(--surface-subtle)] p-4 text-sm text-[var(--muted-text)]">No outline yet.</div>
                )}
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5 shadow-[0_14px_28px_rgba(15,23,42,0.05)]">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">Quick Links</p>
              <div className="mt-4 space-y-3">
                <button
                  type="button"
                  onClick={() => document.getElementById("course-materials")?.scrollIntoView({ behavior: "smooth", block: "start" })}
                  className="flex w-full items-center justify-between rounded-[18px] bg-[var(--surface-subtle)] px-4 py-3 text-left transition hover:bg-[var(--accent-soft)]"
                >
                  <span className="text-sm font-semibold text-[var(--app-text)]">Course resource preview</span>
                  <MaterialIcon name="arrow_forward" className="text-[var(--accent)]" />
                </button>
                <a href={routeHref(routes.resources)} className="flex items-center justify-between rounded-[18px] bg-[var(--surface-subtle)] px-4 py-3 text-left transition hover:bg-[var(--accent-soft)]">
                  <span className="text-sm font-semibold text-[var(--app-text)]">All course resources</span>
                  <MaterialIcon name="arrow_forward" className="text-[var(--accent)]" />
                </a>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </AppSurface>
  );
}
