import { apiRequest } from "./client";
import type {
  BackendCourse,
  BackendCourseCreatePayload,
  CourseMember,
  CourseMaterial,
  CourseMaterialSpace,
  CourseKnowledgeBuild,
  CourseKnowledgeBuildConfig,
  CourseKnowledgeTextbookInput,
  CourseKnowledgeGraphVersion,
  KnowledgeBaseDocument,
  KnowledgeBaseDocumentContent,
  KnowledgeBaseScopeOptions,
  KnowledgeGraphData,
  KnowledgeGraphNode,
  KnowledgeGraphTextbookImportResponse,
  MaterialPublicationResponse,
} from "./types";
import type { CourseSummary } from "../shared";
import type { JobRecord } from "../../jobs/types";
import {
  type CourseMaterialPage,
  unwrapCourseMaterials,
} from "./courseMaterialsResponse";

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
  space?: CourseMaterialSpace | "all";
  sort?: "updated_desc" | "updated_asc" | "name_asc" | "name_desc";
};

export function backendCourseToSummary(course: BackendCourse, index = 0): CourseSummary {
  const accent = accentPalette[index % accentPalette.length];
  const persistedImage =
    typeof course.knowledgeGraph === "string" && /^(https?:\/\/|data:image\/)/i.test(course.knowledgeGraph.trim())
      ? course.knowledgeGraph.trim()
      : "";
  const image = persistedImage || courseImages[index % courseImages.length];

  return {
    id: course.id,
    module: `Module ${(index % 8) + 1}`,
    title: course.title,
    uppercaseTitle: course.title.toUpperCase(),
    instructor: "Edu AI Teacher",
    // Legacy presentation field; course cards and overview use factual counters.
    progress: 0,
    image,
    accent,
    summary: course.description,
  };
}

export function listCourses() {
  return apiRequest<BackendCourse[]>("/api/courses");
}

