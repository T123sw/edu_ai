import { useEffect, useMemo, useRef, useState } from "react";

import { registerCreatedJob } from "../../../jobs/jobStore";
import { listCourses } from "../../api/courses";
import type { BackendCourse } from "../../api/types";
import {
  deletePersonalKnowledgeDocument,
  getPersonalKnowledgeDocumentContent,
  listPersonalKnowledgeDocuments,
  renamePersonalKnowledgeDocument,
  retryPersonalKnowledgeDocument,
  uploadPersonalKnowledgeDocument,
  type PersonalKnowledgeDocument,
} from "../../api/personalKnowledge";
import { MaterialIcon } from "../../shared";
import { buildStudentHash } from "../routes/studentRoutes";
import "../styles/studentKnowledge.css";

const statusLabel: Record<string, string> = {
  received: "已接收", parsing: "解析中", chunking: "切分中", embedding: "向量化中",
  indexing: "索引中", ready: "可检索", partially_ready: "部分可用", failed: "处理失败",
};

export function StudentPersonalKnowledgePage() {
  const [documents, setDocuments] = useState<PersonalKnowledgeDocument[]>([]);
  const [courses, setCourses] = useState<BackendCourse[]>([]);
  const [questionCourseId, setQuestionCourseId] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ title: string; content: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [personal, joinedCourses] = await Promise.all([listPersonalKnowledgeDocuments({ limit: 500 }), listCourses()]);
      setDocuments(personal);
      setCourses(joinedCourses);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "个人知识库加载失败");
    } finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  const visibleDocuments = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return normalized ? documents.filter((item) => (item.display_name || item.name).toLocaleLowerCase().includes(normalized)) : documents;
  }, [documents, query]);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    try {
      for (const file of Array.from(files)) {
        const result = await uploadPersonalKnowledgeDocument(file);
        registerCreatedJob(result.job);
      }
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "上传失败"); }
    finally { if (fileInput.current) fileInput.current.value = ""; }
  }

  async function openPreview(item: PersonalKnowledgeDocument) {
    try {
      const content = await getPersonalKnowledgeDocumentContent(item.id);
      setPreview({ title: item.display_name || item.name, content: content.content || "该资料暂无可显示的文本内容。" });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "预览失败"); }
  }

  async function rename(item: PersonalKnowledgeDocument) {
    const name = window.prompt("输入新的资料名称", item.display_name || item.name)?.trim();
    if (!name) return;
    try { await renamePersonalKnowledgeDocument(item.id, name); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "重命名失败"); }
  }

  async function remove(item: PersonalKnowledgeDocument) {
    if (!window.confirm(`确认删除“${item.display_name || item.name}”吗？`)) return;
    try { await deletePersonalKnowledgeDocument(item.id); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "删除失败"); }
  }

  async function retry(item: PersonalKnowledgeDocument) {
    try { const job = await retryPersonalKnowledgeDocument(item.id); registerCreatedJob(job); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "重试失败"); }
  }

  return (
    <div className="student-personal-knowledge">
      <section className="student-personal-knowledge__intro">
        <div><p>全局个人空间</p><h2>只属于你的学习资料</h2><span>无论从哪门课程上传，都会汇总在这里；教师和其他学生无法读取。</span></div>
        <div className="student-personal-knowledge__actions">
          <label><span>用于问答的课程</span><select value={questionCourseId} onChange={(event) => setQuestionCourseId(event.target.value)}><option value="">需要时手动选择</option>{courses.map((course) => <option key={course.id} value={course.id}>{course.title}</option>)}</select></label>
          <input ref={fileInput} hidden type="file" multiple onChange={(event) => void upload(event.target.files)} />
          <button onClick={() => fileInput.current?.click()}><MaterialIcon name="upload_file" />上传资料</button>
        </div>
      </section>
      <label className="student-personal-knowledge__search"><MaterialIcon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索个人资料" /><span>{visibleDocuments.length} 份</span></label>
      {error ? <div className="student-knowledge-error" role="alert"><span>{error}</span><button onClick={() => void load()}>重新加载</button></div> : null}
      {loading ? <div className="student-knowledge-state">正在加载个人资料…</div> : null}
      {!loading && documents.length === 0 ? <div className="student-knowledge-state"><h3>还没有个人资料</h3><p>上传文档后可用于 AI 问答和个人资源生成，资料不会进入课程知识库。</p></div> : null}
      {!loading && documents.length > 0 && visibleDocuments.length === 0 ? <div className="student-knowledge-state">没有找到匹配的资料。</div> : null}
      <div className="student-personal-knowledge__grid">
        {visibleDocuments.map((item) => (
          <article key={item.id} className="student-personal-document">
            <div className="student-personal-document__icon"><MaterialIcon name="description" /></div>
            <div className="student-personal-document__body"><h3>{item.display_name || item.name}</h3><p>{statusLabel[item.status] || item.status} · {item.chunk_count || 0} 个可检索片段</p><small>{item.course_context_id ? "来源于课程学习上下文" : "全局个人上传"} · {new Date(item.created_at).toLocaleString("zh-CN")}</small></div>
            <div className="student-personal-document__actions">
              <button onClick={() => void openPreview(item)}>预览</button>
              <button onClick={() => void rename(item)}>重命名</button>
              {item.status === "failed" ? <button onClick={() => void retry(item)}>重试</button> : null}
              {questionCourseId ? <a href={buildStudentHash("student-ai", { courseId: questionCourseId })}>用于问答</a> : <button disabled title="请先在页面上方选择课程">用于问答</button>}
              <button className="is-danger" onClick={() => void remove(item)}>删除</button>
            </div>
          </article>
        ))}
      </div>
      {preview ? <div className="student-personal-knowledge__preview" onMouseDown={(event) => { if (event.target === event.currentTarget) setPreview(null); }}><section role="dialog" aria-modal="true" aria-label={preview.title}><header><h3>{preview.title}</h3><button onClick={() => setPreview(null)}><MaterialIcon name="close" /></button></header><pre>{preview.content}</pre></section></div> : null}
    </div>
  );
}
