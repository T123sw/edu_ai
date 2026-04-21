import { API_BASE_URL } from "./api/client";
import type { CourseMaterial } from "./api/types";

const WORD_EXPORTABLE_TYPES = new Set(["report", "lesson_plan", "quiz", "blog"]);
const WORD_BLOCKED_TYPES = new Set(["ppt", "ai_lecture_session"]);

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderInlineMarkdown(text: string) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

function markdownToWordHtml(markdown: string) {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const html: string[] = [];
  const paragraph: string[] = [];
  const listItems: string[] = [];
  let listTag: "ul" | "ol" | null = null;
  let inCodeBlock = false;
  let codeLines: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph.length = 0;
  };

  const flushList = () => {
    if (!listTag || !listItems.length) return;
    html.push(`<${listTag}>${listItems.join("")}</${listTag}>`);
    listTag = null;
    listItems.length = 0;
  };

  const flushCodeBlock = () => {
    if (!codeLines.length) return;
    html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    codeLines = [];
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      flushParagraph();
      flushList();
      if (inCodeBlock) flushCodeBlock();
      inCodeBlock = !inCodeBlock;
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = /^(#{1,6})\s+(.*)$/.exec(line.trim());
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = headingMatch[1].length;
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    const unorderedMatch = /^\s*[-*]\s+(.*)$/.exec(line);
    if (unorderedMatch) {
      flushParagraph();
      if (listTag && listTag !== "ul") flushList();
      listTag = "ul";
      listItems.push(`<li>${renderInlineMarkdown(unorderedMatch[1])}</li>`);
      continue;
    }

    const orderedMatch = /^\s*\d+\.\s+(.*)$/.exec(line);
    if (orderedMatch) {
      flushParagraph();
      if (listTag && listTag !== "ol") flushList();
      listTag = "ol";
      listItems.push(`<li>${renderInlineMarkdown(orderedMatch[1])}</li>`);
      continue;
    }

    flushList();
    paragraph.push(line.trim());
  }

  flushParagraph();
  flushList();
  flushCodeBlock();

  return html.join("\n");
}

function sanitizeFileName(fileName: string) {
  const normalized = fileName.replace(/[\\/:*?"<>|]+/g, "_").trim();
  return normalized || "course-material";
}

function resolveAssetUrl(value: unknown) {
  const normalized = typeof value === "string" ? value.trim() : "";
  if (!normalized) return "";
  if (/^https?:\/\//i.test(normalized)) return normalized;
  return `${API_BASE_URL}${normalized.startsWith("/") ? normalized : `/${normalized}`}`;
}

function buildWordDocumentHtml(title: string, bodyHtml: string) {
  const safeTitle = escapeHtml(title);
  const content = bodyHtml || `<p>${safeTitle}</p>`;

  return `<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head>
  <meta charset="utf-8" />
  <title>${safeTitle}</title>
  <style>
    body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; line-height: 1.7; color: #1f2937; margin: 32px; }
    h1, h2, h3, h4, h5, h6 { color: #0f3c96; margin: 20px 0 12px; }
    p { margin: 0 0 12px; }
    ul, ol { margin: 0 0 14px 22px; }
    li { margin: 6px 0; }
    pre { background: #f3f6fb; border: 1px solid #dbe5f3; border-radius: 8px; padding: 12px; overflow: auto; white-space: pre-wrap; }
    code { font-family: Consolas, "Courier New", monospace; }
  </style>
</head>
<body>
${content}
</body>
</html>`;
}

export function isCourseMaterialWordExportable(material: CourseMaterial | null | undefined, markdown: string) {
  if (!material || !markdown.trim()) return false;

  const normalizedType = String(material.material_type || "").trim().toLowerCase();
  if (WORD_BLOCKED_TYPES.has(normalizedType)) return false;
  if (WORD_EXPORTABLE_TYPES.has(normalizedType)) return true;

  return Boolean(material.report)
    || Boolean(material.plan)
    || (Array.isArray(material.questions) && material.questions.length > 0)
    || (Array.isArray(material.mainContent) && material.mainContent.length > 0)
    || (Array.isArray(material.outline) && material.outline.length > 0);
}

export function getCourseMaterialPptExportUrl(material: CourseMaterial | null | undefined) {
  if (!material) return "";

  const normalizedType = String(material.material_type || "").trim().toLowerCase();
  if (normalizedType !== "ppt") return "";

  const topLevelRecord = material as Record<string, unknown>;
  const contentRecord =
    material.content && typeof material.content === "object" && !Array.isArray(material.content)
      ? (material.content as Record<string, unknown>)
      : {};

  return resolveAssetUrl(topLevelRecord.pptx_url || contentRecord.pptx_url);
}

export function getCourseMaterialPptPreviewUrl(material: CourseMaterial | null | undefined) {
  if (!material) return "";

  const normalizedType = String(material.material_type || "").trim().toLowerCase();
  if (normalizedType !== "ppt") return "";

  const topLevelRecord = material as Record<string, unknown>;
  const contentRecord =
    material.content && typeof material.content === "object" && !Array.isArray(material.content)
      ? (material.content as Record<string, unknown>)
      : {};

  return resolveAssetUrl(
    topLevelRecord.html_full_url || contentRecord.html_full_url || topLevelRecord.html_url || contentRecord.html_url,
  );
}

export function exportCourseMaterialAsWord(material: CourseMaterial, markdown: string) {
  const fileTitle = material.title || material.topic || material.material_id || "course-material";
  const safeFileName = sanitizeFileName(fileTitle);
  const wordDocument = buildWordDocumentHtml(fileTitle, markdownToWordHtml(markdown));
  const blob = new Blob(["\ufeff", wordDocument], { type: "application/msword;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `${safeFileName}.doc`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
