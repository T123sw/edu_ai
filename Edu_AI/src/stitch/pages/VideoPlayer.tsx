import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  askAiLecturer,
  createAiLecturerCourse,
  generateAiLecturerScript,
  getAiLecturerDownloadUrl,
  speakAiLecturerSentence,
  stopAiLecturerSpeaking,
} from "../api/video";
import {
  courseMaterialToMarkdown,
  createAiLectureSession,
  createTeachingVideoTask,
  getAiLectureSession,
  getCourseMaterials,
  getKnowledgeGraph,
  getTeachingVideoPpts,
  getTeachingVideoTaskStatus,
  patchAiLectureSessionSnapshot,
  startAiLectureSessionRecording,
  stopAiLectureSessionRecording,
} from "../api/courses";
import { API_BASE_URL } from "../api/client";
import { MarkdownPreview } from "../components/MarkdownPreview";
import { TransparentAvatarCanvas } from "../components/TransparentAvatarCanvas";
import type { AiLectureSessionSnapshot, CourseMaterial, KnowledgeGraphNode, TeachingVideoPptItem } from "../api/types";
import { useAiLecturerWebRtc } from "../hooks/useAiLecturerWebRtc";
import {
  exportCourseMaterialAsWord,
  getCourseMaterialPptExportUrl,
  getCourseMaterialPptPreviewUrl,
  isCourseMaterialWordExportable,
} from "../wordExport";
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

const PPT_PREVIEW_BASE_WIDTH = 1920;
const AI_LECTURE_AUTOSTART_REQUEST_KEY = "stitch-ai-lecture-autostart-request";
const AI_LECTURE_AUTOSTART_EVENT = "stitch-ai-lecture-autostart";
const AI_LECTURE_PREFERRED_SESSION_KEY = "stitch-ai-lecture-session-id";
const API_AUTH_STORAGE_KEY = "edu-ai-auth";

function readStoredJson<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : null;
  } catch {
    return null;
  }
}

function readStoredString(key: string) {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(key) || "";
}

function clearStoredValue(key: string) {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(key);
}

function getDefaultMarkdown(courseTitle?: string) {
  return [
    `# ${courseTitle || "课程讲义"}`,
    "",
    "## 第一部分 课程导入",
    "",
    "- 课程背景",
    "- 学习目标",
    "",
    "## 第二部分 核心概念",
    "",
    "- 核心知识点一",
    "- 核心知识点二",
    "",
    "## 第三部分 总结",
    "",
    "- 重点回顾",
    "- 延伸思考",
  ].join("\n");
}

function normalizeAiLecturerPages(pages: unknown): Slide[] {
  if (!Array.isArray(pages)) {
    throw new Error("AI Lecturer create_course returned non-array pages.");
  }

  const normalized = pages
    .slice(0, 15)
    .map((page, index) => {
      if (page && typeof page === "object") {
        const item = page as Record<string, unknown>;
        const title = String(item.title || item.page_title || `Slide ${index + 1}`).trim();
        const rawContent = item.content || item.body || item.text || item.bullets || "";
        const content = Array.isArray(rawContent)
          ? rawContent.map((part) => String(part).trim()).filter(Boolean).join("\n")
          : String(rawContent || "").trim();
        return { title, content: content || title };
      }

      const content = String(page || "").trim();
      return { title: `Slide ${index + 1}`, content };
    })
    .filter((page) => page.title || page.content);

  if (!normalized.length) {
    throw new Error("AI Lecturer create_course returned empty pages.");
  }

  return normalized;
}

function describeError(err: unknown) {
  return err instanceof Error ? err.message : String(err);
}

async function runRealtimeStage<T>(stage: string, action: () => Promise<T>): Promise<T> {
  console.info(`[AI Lecturer][Realtime] ${stage}: start`);
  try {
    const result = await action();
    console.info(`[AI Lecturer][Realtime] ${stage}: done`);
    return result;
  } catch (err) {
    console.error(`[AI Lecturer][Realtime] ${stage}: failed`, err);
    throw new Error(`${stage} failed: ${describeError(err)}`);
  }
}

function fileNameFromUrl(url: string) {
  const normalized = url.split("?")[0];
  return normalized.slice(normalized.lastIndexOf("/") + 1);
}

function buildRealtimeStagePptPreviewUrl(previewUrl: string, slideIndex = 0) {
  const normalized = String(previewUrl || "").trim();
  if (!normalized) return "";
  const safeSlideIndex = Math.max(1, Math.round(slideIndex) + 1);

  try {
    const nextUrl = /^https?:\/\//i.test(normalized)
      ? new URL(normalized)
      : new URL(normalized, typeof window !== "undefined" ? window.location.origin : API_BASE_URL);
    nextUrl.searchParams.set("preview_mode", "single-slide");
    nextUrl.searchParams.set("slide", String(safeSlideIndex));
    nextUrl.searchParams.set("page", String(safeSlideIndex));
    nextUrl.hash = `slide-${safeSlideIndex}`;
    return /^https?:\/\//i.test(normalized)
      ? nextUrl.toString()
      : `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`;
  } catch {
    const [pathPart] = normalized.split("#", 2);
    const joiner = pathPart.includes("?") ? "&" : "?";
    const nextHash = `#slide-${safeSlideIndex}`;
    return `${pathPart}${joiner}preview_mode=single-slide&slide=${safeSlideIndex}&page=${safeSlideIndex}${nextHash}`;
  }
}

function buildMaterialFallback(materials: CourseMaterial[]): KnowledgeGraphNode | null {
  if (!materials.length) return null;

  return {
    id: "materials-root",
    label: "课程内容",
    data: {
      type: "chapter",
      summary: "知识图谱不可用时，使用课程内容生成学习结构。",
    },
    children: materials.map((item, index) => ({
      id: item.material_id,
      label: item.title || item.topic || `内容 ${index + 1}`,
      data: {
        type: item.material_type || "topic",
        summary: item.summary || "课程学习资料",
      },
      children: [],
    })),
  };
}

function countNodes(node: KnowledgeGraphNode | null | undefined): number {
  if (!node) return 0;
  return 1 + (node.children || []).reduce((sum, child) => sum + countNodes(child), 0);
}

function findNodeById(node: KnowledgeGraphNode | null | undefined, nodeId: string | null): KnowledgeGraphNode | null {
  if (!node || !nodeId) return null;
  if (node.id === nodeId) return node;

  for (const child of node.children || []) {
    const found = findNodeById(child, nodeId);
    if (found) return found;
  }

  return null;
}

function nodeTypeLabel(node: KnowledgeGraphNode) {
  const type = node.data?.type?.toLowerCase();
  if (type === "chapter") return "章节";
  if (type === "section") return "小节";
  if (type === "topic") return "知识点";
  return "节点";
}

function shouldShowStructureSummary(node: KnowledgeGraphNode) {
  const summary = String(node.data?.summary || "").trim();
  const label = String(node.label || "").trim();
  if (!summary) return false;
  return summary !== label;
}

function isOfflineTaskCompleted(status: string) {
  return ["completed", "success", "succeeded"].includes(status.trim().toLowerCase());
}

function isOfflineTaskFailed(status: string) {
  return status.trim().toLowerCase() === "failed";
}

function estimateSpeechDurationMs(sentence: string) {
  const textLength = sentence.trim().length;
  return Math.min(14000, Math.max(2200, textLength * 180));
}

