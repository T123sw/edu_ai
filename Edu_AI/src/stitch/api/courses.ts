import { apiRequest } from "./client";
import type {
  BackendCourse,
  CourseMaterial,
  KnowledgeBaseDocument,
  KnowledgeBaseScopeOptions,
  KnowledgeGraphData,
  KnowledgeGraphTextbookImportResponse,
  AiLectureRecordingResponse,
  AiLectureSessionDetailResponse,
  AiLectureSessionMaterialResponse,
  AiLectureSessionSnapshot,
  TeachingVideoPptItem,
  TeachingVideoTaskResponse,
} from "./types";
import type { CourseSummary } from "../shared";

const accentPalette = [
  "from-[#0f172a] via-[#1d4ed8] to-[#60a5fa]",
  "from-[#134e4a] via-[#0f766e] to-[#5eead4]",
  "from-[#3f1d4d] via-[#9333ea] to-[#f0abfc]",
  "from-[#7c2d12] via-[#ea580c] to-[#fdba74]",
  "from-[#1f2937] via-[#2563eb] to-[#93c5fd]",
  "from-[#4c0519] via-[#be123c] to-[#fda4af]",
];

const courseImages = [
  "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?auto=format&fit=crop&w=1200&q=80",
  "https://images.unsplash.com/photo-1509228627152-72ae9ae6848d?auto=format&fit=crop&w=1200&q=80",
  "https://images.unsplash.com/photo-1530026405186-ed1f139313f8?auto=format&fit=crop&w=1200&q=80",
  "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80",
  "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=1200&q=80",
  "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80",
];

type CourseMaterialsScopeOptions = {
  materialType?: string;
  scopeType?: "course" | "knowledge_point";
  scopeId?: string;
  aggregate?: boolean;
  limit?: number;
  offset?: number;
};

export function backendCourseToSummary(course: BackendCourse, index = 0): CourseSummary {
  const accent = accentPalette[index % accentPalette.length];
  const persistedImage =
    typeof course.knowledgeGraph === "string" && /^(https?:\/\/|data:image\/)/i.test(course.knowledgeGraph.trim())
      ? course.knowledgeGraph.trim()
      : "";
  const image = persistedImage || courseImages[index % courseImages.length];
  const progressSeed = course.id.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);

  return {
    id: course.id,
    module: `Module ${(index % 8) + 1}`,
    title: course.title,
    uppercaseTitle: course.title.toUpperCase(),
    instructor: "Edu AI Teacher",
    progress: 20 + (progressSeed % 70),
    image,
    accent,
    summary: course.description,
  };
}

export function listCourses() {
  return apiRequest<BackendCourse[]>("/api/courses");
}

export function getCourse(courseId: string) {
  return apiRequest<BackendCourse>(`/api/courses/${courseId}`);
}

export function getCourseMaterials(courseId: string, options?: CourseMaterialsScopeOptions) {
  const params = new URLSearchParams();

  if (options?.materialType) params.set("material_type", options.materialType);
  if (options?.scopeType) params.set("scope_type", options.scopeType);
  if (options?.scopeId) params.set("scope_id", options.scopeId);
  if (typeof options?.aggregate === "boolean") params.set("aggregate", options.aggregate ? "true" : "false");
  if (typeof options?.limit === "number") params.set("limit", String(options.limit));
  if (typeof options?.offset === "number") params.set("offset", String(options.offset));

  const search = params.toString();
  return apiRequest<CourseMaterial[]>(`/api/courses/${courseId}/materials${search ? `?${search}` : ""}`);
}

export function getTeachingVideoPpts(courseId: string) {
  return apiRequest<TeachingVideoPptItem[]>(`/api/courses/${courseId}/teaching-videos/ppts`);
}

