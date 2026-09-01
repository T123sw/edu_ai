import { useRef } from "react";

import type { CourseKnowledgeTextbookInput } from "../../api/types";
import { MaterialIcon } from "../../shared";

type Props = {
  textbooks: CourseKnowledgeTextbookInput[];
  uploading: boolean;
  generating: boolean;
  onBack: () => void;
  onUpload: (files: File[]) => void;
  onRetry: (textbookId: string) => void;
  onRemove: (textbookId: string) => void;
  onGenerate: () => void;
};

const STATUS_LABELS: Record<CourseKnowledgeTextbookInput["status"], string> = {
  queued: "等待解析",
  parsing: "正在解析",
  ready: "解析完成",
  failed: "解析失败",
};

function formatBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export function CourseKnowledgeTextbookStep({
  textbooks,
  uploading,
  generating,
  onBack,
  onUpload,
  onRetry,
  onRemove,
  onGenerate,
}: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const pending = textbooks.some((item) => item.status === "queued" || item.status === "parsing");
  const failed = textbooks.some((item) => item.status === "failed");

  return (
    <section className="course-kb-wizard__step" aria-labelledby="kb-textbook-title">
      <div className="course-kb-wizard__step-heading">
        <div><span>步骤 2 / 3</span><h3 id="kb-textbook-title">添加教材（可跳过）</h3></div>
        <p>教材会先在当前方案中解析，确认图谱前不会进入课程公共知识库或 RAG。</p>
      </div>

      <div className="course-kb-wizard__upload">
        <input
          ref={inputRef}
          type="file"
          hidden
          multiple
          accept=".pdf,.docx,.txt,.md"
          onChange={(event) => {
            const files = Array.from(event.target.files || []);
            if (files.length) onUpload(files);
            event.target.value = "";
          }}
        />
        <button type="button" disabled={uploading || generating} onClick={() => inputRef.current?.click()}>
          <MaterialIcon name="upload_file" />{uploading ? "正在上传…" : "上传教材"}
        </button>
        <span>支持 PDF、DOCX、TXT、Markdown；单个文件不超过 50 MB</span>
      </div>

      {textbooks.length ? (
        <ul className="course-kb-wizard__textbooks">
          {textbooks.map((textbook) => (
            <li key={textbook.textbook_id} className={`is-${textbook.status}`}>
              <span className="course-kb-wizard__file-icon"><MaterialIcon name="menu_book" /></span>
              <div>
                <strong>{textbook.filename}</strong>
                <span>{formatBytes(textbook.size_bytes)} · {STATUS_LABELS[textbook.status]}{textbook.parse_result ? ` · ${textbook.parse_result.chapter_count} 章 / ${textbook.parse_result.chunk_count} 块` : ""}</span>
                {textbook.error?.message ? <small role="alert">{textbook.error.message}</small> : null}
                {textbook.parse_result?.warnings?.length ? <small>{textbook.parse_result.warnings.join("；")}</small> : null}
              </div>
              <div className="course-kb-wizard__file-actions">
                {textbook.status === "failed" ? <button type="button" onClick={() => onRetry(textbook.textbook_id)}>重试</button> : null}
                <button type="button" disabled={textbook.status === "parsing"} onClick={() => onRemove(textbook.textbook_id)}>移除</button>
              </div>
            </li>
          ))}
        </ul>
      ) : <div className="course-kb-wizard__empty">不上传教材也可以生成知识图谱，模型会依据课程信息和规模配置设计结构。</div>}

      {pending ? <p className="course-kb-wizard__hint">请等待已上传教材解析完成，再生成图谱草案。</p> : null}
      {failed ? <p className="course-kb-wizard__hint is-error">请重试或移除解析失败的教材。</p> : null}
      <div className="course-kb-wizard__footer is-split">
        <button type="button" className="course-kb-wizard__secondary" disabled={uploading || generating} onClick={onBack}>返回配置</button>
        <button type="button" className="course-kb-wizard__primary" disabled={uploading || generating || pending || failed} onClick={onGenerate}>
          {generating ? "模型正在生成图谱…" : textbooks.length ? "生成知识图谱草案" : "跳过教材并生成图谱"}
        </button>
      </div>
    </section>
  );
}