function playbackUrl(path: string) {
  if (!path) return "";
  if (/^https?:\/\//.test(path)) return path;
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

function readApiAuthToken() {
  if (typeof window === "undefined") return "";
  try {
    const stored = window.localStorage.getItem(API_AUTH_STORAGE_KEY);
    if (!stored) return "";
    const parsed = JSON.parse(stored) as { token?: string };
    return parsed.token || "";
  } catch {
    return "";
  }
}

async function fetchAuthenticatedBlobUrl(path: string) {
  const headers = new Headers();
  const token = readApiAuthToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(playbackUrl(path), { headers });
  if (!response.ok) {
    throw new Error(`Failed to load slide image: ${response.status}`);
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export function VideoPlayerPage() {
  const { selectedCourse } = useAppShell();
  const course = selectedCourse ?? defaultCourse;

  const preferredSessionId = useMemo(() => readStoredString(AI_LECTURE_PREFERRED_SESSION_KEY), []);
  const [autoStartRequest, setAutoStartRequest] = useState<AiLectureAutoStartRequest | null>(() =>
    readStoredJson<AiLectureAutoStartRequest>(AI_LECTURE_AUTOSTART_REQUEST_KEY),
  );
  const [autoStartReady, setAutoStartReady] = useState(false);
  const autoStartAttemptedRef = useRef(false);
  const lastHydratedSessionIdRef = useRef<string | null>(null);
  const autoPlaybackTimerRef = useRef<number | null>(null);
  const playbackPositionRef = useRef({ slideIndex: 0, sentenceIndex: 0, sessionId: "" });
  const outlineRef = useRef<Slide[]>([]);
  const activeSlideIndexRef = useRef(0);
  const slideScriptsRef = useRef<Record<number, string[]>>({});
  const scriptSentencesRef = useRef<string[]>([]);
  const livetalkingSessionIdRef = useRef<number | null>(null);
  const pptPreviewFrameRef = useRef<HTMLDivElement | null>(null);
  const realtimeStagePptFrameRef = useRef<HTMLIFrameElement | null>(null);
  const realtimeStageFrameRef = useRef<HTMLDivElement | null>(null);
  const pageMainScrollRef = useRef<HTMLDivElement | null>(null);
  const initialMainScrollResetRef = useRef(true);
  const routeEntryScrollGuardRef = useRef({ active: true, userInteracted: false });
  const routeEntryScrollReleaseTimerRef = useRef<number | null>(null);

  const [mode, setMode] = useState<"online" | "offline">("online");
  const [rawDocument, setRawDocument] = useState(getDefaultMarkdown(selectedCourse?.title));
  const [courseId, setCourseId] = useState("");
  const [aiLectureSessionId, setAiLectureSessionId] = useState("");
  const [outline, setOutline] = useState<Slide[]>([]);
  const [activeSlideIndex, setActiveSlideIndex] = useState(0);
  const [slideScripts, setSlideScripts] = useState<Record<number, string[]>>({});
  const [scriptSentences, setScriptSentences] = useState<string[]>([]);
  const [currentSentence, setCurrentSentence] = useState("");
  const [currentSentenceIndex, setCurrentSentenceIndex] = useState(0);
  const [isRealtimePlaying, setIsRealtimePlaying] = useState(false);
  const [studentQuestion, setStudentQuestion] = useState("");
  const [answerText, setAnswerText] = useState("");
  const [persistedRecordingUrl, setPersistedRecordingUrl] = useState("");
  const [hydratedSessionSnapshot, setHydratedSessionSnapshot] = useState<AiLectureSessionSnapshot | null>(null);
  const [realtimeStageSlideObjectUrl, setRealtimeStageSlideObjectUrl] = useState("");

  const [offlineTaskId, setOfflineTaskId] = useState("");
  const [offlineStatus, setOfflineStatus] = useState("");
  const [offlineVideoUrl, setOfflineVideoUrl] = useState("");
  const [offlinePpts, setOfflinePpts] = useState<TeachingVideoPptItem[]>([]);
  const [offlinePptsLoading, setOfflinePptsLoading] = useState(true);
  const [offlinePptsError, setOfflinePptsError] = useState<string | null>(null);
  const [selectedOfflinePptId, setSelectedOfflinePptId] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [materialsLoading, setMaterialsLoading] = useState(true);
  const [materialsError, setMaterialsError] = useState<string | null>(null);
  const [activeMaterialId, setActiveMaterialId] = useState<string | null>(preferredSessionId || null);

  const [graphRoot, setGraphRoot] = useState<KnowledgeGraphNode | null>(null);
  const [graphLoading, setGraphLoading] = useState(true);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [activeStructureId, setActiveStructureId] = useState<string | null>(null);
  const [expandedStructureIds, setExpandedStructureIds] = useState<Set<string>>(new Set());
  const [pptPreviewFrameWidth, setPptPreviewFrameWidth] = useState(PPT_PREVIEW_BASE_WIDTH);
  const [realtimeStageFrameWidth, setRealtimeStageFrameWidth] = useState(PPT_PREVIEW_BASE_WIDTH);

  const {
    audioRef,
    error: webRtcError,
    livetalkingSessionId,
    start: startWebRtc,
    status: webRtcStatus,
    stop: stopWebRtc,
    videoRef,
  } = useAiLecturerWebRtc();

  outlineRef.current = outline;
  activeSlideIndexRef.current = activeSlideIndex;
  slideScriptsRef.current = slideScripts;
  scriptSentencesRef.current = scriptSentences;
  livetalkingSessionIdRef.current = livetalkingSessionId;

  const activeSlide = outline[activeSlideIndex] ?? null;
  const activeMaterial = materials.find((item) => item.material_id === activeMaterialId) ?? materials[0] ?? null;
  const activeMaterialContent =
    activeMaterial?.content && typeof activeMaterial.content === "object"
      ? (activeMaterial.content as Record<string, unknown>)
      : {};
  const selectedPptMaterial =
    materials.find((item) => item.material_id === selectedOfflinePptId) ??
    materials.find((item) => item.material_type === "ppt") ??
    activeMaterial ??
    null;
  const sourcePptMaterial =
    materials.find((item) => item.material_id === String(activeMaterialContent.source_ppt_material_id || "")) ?? null;
  const activeMaterialMarkdown = activeMaterial ? courseMaterialToMarkdown(activeMaterial) : "";
  const canExportActiveMaterial = isCourseMaterialWordExportable(activeMaterial, activeMaterialMarkdown);
  const activeMaterialPptExportUrl = getCourseMaterialPptExportUrl(activeMaterial);
  const activeMaterialPptPreviewUrl = getCourseMaterialPptPreviewUrl(activeMaterial);
  const selectedPptPreviewUrl = getCourseMaterialPptPreviewUrl(sourcePptMaterial || selectedPptMaterial);
  const realtimeStagePptPreviewUrl = buildRealtimeStagePptPreviewUrl(selectedPptPreviewUrl, activeSlideIndex);
  const realtimeStageSlideImageUrls = Array.isArray(hydratedSessionSnapshot?.slide_image_urls)
    ? hydratedSessionSnapshot.slide_image_urls.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
  const realtimeStageSlideImageUrl = realtimeStageSlideImageUrls[activeSlideIndex] || "";
  const pptPreviewScale = Math.min(1, pptPreviewFrameWidth / PPT_PREVIEW_BASE_WIDTH);
  const realtimeStagePptScale = Math.min(1, realtimeStageFrameWidth / PPT_PREVIEW_BASE_WIDTH);
  const lectureMarkdown =
    sourcePptMaterial || selectedPptMaterial
      ? courseMaterialToMarkdown(sourcePptMaterial || selectedPptMaterial)
      : rawDocument;
  const selectedOfflinePpt = offlinePpts.find((item) => item.material_id === selectedOfflinePptId) ?? null;

  const fallbackStructure = useMemo(() => buildMaterialFallback(materials), [materials]);
  const structureRoot = graphRoot ?? fallbackStructure;
  const activeStructureNode = useMemo(
    () => findNodeById(structureRoot, activeStructureId) ?? structureRoot,
    [activeStructureId, structureRoot],
  );
  const selectedMaterialScope = useMemo(() => {
    const selectedGraphNode = findNodeById(graphRoot, activeStructureId);

    if (graphRoot && selectedGraphNode && selectedGraphNode.id !== graphRoot.id) {
      return {
        scopeType: "knowledge_point" as const,
        scopeId: selectedGraphNode.id,
        aggregate: false,
      };
    }

    return {
      scopeType: "course" as const,
      aggregate: false,
    };
  }, [activeStructureId, graphRoot]);
  const structureNodeCount = useMemo(() => countNodes(structureRoot), [structureRoot]);

  const learningSummary = useMemo(() => {
    return `已解析 ${outline.length} 页，当前第 ${outline.length ? activeSlideIndex + 1 : 0} 页，当前讲稿 ${
      scriptSentences.length
    } 句。`;
  }, [activeSlideIndex, outline.length, scriptSentences.length]);

  function resetPageMainScrollToTop() {
    if (!pageMainScrollRef.current) return;
    pageMainScrollRef.current.scrollTop = 0;
    pageMainScrollRef.current.scrollLeft = 0;
  }

  function clearRouteEntryScrollReleaseTimer() {
    if (routeEntryScrollReleaseTimerRef.current !== null) {
      window.clearTimeout(routeEntryScrollReleaseTimerRef.current);
      routeEntryScrollReleaseTimerRef.current = null;
    }
  }

  function releaseRouteEntryScrollGuard() {
    routeEntryScrollGuardRef.current.active = false;
    clearRouteEntryScrollReleaseTimer();
  }

  function scheduleRouteEntryScrollGuardRelease(delayMs: number) {
    clearRouteEntryScrollReleaseTimer();
    routeEntryScrollReleaseTimerRef.current = window.setTimeout(() => {
      releaseRouteEntryScrollGuard();
    }, delayMs);
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setAutoStartReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useLayoutEffect(() => {
    initialMainScrollResetRef.current = true;
    routeEntryScrollGuardRef.current = { active: true, userInteracted: false };
    resetPageMainScrollToTop();
    scheduleRouteEntryScrollGuardRelease(4500);
    return clearRouteEntryScrollReleaseTimer;
  }, [course.id]);

  useLayoutEffect(() => {
    if (!initialMainScrollResetRef.current) return;
    resetPageMainScrollToTop();
    if (!materialsLoading && !graphLoading && !offlinePptsLoading) {
      initialMainScrollResetRef.current = false;
      scheduleRouteEntryScrollGuardRelease(1400);
    }
  }, [materialsLoading, graphLoading, offlinePptsLoading, materials.length, graphRoot, offlinePpts.length]);

  useEffect(() => {
    const pageMain = pageMainScrollRef.current;
    if (!pageMain) return undefined;

    function markUserInteracted() {
      routeEntryScrollGuardRef.current.userInteracted = true;
      releaseRouteEntryScrollGuard();
    }

    function guardRouteEntryScroll() {
      const guard = routeEntryScrollGuardRef.current;
      if (!guard.active || guard.userInteracted) return;
      if (pageMain.scrollTop === 0 && pageMain.scrollLeft === 0) return;
      resetPageMainScrollToTop();
      window.requestAnimationFrame(resetPageMainScrollToTop);
    }

    pageMain.addEventListener("scroll", guardRouteEntryScroll, { passive: true });
    window.addEventListener("wheel", markUserInteracted, { capture: true, passive: true });
    window.addEventListener("touchmove", markUserInteracted, { capture: true, passive: true });
    window.addEventListener("pointerdown", markUserInteracted, { capture: true });
    window.addEventListener("keydown", markUserInteracted, { capture: true });

    return () => {
      pageMain.removeEventListener("scroll", guardRouteEntryScroll);
      window.removeEventListener("wheel", markUserInteracted, { capture: true });
      window.removeEventListener("touchmove", markUserInteracted, { capture: true });
      window.removeEventListener("pointerdown", markUserInteracted, { capture: true });
      window.removeEventListener("keydown", markUserInteracted, { capture: true });
    };
  }, [course.id]);

  useEffect(() => {
    const handleAutoStartEvent = (event: CustomEvent<AiLectureAutoStartRequest>) => {
      if (event.detail?.autoPlay) {
        autoStartAttemptedRef.current = false;
        setAutoStartRequest(event.detail);
      }
    };

    window.addEventListener(AI_LECTURE_AUTOSTART_EVENT, handleAutoStartEvent as EventListener);
    return () => window.removeEventListener(AI_LECTURE_AUTOSTART_EVENT, handleAutoStartEvent as EventListener);
  }, []);

  useEffect(() => {
    const element = pptPreviewFrameRef.current;
    if (!element || typeof ResizeObserver === "undefined" || !activeMaterialPptPreviewUrl) {
      return;
    }

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      const nextWidth = Math.max(Math.floor(entry?.contentRect?.width || 0), 320);
      setPptPreviewFrameWidth(nextWidth);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [activeMaterial?.material_id, activeMaterialPptPreviewUrl]);

  useEffect(() => {
    const element = realtimeStageFrameRef.current;
    if (!element || typeof ResizeObserver === "undefined" || (!realtimeStagePptPreviewUrl && !realtimeStageSlideImageUrl)) {
      return;
    }

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      const nextWidth = Math.max(Math.floor(entry?.contentRect?.width || 0), 320);
      setRealtimeStageFrameWidth(nextWidth);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [realtimeStagePptPreviewUrl, realtimeStageSlideImageUrl]);

  useEffect(() => {
    let cancelled = false;
    let objectUrl = "";

    setRealtimeStageSlideObjectUrl("");
    if (!realtimeStageSlideImageUrl) {
      return () => {};
    }

    void fetchAuthenticatedBlobUrl(realtimeStageSlideImageUrl)
      .then((nextObjectUrl) => {
        objectUrl = nextObjectUrl;
        if (cancelled) {
          URL.revokeObjectURL(nextObjectUrl);
          return;
        }
        setRealtimeStageSlideObjectUrl(objectUrl);
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn("[AI Lecturer][Realtime] failed to load slide image", err);
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [realtimeStageSlideImageUrl]);

  function syncRealtimeStagePptSlide(slideIndex = activeSlideIndex) {
    realtimeStagePptFrameRef.current?.contentWindow?.postMessage(
      {
        type: "ppt-preview-go-to-slide",
        slideIndex: Math.max(1, slideIndex + 1),
      },
      "*",
    );
  }

  useEffect(() => {
    if (mode !== "online" || !realtimeStagePptPreviewUrl || realtimeStageSlideImageUrl) {
      return;
    }
    syncRealtimeStagePptSlide(activeSlideIndex);
  }, [activeSlideIndex, mode, realtimeStagePptPreviewUrl, realtimeStageSlideImageUrl]);

  useEffect(() => {
    function handleRealtimeStagePreviewMessage(event: MessageEvent) {
      if (event.source !== realtimeStagePptFrameRef.current?.contentWindow) return;
      const data =
        event.data && typeof event.data === "object" ? (event.data as Record<string, unknown>) : {};
      if (data.type !== "ppt-preview-ready") return;
      syncRealtimeStagePptSlide(activeSlideIndexRef.current);
    }

    window.addEventListener("message", handleRealtimeStagePreviewMessage);
    return () => window.removeEventListener("message", handleRealtimeStagePreviewMessage);
  }, []);

  async function hydrateAiLectureSessionState(sessionId: string) {
    const result = await getAiLectureSession(course.id, sessionId);
    const snapshot = result.snapshot || {};
    const snapshotSlideImageUrls = Array.isArray(snapshot.slide_image_urls)
      ? snapshot.slide_image_urls.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      : [];
    snapshot.slide_image_urls = snapshotSlideImageUrls;
    setHydratedSessionSnapshot(snapshot);
    if (snapshot.ai_lecturer_course_id) {
      setCourseId(String(snapshot.ai_lecturer_course_id));
    }
    if (Array.isArray(snapshot.outline) && snapshot.outline.length) {
      setOutline(snapshot.outline);
    }
    if (Array.isArray(snapshot.script)) {
      const nextScripts = snapshot.script.reduce<Record<number, string[]>>((acc, item) => {
        acc[Number(item.page_index) || 0] = item.sentences || [];
        return acc;
      }, {});
      setSlideScripts(nextScripts);
      const pageIndex = Number(snapshot.last_position?.page_index || 0);
      setActiveSlideIndex(pageIndex);
      setScriptSentences(nextScripts[pageIndex] || []);
      setCurrentSentenceIndex(Number(snapshot.last_position?.sentence_index || 0));
    }
    if (result.metadata?.recording_url) {
      setPersistedRecordingUrl(String(result.metadata.recording_url));
    }
    return result;
  }

  useEffect(() => {
    setRawDocument(getDefaultMarkdown(selectedCourse?.title));
  }, [selectedCourse?.title]);

  useEffect(() => {
    let cancelled = false;

    async function loadMaterials() {
      try {
        setMaterialsLoading(true);
        setMaterialsError(null);
        const data = await getCourseMaterials(course.id, selectedMaterialScope);
        if (!cancelled) {
          setMaterials(data);
          setActiveMaterialId((current) => {
            if (current && data.some((item) => item.material_id === current)) return current;
            if (preferredSessionId && data.some((item) => item.material_id === preferredSessionId)) return preferredSessionId;
            if (autoStartRequest?.pptMaterialId && data.some((item) => item.material_id === autoStartRequest.pptMaterialId)) {
              return autoStartRequest.pptMaterialId;
            }
            return data[0]?.material_id ?? null;
          });
        }
      } catch (err) {
        if (!cancelled) {
          setMaterials([]);
          setActiveMaterialId(null);
          setMaterialsError(err instanceof Error ? err.message : "课程内容加载失败");
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
  }, [course.id, selectedMaterialScope, preferredSessionId, autoStartRequest?.pptMaterialId]);

  useEffect(() => {
    let cancelled = false;

    async function loadGraph() {
      try {
        setGraphLoading(true);
        setGraphError(null);
        const data = await getKnowledgeGraph(course.id);
        if (!cancelled) {
          setGraphRoot(data.root);
        }
      } catch (err) {
        if (!cancelled) {
          setGraphRoot(null);
          setGraphError(err instanceof Error ? err.message : "知识结构加载失败");
        }
      } finally {
        if (!cancelled) {
          setGraphLoading(false);
        }
      }
    }

    void loadGraph();
    return () => {
      cancelled = true;
    };
  }, [course.id]);

  useEffect(() => {
    let cancelled = false;

    async function loadOfflinePpts() {
      try {
        setOfflinePptsLoading(true);
        setOfflinePptsError(null);
        const data = await getTeachingVideoPpts(course.id);
        if (!cancelled) {
          setOfflinePpts(data);
          setSelectedOfflinePptId((current) =>
            current && data.some((item) => item.material_id === current) ? current : (data[0]?.material_id ?? ""),
          );
        }
      } catch (err) {
        if (!cancelled) {
          setOfflinePpts([]);
          setSelectedOfflinePptId("");
          setOfflinePptsError(err instanceof Error ? err.message : "可用 PPT 列表加载失败");
        }
      } finally {
        if (!cancelled) {
          setOfflinePptsLoading(false);
        }
      }
    }

    void loadOfflinePpts();
    return () => {
      cancelled = true;
    };
  }, [course.id]);

  useEffect(() => {
    if (!structureRoot) {
      setActiveStructureId(null);
      setExpandedStructureIds(new Set());
      return;
    }

    setActiveStructureId((current) => current ?? structureRoot.id);
    setExpandedStructureIds((current) => {
      if (current.size > 0) return current;
      return new Set([structureRoot.id]);
    });
  }, [structureRoot]);

  useEffect(() => {
    const sessionId = String(activeMaterialContent.session_snapshot_id || activeMaterial?.material_id || "").trim();
    if (activeMaterial?.material_type !== "ai_lecture_session" || !sessionId) return;
    if (lastHydratedSessionIdRef.current === sessionId) return;

    lastHydratedSessionIdRef.current = sessionId;
    setAiLectureSessionId(sessionId);
    setPersistedRecordingUrl(String(activeMaterialContent.recording_url || ""));
    const sourcePptId = String(activeMaterialContent.source_ppt_material_id || "").trim();
    if (sourcePptId) {
      setSelectedOfflinePptId(sourcePptId);
    }

    void hydrateAiLectureSessionState(sessionId).catch(() => {});
  }, [
    activeMaterial?.material_id,
    activeMaterial?.material_type,
    activeMaterialContent.recording_url,
    activeMaterialContent.session_snapshot_id,
    activeMaterialContent.source_ppt_material_id,
    course.id,
  ]);

  useEffect(() => {
    if (!offlineTaskId || isOfflineTaskCompleted(offlineStatus) || isOfflineTaskFailed(offlineStatus)) return;

    const timer = window.setInterval(async () => {
      try {
        const result = await getTeachingVideoTaskStatus(course.id, offlineTaskId);
        setOfflineStatus(result.status);
        if (isOfflineTaskCompleted(result.status) && result.video_url) {
          setOfflineVideoUrl(result.video_url);
        }
        if (isOfflineTaskFailed(result.status)) {
          setError(result.error_message || "离线视频生成失败。");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "任务状态查询失败。");
      }
    }, 4000);

    return () => window.clearInterval(timer);
  }, [course.id, offlineStatus, offlineTaskId]);

  useEffect(() => {
    if (!autoStartReady || !autoStartRequest?.autoPlay || materialsLoading || autoStartAttemptedRef.current) return;

    autoStartAttemptedRef.current = true;
    setMode("online");
    const sourcePptMaterial =
      materials.find((item) => item.material_id === autoStartRequest.pptMaterialId) || selectedPptMaterial;

    void (async () => {
      try {
        await startRealtimeSession({
          sessionId: autoStartRequest.sessionId || null,
          sourcePptMaterial,
          title: autoStartRequest.pptTitle || sourcePptMaterial?.title,
        });
      } finally {
        clearStoredValue(AI_LECTURE_AUTOSTART_REQUEST_KEY);
        setAutoStartRequest(null);
      }
    })();
  }, [autoStartReady, autoStartRequest, materials, materialsLoading, selectedPptMaterial]);

  function clearAutoPlaybackTimer() {
    if (autoPlaybackTimerRef.current !== null) {
      window.clearTimeout(autoPlaybackTimerRef.current);
      autoPlaybackTimerRef.current = null;
    }
  }

  async function withBusy(name: string, action: () => Promise<void>) {
    try {
      setBusy(name);
      setError(null);
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败。");
    } finally {
      setBusy("");
    }
  }

  async function ensureAiLectureSession(params: {
    sessionId?: string | null;
    sourcePptMaterial: CourseMaterial | null;
    title?: string;
  }) {
    if (params.sessionId) {
      setAiLectureSessionId(params.sessionId);
      await hydrateAiLectureSessionState(params.sessionId);
      return params.sessionId;
    }
    if (aiLectureSessionId) {
      await hydrateAiLectureSessionState(aiLectureSessionId);
      return aiLectureSessionId;
    }
    if (!params.sourcePptMaterial?.material_id) {
      throw new Error("请先选择一个可用于实时教学的 PPT。");
    }

    const result = await createAiLectureSession(course.id, {
      source_ppt_material_id: params.sourcePptMaterial.material_id,
      title: params.title || `${params.sourcePptMaterial.title || course.title}-AI lecture session`,
    });
    const sessionId = String(result.content?.session_snapshot_id || result.material_id || "").trim();
    if (!sessionId) throw new Error("AI lecture session id was not returned.");
    setAiLectureSessionId(sessionId);
    await hydrateAiLectureSessionState(sessionId);
    return sessionId;
  }

  async function ensureAiLecturerCourse(markdown: string, sessionId: string) {
    if (courseId && outline.length) {
      return { course_id: courseId, pages: outline };
    }

    const result = await createAiLecturerCourse({
      course_name: course.title || "课程学习",
      raw_document: markdown || rawDocument,
    });
    const pages = normalizeAiLecturerPages(result.pages);
    setCourseId(result.course_id);
    setOutline(pages);
    setActiveSlideIndex(0);
    setScriptSentences([]);
    setCurrentSentence("");
    await runRealtimeStage("sync AI lecturer course snapshot", () => patchAiLectureSessionSnapshot(course.id, sessionId, {
      ai_lecturer_course_id: result.course_id,
      outline: pages,
      last_position: { page_index: 0, sentence_index: 0 },
    }));
    return { course_id: result.course_id, pages };
  }

  async function ensureSlideScript(slideIndex: number, sessionId: string, pageList: Slide[] = outlineRef.current) {
    const cached = slideScriptsRef.current[slideIndex];
    if (cached?.length) return cached;

    const slide = pageList[slideIndex];
    if (!slide) throw new Error("请先生成课程大纲。");

    const result = await generateAiLecturerScript({
      course_title: course.title || "课程学习",
      current_slide_content: slide.content,
      page_index: slideIndex,
      total_pages: pageList.length,
    });
    const sentences = result.sentences || [];
    if (!sentences.length) {
      throw new Error("AI Lecturer generate_script returned empty sentences.");
    }
    const nextScripts = { ...slideScriptsRef.current, [slideIndex]: sentences };
    setSlideScripts(nextScripts);
    setScriptSentences(sentences);
    setCurrentSentence(sentences[0] || "");
    setCurrentSentenceIndex(0);
    await patchAiLectureSessionSnapshot(course.id, sessionId, {
      script: Object.entries(nextScripts).map(([pageIndex, pageSentences]) => ({
        page_index: Number(pageIndex),
        sentences: pageSentences,
      })),
      last_position: { page_index: slideIndex, sentence_index: 0 },
    });
    return sentences;
  }

  async function speakSentence(
    sentence: string,
    sentenceIndex = 0,
    slideIndex = activeSlideIndex,
    sessionId = aiLectureSessionId,
    livetalkingSessionIdOverride?: number | null,
    options: { scheduleAutoAdvance?: boolean } = {},
  ) {
    const activeLivetalkingSessionId = livetalkingSessionIdOverride || livetalkingSessionId;
    if (!activeLivetalkingSessionId) {
      throw new Error("请先开始实时教学视频。");
    }

    clearAutoPlaybackTimer();
    await speakAiLecturerSentence({ text: sentence, session_id: activeLivetalkingSessionId });
    setCurrentSentence(sentence);
    setCurrentSentenceIndex(sentenceIndex);
    playbackPositionRef.current = { slideIndex, sentenceIndex, sessionId };
    if (sessionId) {
      await patchAiLectureSessionSnapshot(course.id, sessionId, {
        events: [{ type: "speak", page_index: slideIndex, sentence_index: sentenceIndex, text: sentence }],
        last_position: { page_index: slideIndex, sentence_index: sentenceIndex },
      });
    }
    if (options.scheduleAutoAdvance) {
      autoPlaybackTimerRef.current = window.setTimeout(() => {
        void continueAutoPlayback();
      }, estimateSpeechDurationMs(sentence));
    }
  }

  async function continueAutoPlayback() {
    const { slideIndex, sentenceIndex, sessionId } = playbackPositionRef.current;
    const sentencesOnSlide = slideScriptsRef.current[slideIndex] || (slideIndex === activeSlideIndexRef.current ? scriptSentencesRef.current : []);
    const currentSentenceIndex = sentenceIndex;
    const nextSentenceIndex = currentSentenceIndex + 1;
    const liveSessionId = livetalkingSessionIdRef.current;

    if (nextSentenceIndex < sentencesOnSlide.length) {
      await speakSentence(sentencesOnSlide[nextSentenceIndex], nextSentenceIndex, slideIndex, sessionId, liveSessionId, {
        scheduleAutoAdvance: true,
      });
      return;
    }

    const nextSlideIndex = slideIndex + 1;
    if (nextSlideIndex >= outlineRef.current.length) {
      setIsRealtimePlaying(false);
      return;
    }

    setActiveSlideIndex(nextSlideIndex);
    const sentences = await ensureSlideScript(nextSlideIndex, sessionId);
    if (sentences[0]) {
      await speakSentence(sentences[0], 0, nextSlideIndex, sessionId, liveSessionId, { scheduleAutoAdvance: true });
    }
  }

  async function startRealtimeSession(params: {
    sessionId?: string | null;
    sourcePptMaterial: CourseMaterial | null;
    title?: string;
  }) {
    setMode("online");
    const sessionId = await runRealtimeStage("ensure AI lecture session", () => ensureAiLectureSession(params));
    const markdown = params.sourcePptMaterial ? courseMaterialToMarkdown(params.sourcePptMaterial) : lectureMarkdown;
    const result = await runRealtimeStage("create AI lecturer course", () => ensureAiLecturerCourse(markdown, sessionId));
    const sentences = await runRealtimeStage("generate first slide script", () => ensureSlideScript(0, sessionId, result.pages));
    const liveSessionId = await runRealtimeStage("connect LiveTalking WebRTC", () => startWebRtc());
    if (!liveSessionId) {
      throw new Error(webRtcError || "实时视频连接失败。");
    }
    await runRealtimeStage("start AI lecture recording", () =>
      startAiLectureSessionRecording(course.id, sessionId, { livetalking_session_id: liveSessionId }),
    );
    setIsRealtimePlaying(true);
    if (sentences[0]) {
      await runRealtimeStage("speak first sentence", () =>
        speakSentence(sentences[0], 0, 0, sessionId, liveSessionId, { scheduleAutoAdvance: true }),
      );
    }
  }

  async function handleStartRealtimePlayback() {
    await withBusy("start-realtime", async () => {
      await startRealtimeSession({
        sessionId: aiLectureSessionId || null,
        sourcePptMaterial: sourcePptMaterial || selectedPptMaterial,
        title: selectedOfflinePpt?.title || selectedPptMaterial?.title || course.title,
      });
    });
  }

  async function handleCreateCourse() {
    await withBusy("create-course", async () => {
      const result = await createAiLecturerCourse({
        course_name: course.title || "课程学习",
        raw_document: lectureMarkdown || rawDocument,
      });
      const pages = normalizeAiLecturerPages(result.pages);
      setCourseId(result.course_id);
      setOutline(pages);
      setActiveSlideIndex(0);
      setScriptSentences([]);
      setCurrentSentence("");
      setAnswerText("");
    });
  }

  async function handleGenerateScript() {
    if (!aiLectureSessionId && !activeSlide) {
      setError("请先开始实时教学视频或生成课程大纲。");
      return;
    }

    await withBusy("generate-script", async () => {
      const sessionId = aiLectureSessionId || (await ensureAiLectureSession({ sourcePptMaterial: sourcePptMaterial || selectedPptMaterial }));
      const courseResult = await ensureAiLecturerCourse(lectureMarkdown, sessionId);
      await ensureSlideScript(activeSlideIndex, sessionId, courseResult.pages);
    });
  }

  async function handleSpeak(sentence: string, index = 0) {
    await withBusy("speak", async () => {
      await speakSentence(sentence, index, activeSlideIndex, aiLectureSessionId, livetalkingSessionId, {
        scheduleAutoAdvance: false,
      });
    });
  }

  async function handleStop() {
    await withBusy("stop", async () => {
      clearAutoPlaybackTimer();
      setIsRealtimePlaying(false);
      if (livetalkingSessionId) {
        await stopAiLecturerSpeaking(livetalkingSessionId);
        if (aiLectureSessionId) {
          const result = await stopAiLectureSessionRecording(course.id, aiLectureSessionId, {
            livetalking_session_id: livetalkingSessionId,
          });
          if (result.recording_url) {
            setPersistedRecordingUrl(result.recording_url);
          }
        }
      }
      stopWebRtc();
    });
  }

  async function handleInterruptAsk() {
    if (!studentQuestion.trim()) {
      setError("请输入学生实时提问内容。");
      return;
    }
    if (!livetalkingSessionId) {
      setError("请先开始实时教学视频。");
      return;
    }

    await withBusy("ask", async () => {
      const result = await askAiLecturer({
        question: studentQuestion.trim(),
        slide_context: activeSlide?.content || "",
        interrupted_sentence: currentSentence || "",
        session_id: livetalkingSessionId,
      });
      setAnswerText(result.answer || "");
      if (aiLectureSessionId) {
        await patchAiLectureSessionSnapshot(course.id, aiLectureSessionId, {
          events: [{ type: "ask", question: studentQuestion.trim(), answer: result.answer || "" }],
        });
      }
    });
  }

  async function handleGenerateOfflineVideo() {
    if (!selectedOfflinePptId) {
      setError("请先选择一个可用于生成的视频 PPT。");
      return;
    }

    await withBusy("offline", async () => {
      const result = await createTeachingVideoTask(course.id, { ppt_material_id: selectedOfflinePptId });
      setOfflineTaskId(result.task_id);
      setOfflineStatus(result.status || "processing");
      setOfflineVideoUrl(result.video_url || "");
    });
  }

  const handleExportActiveMaterial = () => {
    if (!activeMaterial || !canExportActiveMaterial) return;

    try {
      exportCourseMaterialAsWord(activeMaterial, activeMaterialMarkdown);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出失败，请稍后重试。");
    }
  };

  function toggleStructureNode(nodeId: string) {
    setExpandedStructureIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }

  function handleStructureSelect(node: KnowledgeGraphNode) {
    setActiveStructureId(node.id);
    if (materials.some((item) => item.material_id === node.id)) {
      setActiveMaterialId(node.id);
    }
  }

  function renderStructureNode(node: KnowledgeGraphNode, depth = 0): ReactNode {
    const hasChildren = Boolean(node.children?.length);
    const expanded = expandedStructureIds.has(node.id);
    const active = activeStructureId === node.id;
    const isRootNode = depth === 0;
    const isBranchNode = depth === 1;

    return (
      <div key={node.id} className="space-y-2" style={{ marginLeft: depth > 0 ? `${depth * 12}px` : "0px" }}>
        <div
          className={`relative transition ${
            isRootNode
              ? "rounded-[18px] border px-3.5 py-3.5"
              : isBranchNode
                ? "rounded-[16px] border px-3.5 py-3"
                : "rounded-[12px] border px-3 py-2.5"
          } ${
            active
              ? "border-[var(--accent-border)] bg-[var(--accent-soft)] shadow-[0_12px_24px_var(--accent-shadow)]"
              : "border-[var(--shell-border)] bg-white hover:border-[rgba(37,99,235,0.24)] hover:bg-[rgba(248,250,255,0.96)]"
          }`}
        >
          {active ? <span className="absolute inset-y-3 left-0 w-1 rounded-full bg-[var(--accent)]" /> : null}

          <div className="flex items-start gap-2.5">
            {hasChildren ? (
              <button
                type="button"
                onClick={() => toggleStructureNode(node.id)}
                className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full border border-[var(--shell-border)] bg-[var(--surface-elevated)] text-[var(--accent-strong)]"
              >
                <MaterialIcon name={expanded ? "expand_less" : "expand_more"} className="text-[13px]" />
              </button>
            ) : (
              <div className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[rgba(37,99,235,0.08)] text-[var(--accent-strong)]">
                <span className="h-2 w-2 rounded-full bg-current" />
              </div>
            )}

            <button type="button" onClick={() => handleStructureSelect(node)} className="min-w-0 flex-1 text-left">
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-[rgba(37,99,235,0.08)] px-2 py-0.5 text-[9px] font-bold tracking-[0.1em] text-[var(--accent-strong)]">
                  {nodeTypeLabel(node)}
                </span>
              </div>
              <p
                className={`${
                  isRootNode ? "mt-1.5 text-[15px]" : isBranchNode ? "mt-1 text-[13.5px]" : "mt-1 text-[13px]"
                } font-bold leading-5 text-[var(--app-text)]`}
              >
                {node.label}
              </p>
              {shouldShowStructureSummary(node) ? (
                <p className="mt-0.5 text-[11px] leading-4 text-[var(--muted-text)]">{node.data?.summary}</p>
              ) : null}
            </button>
          </div>
        </div>

        {hasChildren && expanded ? (
          <div className="relative ml-2.5 space-y-2 border-l border-[rgba(37,99,235,0.12)] pl-2.5">
            {node.children!.map((child) => renderStructureNode(child, depth + 1))}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <AppSurface className="flex h-screen overflow-hidden">
      <SidebarDock className="h-screen gap-6 overflow-hidden bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="px-2 py-4">
          <SidebarBackLink />
          <h2 className="text-xl font-extrabold tracking-tight text-[var(--accent-strong)]">{course.title}</h2>
          <p className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--muted-text)]">课程学习</p>
        </div>
        <SidebarNav activeRoute={routes.video} />
      </SidebarDock>

      <div className="grid min-w-0 flex-1 gap-6 overflow-hidden p-6 lg:grid-cols-[360px_minmax(0,1fr)_380px]">
        <aside className="overflow-hidden rounded-[32px] border border-[var(--shell-border)] bg-[var(--panel-surface)] shadow-[0_16px_32px_var(--panel-shadow)] lg:h-[calc(100vh-48px)]">
          <div className="border-b border-[var(--shell-border)] bg-[var(--surface-elevated)]/92 p-6 backdrop-blur-xl">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">课程学习</p>
            <h3 className="mt-2 text-2xl font-black text-[var(--accent-strong)]">知识结构列表</h3>
          </div>

          <div className="space-y-5 overflow-y-auto p-5 lg:h-[calc(100vh-196px)]">
            <div className="rounded-[24px] border border-[var(--shell-border)] bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-[var(--accent-strong)]">学习路径</p>
                  <p className="mt-1 text-xs text-[var(--muted-text)]">
                    {graphRoot ? "当前结构直接来自知识图谱。" : "知识图谱不可用时，自动回退为课程内容列表。"}
                  </p>
                </div>
                <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">
                  {structureNodeCount} nodes
                </span>
              </div>

              <div className="mt-4 space-y-2.5">
                {graphLoading ? (
                  <div className="rounded-[18px] bg-[var(--surface-subtle)] px-4 py-4 text-sm text-[var(--muted-text)]">
                    正在加载知识结构...
                  </div>
                ) : structureRoot ? (
                  renderStructureNode(structureRoot)
                ) : (
                  <div className="rounded-[18px] bg-[var(--surface-subtle)] px-4 py-4 text-sm text-[var(--muted-text)]">
                    {graphError || "当前课程还没有可显示的知识结构。"}
                  </div>
                )}
              </div>
            </div>
          </div>
        </aside>

        <main
          ref={pageMainScrollRef}
          data-route-scroll-root
          className="min-w-0 overflow-y-auto rounded-[32px] border border-[var(--shell-border)] bg-[var(--app-bg)] [overflow-anchor:none] lg:h-[calc(100vh-48px)]"
        >
          <header className="sticky top-0 z-40 border-b border-[var(--shell-border)] bg-[var(--app-bg)]/88 px-8 py-4 backdrop-blur-xl">
            <h1 className="text-xl font-extrabold tracking-tight text-[var(--accent-strong)]">课程学习</h1>
            <p className="mt-1 text-sm text-[var(--muted-text)]">
              {mode === "online"
                ? "在线学习模式：开始实时教学视频、生成讲稿、学生提问与课程内容联动。"
                : "离线生成模式：根据已生成 PPT 批量生成完整课程视频。"}
            </p>
          </header>

          <div className="w-full px-6 py-6 xl:px-8">
            <GlassPanel className="overflow-hidden bg-[#020617]">
              {mode === "online" ? (
                <div ref={realtimeStageFrameRef} className="relative aspect-video w-full overflow-hidden bg-black">
                  {realtimeStageSlideObjectUrl ? (
                    <img
                      src={realtimeStageSlideObjectUrl}
                      alt={`${selectedPptMaterial?.title || sourcePptMaterial?.title || course.title} slide ${activeSlideIndex + 1}`}
                      className="absolute inset-0 h-full w-full object-contain bg-white"
                    />
                  ) : realtimeStagePptPreviewUrl ? (
                    <div
                      className="pointer-events-none absolute inset-0 overflow-hidden bg-white"
                      style={{ contain: "layout paint size" }}
                    >
                      <iframe
                        ref={realtimeStagePptFrameRef}
                        src={realtimeStagePptPreviewUrl}
                        onLoad={() => syncRealtimeStagePptSlide(activeSlideIndex)}
                        title={`${selectedPptMaterial?.title || sourcePptMaterial?.title || course.title} slide ${activeSlideIndex + 1}`}
                        style={{
                          width: `${PPT_PREVIEW_BASE_WIDTH}px`,
                          height: `calc(100% / ${realtimeStagePptScale})`,
                          minHeight: `${Math.round(1080 / Math.max(realtimeStagePptScale, 0.1))}px`,
                          border: 0,
                          background: "#fff",
                          transform: `scale(${realtimeStagePptScale})`,
                          transformOrigin: "top left",
                        }}
                      />
                    </div>
                  ) : (
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(96,165,250,0.32),transparent_24%),radial-gradient(circle_at_75%_58%,rgba(14,165,233,0.22),transparent_30%),linear-gradient(135deg,#020617_0%,#0f172a_45%,#1d4ed8_100%)]" />
                  )}
                  <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(2,6,23,0.08)_0%,rgba(2,6,23,0.12)_52%,rgba(2,6,23,0.42)_100%)]" />
                  {outline.length ? (
                    <div className="absolute left-5 top-5 z-10 rounded-full bg-[rgba(15,23,42,0.72)] px-4 py-2 text-xs font-bold uppercase tracking-[0.18em] text-white/92 backdrop-blur">
                      Slide {activeSlideIndex + 1}/{outline.length}
                    </div>
                  ) : null}
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className="hidden"
                  />
                  <TransparentAvatarCanvas
                    sourceVideoRef={videoRef}
                    className="pointer-events-none absolute bottom-[2%] right-[1.8%] z-20 block h-auto w-[24%] min-w-[180px] max-w-[320px] object-contain drop-shadow-[0_18px_36px_rgba(15,23,42,0.34)]"
                  />
                  <audio ref={audioRef} autoPlay className="hidden" />
                  {webRtcStatus !== "connected" ? (
                    <div className="absolute inset-0 z-30 grid place-items-center bg-[linear-gradient(135deg,rgba(2,6,23,0.92),rgba(15,23,42,0.78))] p-8 text-center">
                      <div className="max-w-md">
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-200">Live teaching</p>
                        <h2 className="mt-3 text-3xl font-black text-white">实时教学视频待开始</h2>
                        <p className="mt-3 text-sm leading-7 text-blue-100">
                          创建视频任务后，点击开始即可连接数字人课堂、生成当前页讲稿并自动播报。
                        </p>
                        <button
                          type="button"
                          onClick={() => void handleStartRealtimePlayback()}
                          disabled={busy === "start-realtime" || webRtcStatus === "connecting"}
                          className="mt-6 inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-bold text-slate-950 disabled:opacity-60"
                        >
                          <MaterialIcon name="play_arrow" className="text-base" />
                          {busy === "start-realtime" || webRtcStatus === "connecting" ? "正在开始..." : "开始实时教学"}
                        </button>
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
                      <h2 className="text-2xl font-black text-[var(--accent-strong)]">当前讲解</h2>
                      <p className="mt-1 text-xs text-[var(--muted-text)]">
                        {webRtcStatus === "connected" ? `LiveTalking session ${livetalkingSessionId || "--"}` : "尚未连接实时课堂"}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => void handleStartRealtimePlayback()}
                        disabled={busy === "start-realtime" || webRtcStatus === "connecting"}
                        className="rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                      >
                        {isRealtimePlaying ? "继续实时教学" : "开始实时教学"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleGenerateScript()}
                        disabled={busy === "generate-script"}
                        className="rounded-full border border-[var(--shell-border)] bg-white px-4 py-3 text-sm font-bold text-[var(--accent-strong)] disabled:opacity-60"
                      >
                        {busy === "generate-script" ? "生成中..." : "生成当前页讲稿"}
                      </button>
                    </div>
                  </div>
                  <div className="mt-4 rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4">
                    <p className="text-sm font-bold text-[var(--accent-strong)]">{activeSlide ? activeSlide.title : "未选择页面"}</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--muted-text)]">
                      {activeSlide?.content || "点击开始实时教学后，系统会先根据 PPT/课程内容生成课程大纲。"}
                    </p>
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
                        <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">讲稿句子 {index + 1}</p>
                        <p className="mt-2 text-sm leading-7 text-[var(--app-text)]">{sentence}</p>
                      </button>
                    ))}
                    {!scriptSentences.length ? <div className="text-sm text-[var(--muted-text)]">当前还没有生成讲稿。</div> : null}
                  </div>
                </GlassPanel>

                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <h2 className="text-2xl font-black text-[var(--accent-strong)]">课堂问答</h2>
                  <textarea
                    value={studentQuestion}
                    onChange={(event) => setStudentQuestion(event.target.value)}
                    className="mt-4 min-h-[140px] w-full rounded-[20px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4 text-sm outline-none"
                    placeholder="输入学生实时提问..."
                  />
                  <div className="mt-4 flex gap-3">
                    <button
                      type="button"
                      onClick={() => void handleStop()}
                      disabled={busy === "stop"}
                      className="flex-1 rounded-full border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-bold text-rose-600 disabled:opacity-60"
                    >
                      {busy === "stop" ? "停止中..." : "停止并保存录制"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleInterruptAsk()}
                      disabled={busy === "ask"}
                      className="flex-1 rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                    >
                      {busy === "ask" ? "回答中..." : "提交提问"}
                    </button>
                  </div>
                  <div className="mt-5 rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4">
                    <p className="text-sm font-bold text-[var(--accent-strong)]">AI 回答</p>
                    <div className="mt-3 text-sm leading-7 text-[var(--muted-text)]">
                      <MarkdownPreview content={answerText || "学生提问后，回答会显示在这里。"} />
                    </div>
                  </div>
                  {persistedRecordingUrl ? (
                    <div className="mt-5 rounded-[22px] border border-[var(--shell-border)] bg-white p-4">
                      <p className="text-sm font-bold text-[var(--accent-strong)]">录制回看</p>
                      <video controls preload="metadata" className="mt-3 aspect-video w-full rounded-[18px] bg-black" src={playbackUrl(persistedRecordingUrl)} />
                    </div>
                  ) : null}
                </GlassPanel>
              </section>
            ) : (
              <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_1fr]">
                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <h2 className="text-2xl font-black text-[var(--accent-strong)]">离线整课视频生成</h2>
                  <p className="mt-3 text-sm leading-7 text-[var(--muted-text)]">
                    选择课程里已经生成完成的 PPT，前端会通过课程后端提交视频任务；PPT 图片、讲稿素材和本地路径都由后端统一处理。
                  </p>
                  <div className="mt-4 rounded-[20px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4">
                    {offlinePptsLoading ? (
                      <p className="text-sm text-[var(--muted-text)]">正在加载可用 PPT...</p>
                    ) : offlinePptsError ? (
                      <p className="text-sm text-rose-600">{offlinePptsError}</p>
                    ) : offlinePpts.length === 0 ? (
                      <p className="text-sm text-[var(--muted-text)]">当前课程还没有可用于生成教学视频的 PPT，请先在 PPT 工作坊完成课件生成。</p>
                    ) : (
                      <div className="space-y-3">
                        <label className="text-xs font-black uppercase tracking-[0.16em] text-[var(--accent-strong)]">Select PPT</label>
                        <select
                          value={selectedOfflinePptId}
                          onChange={(event) => setSelectedOfflinePptId(event.target.value)}
                          className="h-12 w-full rounded-[16px] border border-[var(--shell-border)] bg-white px-4 text-sm font-semibold text-[var(--app-text)] outline-none"
                        >
                          {offlinePpts.map((item) => (
                            <option key={item.material_id} value={item.material_id}>
                              {item.title}
                            </option>
                          ))}
                        </select>
                        <p className="text-xs leading-6 text-[var(--muted-text)]">
                          {selectedOfflinePpt
                            ? `已选择：${selectedOfflinePpt.title}${selectedOfflinePpt.slide_count ? `，共 ${selectedOfflinePpt.slide_count} 页` : ""}`
                            : "请选择一个 PPT"}
                        </p>
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleGenerateOfflineVideo()}
                    disabled={busy === "offline" || offlinePptsLoading || !selectedOfflinePptId}
                    className="mt-4 w-full rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                  >
                    {busy === "offline" ? "提交中..." : "提交整套课件渲染任务"}
                  </button>
                </GlassPanel>

                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <h2 className="text-2xl font-black text-[var(--accent-strong)]">任务状态</h2>
                  <div className="mt-4 space-y-3 text-sm text-[var(--muted-text)]">
                    <p>任务 ID：{offlineTaskId || "--"}</p>
                    <p>当前状态：{offlineStatus || "--"}</p>
                    <p>视频地址：{offlineVideoUrl || "--"}</p>
                  </div>
                  {offlineVideoUrl ? (
                    <div className="mt-5 flex gap-3">
                      <a
                        href={offlineVideoUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-1 rounded-full border border-[var(--shell-border)] bg-white px-4 py-3 text-center text-sm font-bold text-[var(--accent-strong)]"
                      >
                        在线预览
                      </a>
                      <a
                        href={getAiLecturerDownloadUrl(fileNameFromUrl(offlineVideoUrl))}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-1 rounded-full bg-[var(--accent)] px-4 py-3 text-center text-sm font-bold text-white"
                      >
                        下载视频
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
                    <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">Course Content</p>
                    <h2 className="mt-2 text-2xl font-black text-[var(--accent-strong)]">课程内容</h2>
                    <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--muted-text)]">
                      学习视频下方保留课程内容预览区，便于在课程学习过程中对照讲义、资料与文本内容。
                    </p>
                  </div>
                  <div className="rounded-[20px] border border-[var(--accent-border)] bg-[var(--accent-soft)] px-4 py-3 text-sm font-semibold text-[var(--accent-strong)]">
                    {materialsLoading ? "加载中..." : `共 ${materials.length} 份内容`}
                  </div>
                </div>

                <div className="mt-6 grid gap-6 xl:h-[min(72vh,760px)] xl:min-h-0 xl:grid-cols-[340px_minmax(0,1fr)]">
                  <div className="min-h-0 overflow-y-auto pr-2">
                    <div className="space-y-3">
                    {materialsLoading ? (
                      <div className="rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] px-4 py-5 text-sm text-[var(--muted-text)]">
                        正在加载课程内容...
                      </div>
                    ) : materialsError ? (
                      <div className="rounded-[22px] border border-rose-200 bg-rose-50 px-4 py-5 text-sm text-rose-600">
                        {materialsError}
                      </div>
                    ) : materials.length === 0 ? (
                      <div className="rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] px-4 py-5 text-sm text-[var(--muted-text)]">
                        当前课程还没有可展示的内容。
                      </div>
                    ) : (
                      materials.map((item, index) => {
                        const active = item.material_id === activeMaterial?.material_id;

                        return (
                          <button
                            key={item.material_id}
                            type="button"
                            onClick={() => setActiveMaterialId(item.material_id)}
                            className={`w-full rounded-[22px] border px-4 py-4 text-left transition ${
                              active
                                ? "border-[var(--accent-border)] bg-[var(--accent-soft)] shadow-[0_14px_28px_var(--accent-shadow)]"
                                : "border-[var(--shell-border)] bg-[var(--surface-subtle)] hover:border-[var(--accent-border)] hover:bg-white"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--muted-text)]">
                                  第 {index + 1} 项 · {item.material_type || "content"}
                                </p>
                                <h3 className="mt-2 truncate text-sm font-bold text-[var(--app-text)]">
                                  {item.title || item.topic || item.material_id}
                                </h3>
                                <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--muted-text)]">
                                  {item.summary || "点击查看当前内容详情。"}
                                </p>
                              </div>
                              {item.is_pinned ? (
                                <span className="rounded-full bg-white px-3 py-1 text-[10px] font-bold text-[var(--accent-strong)]">置顶</span>
                              ) : null}
                            </div>
                          </button>
                        );
                      })
                    )}
                    </div>
                  </div>

                  <div className="flex min-h-0 min-w-0 flex-col rounded-[24px] border border-[var(--shell-border)] bg-white/88 p-5">
                    {activeMaterial ? (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--shell-border)] pb-4">
                          <div>
                            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">
                              {activeMaterial.material_type || "content"}
                            </p>
                            <h3 className="mt-2 text-2xl font-black text-[var(--accent-strong)]">
                              {activeMaterial.title || activeMaterial.topic || activeMaterial.material_id}
                            </h3>
                          </div>
                          <div className="flex flex-wrap items-center gap-3">
                            <div className="rounded-full border border-[var(--shell-border)] bg-[var(--surface-subtle)] px-3 py-2 text-xs font-semibold text-[var(--muted-text)]">
                              {course.title}
                            </div>
                            {canExportActiveMaterial ? (
                              <button
                                type="button"
                                onClick={handleExportActiveMaterial}
                                className="rounded-full border border-[var(--accent-border)] bg-[var(--accent-soft)] px-4 py-2 text-xs font-bold text-[var(--accent-strong)] transition hover:bg-white"
                              >
                                导出 DOC
                              </button>
                            ) : null}
                            {activeMaterialPptExportUrl ? (
                              <button
                                type="button"
                                onClick={() => window.open(activeMaterialPptExportUrl, "_blank", "noopener,noreferrer")}
                                className="rounded-full border border-[var(--accent-border)] bg-[var(--accent-soft)] px-4 py-2 text-xs font-bold text-[var(--accent-strong)] transition hover:bg-white"
                              >
                                导出 PPT
                              </button>
                            ) : null}
                          </div>
                        </div>
                        <div className="mt-5 min-h-0 flex-1 overflow-y-auto pr-2">
                          {activeMaterialPptPreviewUrl ? (
                            <div
                              ref={pptPreviewFrameRef}
                              className="h-full min-h-[620px] overflow-auto rounded-[20px] border border-[var(--shell-border)] bg-[#f8fafc] shadow-[0_18px_36px_rgba(15,23,42,0.08)]"
                            >
                              <iframe
                                src={activeMaterialPptPreviewUrl}
                                title={activeMaterial.title || activeMaterial.topic || activeMaterial.material_id}
                                style={{
                                  width: `${PPT_PREVIEW_BASE_WIDTH}px`,
                                  height: `calc(100% / ${pptPreviewScale})`,
                                  minHeight: `${Math.round(620 / Math.max(pptPreviewScale, 0.1))}px`,
                                  border: 0,
                                  background: "#fff",
                                  transform: `scale(${pptPreviewScale})`,
                                  transformOrigin: "top left",
                                }}
                              />
                            </div>
                          ) : (
                            <MarkdownPreview content={activeMaterialMarkdown} />
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="rounded-[20px] bg-[var(--surface-subtle)] px-4 py-5 text-sm text-[var(--muted-text)]">
                        选择左侧一项内容后，会在这里显示完整预览。
                      </div>
                    )}
                  </div>
                </div>
              </GlassPanel>
            </section>

            {error || webRtcError ? (
              <div className="mt-6 rounded-[22px] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-600">
                {error || webRtcError}
              </div>
            ) : null}
          </div>
        </main>

        <aside className="flex flex-col overflow-hidden rounded-[32px] border border-[var(--shell-border)] bg-[linear-gradient(180deg,rgba(246,249,255,0.94)_0%,rgba(239,245,253,0.96)_100%)] shadow-[0_16px_32px_var(--panel-shadow)] lg:h-[calc(100vh-48px)] lg:overflow-auto">
          <div className="border-b border-[var(--shell-border)] bg-[var(--surface-elevated)]/95 p-6 backdrop-blur-xl">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[var(--accent)] text-white">
                <MaterialIcon name="school" className="text-lg" />
              </div>
              <div>
                <h4 className="font-bold text-[var(--accent-strong)]">学习概览</h4>
                <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-[#1b6d24]">实时联动</p>
              </div>
            </div>
          </div>

          <div className="flex flex-1 flex-col gap-6 overflow-hidden p-6">
            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5 shadow-[0_14px_28px_rgba(15,23,42,0.05)]">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">学习状态</p>
              <div className="mt-4 space-y-3 text-sm text-[var(--muted-text)]">
                <p>{learningSummary}</p>
                <p>课程 ID：{courseId || "--"}</p>
                <p>AI 会话：{aiLectureSessionId || "--"}</p>
                <p>LiveTalking：{livetalkingSessionId || "--"}</p>
                <p>当前结构节点：{activeStructureNode?.label || "--"}</p>
                <p>当前播报句子：{currentSentence || "--"}</p>
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5 shadow-[0_14px_28px_rgba(15,23,42,0.05)]">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">节点说明</p>
              <div className="mt-4 rounded-[18px] bg-[var(--surface-subtle)] p-4 text-sm leading-7 text-[var(--muted-text)]">
                {activeStructureNode?.data?.summary || "选择左侧知识结构节点后，这里会显示当前节点摘要。"}
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5 shadow-[0_14px_28px_rgba(15,23,42,0.05)]">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">快速跳转</p>
              <div className="mt-4 space-y-3">
                <button
                  type="button"
                  onClick={() => document.getElementById("course-materials")?.scrollIntoView({ behavior: "smooth", block: "start" })}
                  className="flex w-full items-center justify-between rounded-[18px] bg-[var(--surface-subtle)] px-4 py-3 text-left transition hover:bg-[var(--accent-soft)]"
                >
                  <span className="text-sm font-semibold text-[var(--app-text)]">课程内容</span>
                  <MaterialIcon name="arrow_forward" className="text-[var(--accent)]" />
                </button>
                <a
                  href={routeHref(routes.ai)}
                  className="flex items-center justify-between rounded-[18px] bg-[var(--surface-subtle)] px-4 py-3 text-left transition hover:bg-[var(--accent-soft)]"
                >
                  <span className="text-sm font-semibold text-[var(--app-text)]">问答工作台</span>
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