export function createTeachingVideoTask(courseId: string, payload: { ppt_material_id: string }) {
  return apiRequest<TeachingVideoTaskResponse>(`/api/courses/${courseId}/teaching-videos`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTeachingVideoTaskStatus(courseId: string, taskId: string) {
  return apiRequest<TeachingVideoTaskResponse>(`/api/courses/${courseId}/teaching-videos/tasks/${taskId}`);
}

export function createAiLectureSession(courseId: string, payload: { source_ppt_material_id: string; title?: string }) {
  return apiRequest<AiLectureSessionMaterialResponse>(`/api/courses/${courseId}/lecture-sessions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAiLectureSession(courseId: string, sessionId: string) {
  return apiRequest<AiLectureSessionDetailResponse>(`/api/courses/${courseId}/lecture-sessions/${sessionId}`);
}

export function patchAiLectureSessionSnapshot(
  courseId: string,
  sessionId: string,
  payload: Partial<AiLectureSessionSnapshot>,
) {
  return apiRequest<AiLectureSessionSnapshot>(`/api/courses/${courseId}/lecture-sessions/${sessionId}/snapshot`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function startAiLectureSessionRecording(
  courseId: string,
  sessionId: string,
  payload: { livetalking_session_id: number },
) {
  return apiRequest<AiLectureRecordingResponse>(`/api/courses/${courseId}/lecture-sessions/${sessionId}/recording/start`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function stopAiLectureSessionRecording(
  courseId: string,
  sessionId: string,
  payload: { livetalking_session_id: number },
) {
  return apiRequest<AiLectureRecordingResponse>(`/api/courses/${courseId}/lecture-sessions/${sessionId}/recording/stop`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getKnowledgeBaseDocuments(courseId: string, options?: KnowledgeBaseScopeOptions) {
  const params = new URLSearchParams();

  if (options?.scopeType) params.set("scope_type", options.scopeType);
  if (options?.scopeId) params.set("scope_id", options.scopeId);
  if (typeof options?.aggregate === "boolean") params.set("aggregate", options.aggregate ? "true" : "false");
  if (options?.libraryType) params.set("library_type", options.libraryType);
  if (typeof options?.includeDescendants === "boolean") {
    params.set("include_descendants", options.includeDescendants ? "true" : "false");
  }
  if (typeof options?.limit === "number") params.set("limit", String(options.limit));
  if (typeof options?.offset === "number") params.set("offset", String(options.offset));

  const search = params.toString();
  const path = search
    ? `/api/courses/${courseId}/knowledge-base/documents?${search}`
    : `/api/courses/${courseId}/knowledge-base/documents`;

  return apiRequest<KnowledgeBaseDocument[]>(path);
}

export function uploadKnowledgeBaseDocument(courseId: string, file: File, options?: KnowledgeBaseScopeOptions) {
  const formData = new FormData();
  formData.append("file", file);
  if (options?.scopeType) formData.append("scope_type", options.scopeType);
  if (options?.scopeId) formData.append("scope_id", options.scopeId);
  if (options?.libraryType) formData.append("library_type", options.libraryType);

  return apiRequest<KnowledgeBaseDocument>(`/api/courses/${courseId}/knowledge-base/documents`, {
    method: "POST",
    body: formData,
  });
}

export function getKnowledgeGraph(courseId: string) {
  return apiRequest<KnowledgeGraphData>(`/api/courses/${courseId}/knowledge-graph`);
}

export function saveKnowledgeGraph(courseId: string, payload: KnowledgeGraphData) {
  return apiRequest<KnowledgeGraphData>(`/api/courses/${courseId}/knowledge-graph`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function importKnowledgeGraphTextbook(courseId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);

  return apiRequest<KnowledgeGraphTextbookImportResponse>(`/api/courses/${courseId}/knowledge-graph/textbook-import`, {
    method: "POST",
    body: formData,
  });
}

function hasTextContent(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function toPlainRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function textFromUnknown(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}

function extractDirectMaterialMarkdown(material: CourseMaterial): string {
  if (hasTextContent(material.final_markdown)) return material.final_markdown;
  if (hasTextContent(material.content)) return material.content;

  const record = toPlainRecord(material.content);
  const candidates = [
    record.content_markdown,
    record.markdown,
    record.report,
    record.report_content,
    record.content,
    record.text,
  ];

  for (const candidate of candidates) {
    if (hasTextContent(candidate)) return candidate;
  }

  return "";
}

function formatPptDeckMarkdown(material: CourseMaterial): string {
  const record = toPlainRecord(material.content);
  const deckTitle = textFromUnknown(record.deck_title) || textFromUnknown(record.title) || material.title || material.material_id;
  const slides = Array.isArray(record.slides) ? record.slides : [];

  const slideMarkdown = slides
    .map((slide, index) => {
      const slideRecord = toPlainRecord(slide);
      const title = textFromUnknown(slideRecord.title) || `Slide ${index + 1}`;
      const bullets = Array.isArray(slideRecord.bullets)
        ? slideRecord.bullets.map((item) => textFromUnknown(item)).filter(Boolean)
        : [];
      const notes = textFromUnknown(slideRecord.notes) || textFromUnknown(slideRecord.content);
      const bulletText = bullets.length > 0 ? bullets.map((item) => `- ${item}`).join("\n") : "";
      return [`## ${title}`, bulletText, notes].filter(Boolean).join("\n\n");
    })
    .filter(Boolean)
    .join("\n\n");

  return [`# ${deckTitle}`, material.summary || "", slideMarkdown || "当前 PPT 暂无可展示的页面内容。"]
    .filter(Boolean)
    .join("\n\n");
}

export function courseMaterialToMarkdown(material: CourseMaterial) {
  const directMarkdown = extractDirectMaterialMarkdown(material);
  if (directMarkdown) return directMarkdown;

  if (material.material_type === "ppt") {
    return formatPptDeckMarkdown(material);
  }

  if (material.material_type === "report" && Array.isArray(material.mainContent)) {
    const body = material.mainContent
      .map((section) => `## ${section.title || "章节"}\n\n${section.content || ""}`)
      .join("\n\n");
    return `# ${material.title || "报告"}\n\n${material.summary || ""}\n\n${body}`;
  }

  if (material.material_type === "blog" && Array.isArray(material.outline)) {
    const body = material.outline
      .map((section) => {
        const children = Array.isArray(section.children) ? section.children : [];
        const childText = children
          .map((child) => {
            const concepts = Array.isArray(child.key_concepts)
              ? child.key_concepts.map((item) => `- ${item}`).join("\n")
              : "";
            return `### ${child.title || "小节"}\n\n${concepts}`;
          })
          .join("\n\n");
        return `## ${section.title || "章节"}\n\n${childText}`;
      })
      .join("\n\n");
    return `# ${material.title || material.topic || "教学博客"}\n\n${body}`;
  }

  return `# ${material.title || material.material_id}\n\n当前资源暂无可直接渲染的 Markdown 内容。`;
}
