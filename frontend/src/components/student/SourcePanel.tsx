import { useCallback, useEffect, useRef, useState } from "react";

import {
  getKnowledgeBaseDocumentContent,
  getKnowledgeBaseDocuments,
} from "../../stitch/api/courses";
import type { KnowledgeBaseDocument } from "../../stitch/api/types";
import {
  deletePersonalKnowledgeDocument,
  getPersonalKnowledgeDocumentContent,
  listPersonalKnowledgeDocuments,
  renamePersonalKnowledgeDocument,
  retryPersonalKnowledgeDocument,
  uploadPersonalKnowledgeDocument,
} from "../../stitch/api/personalKnowledge";
import { registerCreatedJob } from "../../jobs/jobStore";
import { deepSearchAndCrawl, getCrawlResults, type CrawlResult } from "../../services/deepsearch";
import { MaterialIcon, cx } from "../../stitch/shared";
import { getStudentSourceActions } from "./studentSourceActions";

type Props = {
  courseId: string;
  selectedDocumentIds: readonly string[];
  onSelectedDocumentIdsChange: (ids: string[]) => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
};

type Library = "course" | "personal";
type ListedDocument = KnowledgeBaseDocument & { course_context_id?: string | null };

const statusLabels: Record<string, string> = {
  received: "已接收", parsing: "解析中", chunking: "切分中", embedding: "向量化中",
  indexing: "索引中", ready: "可检索", partially_ready: "部分可用", failed: "处理失败",
};

function researchMarkdown(query: string, results: CrawlResult[]) {
  return [
    `# 深度研究：${query}`,
    ...results.filter((item) => item.status === "success" && item.content).map((item) =>
      `## ${item.title || item.url}\n\n来源：${item.url}\n\n${item.content}`,
    ),
  ].join("\n\n");
}

