import { useEffect, useMemo, useState } from "react";

import { loadPreviewMediaUrl } from "../../../services/rag";
import { getKnowledgeBaseDocumentContent } from "../../api/courses";
import type { KnowledgeBaseDocument, KnowledgeBaseDocumentContent } from "../../api/types";
import { MarkdownPreview } from "../../components/MarkdownPreview";
import { MaterialIcon } from "../../shared";

function markdownMediaSources(content: string): string[] {
  const matches = content.matchAll(/!\[[^\]]*\]\(([^)\s]+)(?:\s+["'][^"']*["'])?\)/g);
  return Array.from(new Set(Array.from(matches, (match) => match[1]).filter(Boolean)));
}

export function KnowledgeDocumentPreviewDialog({
  courseId,
  document,
  onClose,
}: {
  courseId: string;
  document: KnowledgeBaseDocument;
  onClose: () => void;
}) {
  const [content, setContent] = useState<KnowledgeBaseDocumentContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({});
  const title = document.display_name || document.source_title || document.name;
  const sources = useMemo(() => markdownMediaSources(content?.content || ""), [content]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getKnowledgeBaseDocumentContent(courseId, document.id)
      .then((result) => !cancelled && setContent(result))
      .catch(() => !cancelled && setError("文档内容暂时无法读取，请稍后重试。"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [courseId, document.id]);

  useEffect(() => {
    let cancelled = false;
    const objectUrls: string[] = [];
    Promise.all(sources.map(async (source) => {
      try {
        const url = await loadPreviewMediaUrl(source);
        if (url.startsWith("blob:")) objectUrls.push(url);
        return [source, url] as const;
      } catch {
        return [source, source] as const;
      }
    })).then((entries) => !cancelled && setImageUrls(Object.fromEntries(entries)));
    return () => {
      cancelled = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [sources]);

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-label={`预览 ${title}`} onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-[24px] bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-blue-600">课程知识库 · 文档预览</p>
            <h2 className="mt-1 truncate text-xl font-bold text-slate-900">{title}</h2>
            {document.source_title && document.source_title !== title && <p className="mt-1 text-xs text-slate-500">来源：{document.source_title}</p>}
          </div>
          <button type="button" className="rounded-full p-2 text-slate-500 hover:bg-slate-100" aria-label="关闭预览" onClick={onClose}><MaterialIcon name="close" /></button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-7 py-6">
          {loading ? <p className="py-16 text-center text-slate-500">正在读取文档…</p>
            : error ? <p className="py-16 text-center text-red-600">{error}</p>
            : content?.content ? <MarkdownPreview content={content.content} imageUrls={imageUrls} />
            : <p className="py-16 text-center text-slate-500">该文档没有可展示的正文。</p>}
        </div>
      </div>
    </div>
  );
}
