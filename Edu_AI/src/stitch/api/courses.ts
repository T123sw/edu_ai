import { apiRequest } from "./client";
import type { BackendCourse, CourseMaterial, KnowledgeBaseDocument, KnowledgeGraphData } from "./types";
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

export function backendCourseToSummary(course: BackendCourse, index = 0): CourseSummary {
  const accent = accentPalette[index % accentPalette.length];
  const image = courseImages[index % courseImages.length];
  const progressSeed = course.id
    .split("")
    .reduce((sum, char) => sum + char.charCodeAt(0), 0);

  return {
    id: course.id,
    module: `模块 ${(index % 8) + 1}`,
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

export function getCourseMaterials(courseId: string) {
  return apiRequest<CourseMaterial[]>(`/api/courses/${courseId}/materials`);
}

export function getKnowledgeBaseDocuments(courseId: string) {
  return apiRequest<KnowledgeBaseDocument[]>(`/api/courses/${courseId}/knowledge-base/documents`);
}

export function uploadKnowledgeBaseDocument(courseId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);

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

function hasTextContent(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export function courseMaterialToMarkdown(material: CourseMaterial) {
  if (hasTextContent(material.final_markdown)) return material.final_markdown;
  if (hasTextContent(material.content)) return material.content;

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
          .map((child) => `### ${child.title || "小节"}\n\n${Array.isArray(child.key_concepts) ? child.key_concepts.map((item) => `- ${item}`).join("\n") : ""}`)
          .join("\n\n");
        return `## ${section.title || "章节"}\n\n${childText}`;
      })
      .join("\n\n");
    return `# ${material.title || material.topic || "教学博客"}\n\n${body}`;
  }

  return `# ${material.title || material.material_id}\n\n当前资源暂无可直接渲染的 Markdown 内容。`;
}