export default function StudentSourcePanel({
  courseId,
  selectedDocumentIds,
  onSelectedDocumentIdsChange,
  collapsed = false,
  onToggleCollapsed,
}: Props) {
  const [library, setLibrary] = useState<Library>("course");
  const [courseDocuments, setCourseDocuments] = useState<ListedDocument[]>([]);
  const [personalDocuments, setPersonalDocuments] = useState<ListedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [researchQuery, setResearchQuery] = useState("");
  const [researchStatus, setResearchStatus] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ title: string; content: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const selectedDocumentIdsRef = useRef(selectedDocumentIds);

  useEffect(() => {
    selectedDocumentIdsRef.current = selectedDocumentIds;
  }, [selectedDocumentIds]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [courseItems, personalItems] = await Promise.all([
        getKnowledgeBaseDocuments(courseId, { aggregate: true, libraryType: "course", limit: 300, sort: "created_desc" }),
        listPersonalKnowledgeDocuments({ limit: 300 }),
      ]);
      setCourseDocuments(courseItems);
      setPersonalDocuments(personalItems.map((item) => ({ ...item, course_id: item.course_context_id ?? courseId })));
      const validIds = new Set([...courseItems, ...personalItems].map((item) => item.id));
      onSelectedDocumentIdsChange(selectedDocumentIdsRef.current.filter((id) => validIds.has(id)));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "知识库加载失败");
    } finally {
      setLoading(false);
    }
  }, [courseId, onSelectedDocumentIdsChange]);

  useEffect(() => { void load(); }, [load]);

  if (collapsed) {
    return <button type="button" className="student-ai__collapsed-panel" onClick={onToggleCollapsed}><MaterialIcon name="database" /><span>知识库</span></button>;
  }

  const documents = library === "course" ? courseDocuments : personalDocuments;
  const visible = documents.filter((item) => (item.display_name || item.name).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));

  function toggleSelection(documentId: string) {
    onSelectedDocumentIdsChange(selectedDocumentIds.includes(documentId)
      ? selectedDocumentIds.filter((id) => id !== documentId)
      : [...selectedDocumentIds, documentId]);
  }

  async function openPreview(item: ListedDocument) {
    try {
      const content = library === "course"
        ? await getKnowledgeBaseDocumentContent(courseId, item.id)
        : await getPersonalKnowledgeDocumentContent(item.id);
      setPreview({ title: item.display_name || item.name, content: content.content || "该文档暂无可显示的文本内容。" });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "文档预览失败");
    }
  }

  async function uploadFiles(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    try {
      for (const file of Array.from(files)) {
        const response = await uploadPersonalKnowledgeDocument(file, courseId);
        registerCreatedJob(response.job);
      }
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "个人资料上传失败");
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function renameDocument(item: ListedDocument) {
    const nextName = window.prompt("输入新的资料名称", item.display_name || item.name)?.trim();
    if (!nextName) return;
    try { await renamePersonalKnowledgeDocument(item.id, nextName); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "重命名失败"); }
  }

  async function removeDocument(item: ListedDocument) {
    if (!window.confirm(`确认删除“${item.display_name || item.name}”吗？`)) return;
    try {
      await deletePersonalKnowledgeDocument(item.id);
      onSelectedDocumentIdsChange(selectedDocumentIds.filter((id) => id !== item.id));
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "删除失败"); }
  }

  async function retryDocument(item: ListedDocument) {
    try { const job = await retryPersonalKnowledgeDocument(item.id); registerCreatedJob(job); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "重试失败"); }
  }

  async function startResearch() {
    const query = researchQuery.trim();
    if (!query) return;
    setResearchStatus("正在检索并阅读网页…");
    setError(null);
    try {
      const response = await deepSearchAndCrawl({ query, depth: "full", max_urls: 5, course_id: courseId });
      let results = response.results ?? [];
      if (results.length === 0 && response.batch_id) {
        const loaded = await getCrawlResults(response.batch_id);
        results = loaded.results ?? [];
      }
      const markdown = researchMarkdown(query, results);
      if (markdown.split("\n").length <= 2) throw new Error("本次研究没有取得可保存的网页内容");
      const safeName = query.replace(/[\\/:*?"<>|]/g, "-").slice(0, 60) || "研究结果";
      const result = await uploadPersonalKnowledgeDocument(new File([markdown], `深度研究-${safeName}.md`, { type: "text/markdown" }), courseId);
      registerCreatedJob(result.job);
      setResearchStatus("研究结果已保存到个人知识库");
      setLibrary("personal");
      setResearchQuery("");
      await load();
    } catch (reason) {
      setResearchStatus(null);
      setError(reason instanceof Error ? reason.message : "深度研究失败");
    }
  }

  return (
    <section className="student-source-panel" aria-label="知识库与深度研究">
      <header><div><small>学习资料</small><h2>知识库</h2></div>{onToggleCollapsed ? <button aria-label="收起知识库" onClick={onToggleCollapsed}><MaterialIcon name="chevron_left" /></button> : null}</header>
      <div className="student-source-panel__research">
        <strong><MaterialIcon name="travel_explore" /> 深度研究</strong>
        <div><input value={researchQuery} onChange={(event) => setResearchQuery(event.target.value)} placeholder="输入需要深入研究的问题" onKeyDown={(event) => { if (event.key === "Enter") void startResearch(); }} /><button disabled={!researchQuery.trim() || Boolean(researchStatus?.startsWith("正在"))} onClick={() => void startResearch()}>研究</button></div>
        {researchStatus ? <p role="status">{researchStatus}</p> : null}
      </div>
      <div className="student-source-panel__tabs" role="tablist">
        <button role="tab" aria-selected={library === "course"} className={cx(library === "course" && "is-active")} onClick={() => setLibrary("course")}>课程知识库</button>
        <button role="tab" aria-selected={library === "personal"} className={cx(library === "personal" && "is-active")} onClick={() => setLibrary("personal")}>个人知识库</button>
      </div>
      <label className="student-source-panel__search"><MaterialIcon name="search" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索资料" /></label>
      {error ? <div className="student-source-panel__error" role="alert"><span>{error}</span><button onClick={() => void load()}>重试</button></div> : null}
      <div className="student-source-panel__list">
        {loading ? <p className="student-source-panel__state">正在加载资料…</p> : null}
        {!loading && visible.length === 0 ? <p className="student-source-panel__state">{search ? "没有匹配的资料" : library === "course" ? "教师尚未发布课程资料" : "还没有个人资料"}</p> : null}
        {visible.map((item) => {
          const actions = getStudentSourceActions(library, item.status);
          return (
            <article key={item.id} className={cx("student-source-panel__item", selectedDocumentIds.includes(item.id) && "is-selected")}>
              <input type="checkbox" aria-label={`选择${item.display_name || item.name}`} checked={selectedDocumentIds.includes(item.id)} onChange={() => toggleSelection(item.id)} />
              <button className="student-source-panel__item-main" onClick={() => void openPreview(item)}><MaterialIcon name="description" /><span><strong>{item.display_name || item.name}</strong><small>{statusLabels[item.status] || item.status} · {item.chunk_count || 0} 个片段</small></span></button>
              <div className="student-source-panel__item-actions">
                {actions.includes("rename") ? <button aria-label="重命名" onClick={() => void renameDocument(item)}><MaterialIcon name="edit_note" /></button> : null}
                {actions.includes("retry") ? <button aria-label="重试索引" onClick={() => void retryDocument(item)}><MaterialIcon name="schedule" /></button> : null}
                {actions.includes("delete") ? <button aria-label="删除" onClick={() => void removeDocument(item)}><MaterialIcon name="close" /></button> : null}
              </div>
            </article>
          );
        })}
      </div>
      {library === "personal" ? <div className="student-source-panel__upload"><input ref={fileInput} type="file" multiple hidden onChange={(event) => void uploadFiles(event.target.files)} /><button onClick={() => fileInput.current?.click()}><MaterialIcon name="upload_file" /> 上传到个人知识库</button><small>仅自己可见，不会加入课程知识库</small></div> : <p className="student-source-panel__readonly">课程资料由教师维护，学生仅可选择和预览。</p>}
      {preview ? <div className="student-source-panel__preview-layer" onMouseDown={(event) => { if (event.target === event.currentTarget) setPreview(null); }}><section role="dialog" aria-modal="true" aria-label={preview.title}><header><h3>{preview.title}</h3><button onClick={() => setPreview(null)}><MaterialIcon name="close" /></button></header><pre>{preview.content}</pre></section></div> : null}
    </section>
  );
}