export function createCourse(payload: BackendCourseCreatePayload) {
  return apiRequest<BackendCourse>("/api/courses", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function joinCourseByCode(courseCode: string) {
  return apiRequest<BackendCourse>("/api/courses/join", {
    method: "POST",
    body: JSON.stringify({ course_code: courseCode }),
  });
}

export function listCourseMembers(courseId: string) {
  return apiRequest<{ items: CourseMember[] }>(
    `/api/courses/${encodeURIComponent(courseId)}/members`,
  ).then((response) => response.items);
}

export function addCourseMember(
  courseId: string,
  payload: Pick<CourseMember, "user_id" | "role">,
) {
  return apiRequest<CourseMember>(
    `/api/courses/${encodeURIComponent(courseId)}/members`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function updateCourseMember(
  courseId: string,
  userId: string,
  role: CourseMember["role"],
) {
  return apiRequest<CourseMember>(
    `/api/courses/${encodeURIComponent(courseId)}/members/${encodeURIComponent(userId)}`,
    { method: "PATCH", body: JSON.stringify({ role }) },
  );
}

export function removeCourseMember(courseId: string, userId: string) {
  return apiRequest<{ ok: boolean }>(
    `/api/courses/${encodeURIComponent(courseId)}/members/${encodeURIComponent(userId)}`,
    { method: "DELETE" },
  );
}

export function getCourse(courseId: string) {
  return apiRequest<BackendCourse>(`/api/courses/${courseId}`);
}

export function updateCourse(
  courseId: string,
  payload: Pick<
    BackendCourse,
    "title" | "description" | "icon" | "color" | "objectives" | "audience" | "language" | "difficulty" | "knowledgeGraph"
  > & { expected_revision: number },
) {
  return apiRequest<BackendCourse>(`/api/courses/${courseId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getCourseMaterials(courseId: string, options?: CourseMaterialsScopeOptions) {
  const params = new URLSearchParams();

  if (options?.materialType) params.set("material_type", options.materialType);
  if (options?.scopeType) params.set("scope_type", options.scopeType);
  if (options?.scopeId) params.set("scope_id", options.scopeId);
  if (typeof options?.aggregate === "boolean") params.set("aggregate", options.aggregate ? "true" : "false");
  if (typeof options?.limit === "number") params.set("limit", String(options.limit));
  if (typeof options?.offset === "number") params.set("offset", String(options.offset));
  if (options?.sort) params.set("sort", options.sort);
  if (options?.space) params.set("space", options.space);
  if (options?.sort) params.set("sort", options.sort);

  const search = params.toString();
  return apiRequest<CourseMaterial[] | CourseMaterialPage>(
    `/api/courses/${courseId}/materials${search ? `?${search}` : ""}`,
  ).then(unwrapCourseMaterials);
}

export function getCourseMaterial(
  courseId: string,
  materialType: string,
  materialId: string,
) {
  return apiRequest<CourseMaterial>(
    `/api/courses/${courseId}/materials/${materialType}/${materialId}`,
  );
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

  return apiRequest<{ document: KnowledgeBaseDocument; job: JobRecord }>(`/api/courses/${courseId}/knowledge-base/documents`, {
    method: "POST",
    body: formData,
  });
}

export function getKnowledgeBaseDocumentContent(courseId: string, documentId: string) {
  return apiRequest<KnowledgeBaseDocumentContent>(
    `/api/courses/${courseId}/knowledge-base/documents/${documentId}/content`,
  );
}

export function buildKnowledgeBaseFromOpenTextbook(courseId: string) {
  return apiRequest<JobRecord>(`/api/courses/${courseId}/knowledge-base/build-from-open-textbook`, {
    method: "POST",
    body: JSON.stringify({
      source_id: "auto",
      max_pages: 160,
      clean_placeholders: true,
    }),
  });
}

export function createCourseKnowledgeBuildDraft(
  courseId: string,
  config?: Partial<CourseKnowledgeBuildConfig>,
) {
  return apiRequest<CourseKnowledgeBuild>(`/api/courses/${courseId}/knowledge-builds`, {
    method: "POST",
    body: JSON.stringify(config ? { config } : {}),
  });
}

export function leaveCourse(courseId: string) {
  return apiRequest<{ ok: boolean; message: string }>(
    `/api/courses/${encodeURIComponent(courseId)}/membership`,
    { method: "DELETE" },
  );
}

export function deleteCourse(courseId: string) {
  return apiRequest<{ message: string }>(
    `/api/courses/${encodeURIComponent(courseId)}`,
    { method: "DELETE" },
  );
}

export function deleteCourseKnowledgeBase(courseId: string) {
  return apiRequest<{ message: string }>(
    `/api/courses/${encodeURIComponent(courseId)}/knowledge-base`,
    { method: "DELETE" },
  );
}

export function updateCourseKnowledgeBuildDraft(
  courseId: string,
  buildId: string,
  expectedRevision: number,
  config: CourseKnowledgeBuildConfig,
) {
  return apiRequest<CourseKnowledgeBuild>(`/api/courses/${courseId}/knowledge-builds/${buildId}`, {
    method: "PATCH",
    body: JSON.stringify({ expected_revision: expectedRevision, config }),
  });
}

export function uploadCourseKnowledgeTextbook(
  courseId: string,
  buildId: string,
  expectedRevision: number,
  file: File,
) {
  const form = new FormData();
  form.append("expected_revision", String(expectedRevision));
  form.append("file", file);
  return apiRequest<{ build: CourseKnowledgeBuild; textbook: CourseKnowledgeTextbookInput; job: JobRecord }>(
    `/api/courses/${courseId}/knowledge-builds/${buildId}/textbooks`,
    { method: "POST", body: form },
  );
}

export function retryCourseKnowledgeTextbook(
  courseId: string,
  buildId: string,
  textbookId: string,
  expectedRevision: number,
) {
  return apiRequest<{ build: CourseKnowledgeBuild; job: JobRecord }>(
    `/api/courses/${courseId}/knowledge-builds/${buildId}/textbooks/${textbookId}/retry`,
    { method: "POST", body: JSON.stringify({ expected_revision: expectedRevision }) },
  );
}

export function removeCourseKnowledgeTextbook(
  courseId: string,
  buildId: string,
  textbookId: string,
  expectedRevision: number,
) {
  return apiRequest<CourseKnowledgeBuild>(
    `/api/courses/${courseId}/knowledge-builds/${buildId}/textbooks/${textbookId}`,
    { method: "DELETE", body: JSON.stringify({ expected_revision: expectedRevision }) },
  );
}

export function generateCourseKnowledgeGraphDraft(
  courseId: string,
  buildId: string,
  expectedRevision: number,
  targetModuleId?: string,
) {
  return apiRequest<JobRecord>(`/api/courses/${courseId}/knowledge-builds/${buildId}/graph/generate`, {
    method: "POST",
    body: JSON.stringify({
      expected_revision: expectedRevision,
      target_module_id: targetModuleId,
    }),
  });
}

export function saveCourseKnowledgeGraphDraft(
  courseId: string,
  buildId: string,
  expectedRevision: number,
  root: KnowledgeGraphNode,
) {
  return apiRequest<CourseKnowledgeBuild>(`/api/courses/${courseId}/knowledge-builds/${buildId}/graph`, {
    method: "PUT",
    body: JSON.stringify({ expected_revision: expectedRevision, root }),
  });
}

export function confirmCourseKnowledgeGraph(
  courseId: string,
  buildId: string,
  expectedRevision: number,
) {
  return apiRequest<CourseKnowledgeBuild>(
    `/api/courses/${courseId}/knowledge-builds/${buildId}/graph/confirm`,
    { method: "POST", body: JSON.stringify({ expected_revision: expectedRevision }) },
  );
}

export function getCourseKnowledgeBuild(courseId: string, buildId: string) {
  return apiRequest<CourseKnowledgeBuild>(`/api/courses/${courseId}/knowledge-builds/${buildId}`);
}

export function startCourseKnowledgeBuild(courseId: string, buildId: string) {
  return apiRequest<JobRecord>(`/api/courses/${courseId}/knowledge-builds/${buildId}/start`, {
    method: "POST",
  });
}

export function retryCourseKnowledgeBuild(courseId: string, buildId: string) {
  return apiRequest<JobRecord>(`/api/courses/${courseId}/knowledge-builds/${buildId}/retry`, {
    method: "POST",
  });
}

export function listCourseKnowledgeVersions(courseId: string) {
  return apiRequest<CourseKnowledgeGraphVersion[]>(`/api/courses/${courseId}/knowledge-base/versions`);
}

export function rollbackCourseKnowledgeVersion(courseId: string, version: number) {
  return apiRequest<{ version: number; rolled_back_from_version: number }>(
    `/api/courses/${courseId}/knowledge-base/versions/${version}/rollback`,
    { method: "POST" },
  );
}

export function deleteCourseMaterial(
  courseId: string,
  materialType: string,
  materialId: string,
) {
  return apiRequest<{ ok: boolean }>(
    `/api/courses/${courseId}/materials/${materialType}/${materialId}`,
    { method: "DELETE" },
  );
}

export function pinCourseMaterial(
  courseId: string,
  materialType: string,
  materialId: string,
  isPinned: boolean,
) {
  return apiRequest<CourseMaterial>(
    `/api/courses/${courseId}/materials/${materialType}/${materialId}/pin`,
    {
      method: "POST",
      body: JSON.stringify({ is_pinned: isPinned }),
    },
  );
}

export function renameCourseMaterial(
  courseId: string,
  materialType: string,
  materialId: string,
  title: string,
) {
  return apiRequest<CourseMaterial>(
    `/api/courses/${courseId}/materials/${materialType}/${materialId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ title }),
    },
  );
}

export function updateCourseMaterialContent(
  courseId: string,
  materialType: string,
  materialId: string,
  content: unknown,
) {
  return apiRequest<CourseMaterial>(
    `/api/courses/${courseId}/materials/${materialType}/${materialId}/content`,
    {
      method: "PATCH",
      body: JSON.stringify({ content }),
    },
  );
}

export function publishCourseMaterial(
  courseId: string,
  materialType: string,
  materialId: string,
) {
  return apiRequest<MaterialPublicationResponse>(
    `/api/courses/${courseId}/materials/${materialType}/${materialId}/publish`,
    { method: "POST" },
  );
}

export function withdrawCourseMaterial(
  courseId: string,
  materialType: string,
  materialId: string,
) {
  return apiRequest<{ ok: boolean }>(
    `/api/courses/${courseId}/materials/${materialType}/${materialId}/publication`,
    { method: "DELETE" },
  );
}

export function reindexKnowledgeBaseDocument(courseId: string, documentId: string) {
  return apiRequest<JobRecord>(
    `/api/courses/${courseId}/knowledge-base/documents/${documentId}/reindex`,
    { method: "POST" },
  );
}

export function retryKnowledgeBaseDocument(courseId: string, documentId: string) {
  return apiRequest<JobRecord>(
    `/api/courses/${courseId}/knowledge-base/documents/${documentId}/retry`,
    { method: "POST" },
  );
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

  const materialRecord = toPlainRecord(material);
  const topLevelCandidates = [
    materialRecord.content_markdown,
    materialRecord.markdown,
    materialRecord.report,
    materialRecord.report_content,
    materialRecord.text,
  ];

  for (const candidate of topLevelCandidates) {
    if (hasTextContent(candidate)) return candidate;
  }

  const record = toPlainRecord(material.content);
  const candidates = [record.content_markdown, record.markdown, record.report, record.report_content, record.content, record.text];

  for (const candidate of candidates) {
    if (hasTextContent(candidate)) return candidate;
  }

  return "";
}

function formatMarkdownList(heading: string, values: unknown): string {
  const items = Array.isArray(values) ? values.map((item) => textFromUnknown(item)).filter(Boolean) : [];
  if (items.length === 0) return "";
  return `## ${heading}\n\n${items.map((item) => `- ${item}`).join("\n")}`;
}

function formatReportSections(sections: unknown[]): string {
  return sections
    .map((section) => {
      const record = toPlainRecord(section);
      const subsections = Array.isArray(record.subsections) ? record.subsections : [];
      const subsectionMarkdown = subsections
        .map((subsection) => {
          const subsectionRecord = toPlainRecord(subsection);
          const title = textFromUnknown(subsectionRecord.title) || "小节";
          const content = textFromUnknown(subsectionRecord.content);
          return [`### ${title}`, content].filter(Boolean).join("\n\n");
        })
        .filter(Boolean)
        .join("\n\n");

      return [`## ${textFromUnknown(record.title) || "章节"}`, textFromUnknown(record.content), subsectionMarkdown]
        .filter(Boolean)
        .join("\n\n");
    })
    .filter(Boolean)
    .join("\n\n");
}

function formatReportMarkdown(material: CourseMaterial): string {
  const reportRecord = toPlainRecord(material.report);
  const reportSections = Array.isArray(reportRecord.mainContent)
    ? reportRecord.mainContent
    : Array.isArray(material.mainContent)
      ? material.mainContent
      : [];
  const title = textFromUnknown(reportRecord.title) || material.title || material.topic || material.material_id;
  const summary = textFromUnknown(reportRecord.summary) || material.summary || "";
  const introduction = textFromUnknown(reportRecord.introduction);
  const sectionsMarkdown = formatReportSections(reportSections);
  const keyFindings = formatMarkdownList("关键结论", reportRecord.keyFindings);
  const conclusions = textFromUnknown(reportRecord.conclusions);
  const recommendations = formatMarkdownList("建议", reportRecord.recommendations);

  if (!summary && !introduction && !sectionsMarkdown && !keyFindings && !conclusions && !recommendations) {
    return "";
  }

  return [
    `# ${title}`,
    summary,
    introduction ? `## 引言\n\n${introduction}` : "",
    sectionsMarkdown,
    keyFindings,
    conclusions ? `## 结论\n\n${conclusions}` : "",
    recommendations,
  ]
    .filter(Boolean)
    .join("\n\n");
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

function formatQuizMarkdown(material: CourseMaterial): string {
  const questions = Array.isArray(material.questions) ? material.questions : [];
  if (questions.length === 0) return "";

  const body = questions
    .map((question, index) => {
      const options = Array.isArray(question.options)
        ? question.options.map((option) => `- ${textFromUnknown(option)}`).filter(Boolean).join("\n")
        : "";
      const answer = textFromUnknown(question.answer);
      const explanation = textFromUnknown(question.explanation);

      return [
        `## 第 ${index + 1} 题`,
        textFromUnknown(question.stem),
        options,
        answer ? `**答案：** ${answer}` : "",
        explanation ? `**解析：** ${explanation}` : "",
      ]
        .filter(Boolean)
        .join("\n\n");
    })
    .filter(Boolean)
    .join("\n\n");

  return [`# ${material.title || material.topic || material.material_id}`, material.summary || "", body]
    .filter(Boolean)
    .join("\n\n");
}

function formatLessonPlanMarkdown(material: CourseMaterial): string {
  const plan = toPlainRecord(material.plan);
  const process = Array.isArray(plan.process) ? plan.process : [];
  const processMarkdown = process
    .map((item, index) => {
      const record = toPlainRecord(item);
      const step = textFromUnknown(record.step) || `步骤 ${index + 1}`;
      const content = textFromUnknown(record.content);
      const duration = textFromUnknown(record.duration);

      return [`### ${step}`, duration ? `时长：${duration}` : "", content]
        .filter(Boolean)
        .join("\n\n");
    })
    .filter(Boolean)
    .join("\n\n");

  if (
    !textFromUnknown(plan.title)
    && !Array.isArray(plan.objectives)
    && !Array.isArray(plan.keyPoints)
    && !Array.isArray(plan.hardPoints)
    && process.length === 0
    && !textFromUnknown(plan.homework)
  ) {
    return "";
  }

  return [
    `# ${textFromUnknown(plan.title) || material.title || material.topic || material.material_id}`,
    formatMarkdownList("教学目标", plan.objectives),
    formatMarkdownList("重点", plan.keyPoints),
    formatMarkdownList("难点", plan.hardPoints),
    processMarkdown ? `## 教学过程\n\n${processMarkdown}` : "",
    textFromUnknown(plan.homework) ? `## 作业\n\n${textFromUnknown(plan.homework)}` : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

function formatFlashcardMarkdown(material: CourseMaterial): string {
  const contentRecord = toPlainRecord(material.content);
  const cards = Array.isArray(material.flashcards)
    ? material.flashcards
    : Array.isArray(contentRecord.cards)
      ? contentRecord.cards
      : Array.isArray(material.content)
        ? material.content
        : [];
  if (cards.length === 0) return "";

  const cardMarkdown = cards
    .map((card, index) => {
      const record = toPlainRecord(card);
      const front =
        textFromUnknown(record.front)
        || textFromUnknown(record.question)
        || textFromUnknown(record.term);
      const back =
        textFromUnknown(record.back)
        || textFromUnknown(record.answer)
        || textFromUnknown(record.definition);
      const category = textFromUnknown(record.category);
      const source = textFromUnknown(record.source);

      return [
        `## 第 ${index + 1} 张`,
        category ? `**分类：** ${category}` : "",
        front ? `**正面：** ${front}` : "",
        back ? `**背面：** ${back}` : "",
        source ? `**来源：** ${source}` : "",
      ]
        .filter(Boolean)
        .join("\n\n");
    })
    .filter(Boolean)
    .join("\n\n");

  return [
    `# ${material.title || material.topic || "闪卡"}`,
    material.summary || "",
    cardMarkdown,
  ]
    .filter(Boolean)
    .join("\n\n");
}

export function courseMaterialToMarkdown(material: CourseMaterial) {
  const directMarkdown = extractDirectMaterialMarkdown(material);
  if (directMarkdown) return directMarkdown;

  if (material.material_type === "report") {
    const reportMarkdown = formatReportMarkdown(material);
    if (reportMarkdown) return reportMarkdown;
  }

  if (material.material_type === "ppt") {
    return formatPptDeckMarkdown(material);
  }

  if (material.material_type === "quiz") {
    const quizMarkdown = formatQuizMarkdown(material);
    if (quizMarkdown) return quizMarkdown;
  }

  if (material.material_type === "lesson_plan") {
    const lessonPlanMarkdown = formatLessonPlanMarkdown(material);
    if (lessonPlanMarkdown) return lessonPlanMarkdown;
  }

  if (material.material_type === "flashcard") {
    const flashcardMarkdown = formatFlashcardMarkdown(material);
    if (flashcardMarkdown) return flashcardMarkdown;
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
