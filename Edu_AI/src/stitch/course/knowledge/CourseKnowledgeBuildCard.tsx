import { useEffect, useMemo, useRef, useState } from "react";

import { registerCreatedJob, useCourseJobs } from "../../../jobs/jobStore";
import { isActiveJob } from "../../../jobs/types";
import {
  getCourseKnowledgeBuild,
  listCourseKnowledgeVersions,
  previewCourseKnowledgeBuild,
  rollbackCourseKnowledgeVersion,
  startCourseKnowledgeBuild,
} from "../../api/courses";
import type { CourseKnowledgeBuild, CourseKnowledgeGraphVersion } from "../../api/types";
import { MaterialIcon } from "../../shared";

const PHASE_LABELS: Record<string, string> = {
  queued: "等待后台处理",
  running: "正在构建",
  source_audit: "核验来源许可与抓取约束",
  indexing: "抓取、清洗并建立课程索引",
  quality_check: "执行质量门禁",
  publishing: "原子发布新版本",
  completed: "构建完成",
};

type Props = {
  courseId: string;
  documentCount: number;
  canBuild: boolean;
  requestedAction?: string | null;
};

function storageKey(courseId: string) {
  return `edu-ai:course-kb-build:${courseId}`;
}

export function CourseKnowledgeBuildCard({ courseId, documentCount, canBuild, requestedAction }: Props) {
  const jobs = useCourseJobs(courseId, "build_knowledge_index");
  const activeJob = useMemo(() => jobs.find(isActiveJob) ?? null, [jobs]);
  const latestJob = jobs[0] ?? null;
  const [plan, setPlan] = useState<CourseKnowledgeBuild | null>(null);
  const [planning, setPlanning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [versions, setVersions] = useState<CourseKnowledgeGraphVersion[]>([]);
  const [rollingBack, setRollingBack] = useState<number | null>(null);
  const [submitError, setSubmitError] = useState("");
  const cardRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (requestedAction !== "build") return;
    cardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    cardRef.current?.focus({ preventScroll: true });
  }, [requestedAction]);

  useEffect(() => {
    const buildId = window.localStorage.getItem(storageKey(courseId));
    if (!buildId) {
      setPlan(null);
      return;
    }
    let canceled = false;
    void getCourseKnowledgeBuild(courseId, buildId)
      .then((value) => { if (!canceled) setPlan(value); })
      .catch(() => { window.localStorage.removeItem(storageKey(courseId)); });
    return () => { canceled = true; };
  }, [courseId, latestJob?.status, latestJob?.updated_at]);

  useEffect(() => {
    let canceled = false;
    void listCourseKnowledgeVersions(courseId)
      .then((value) => { if (!canceled) setVersions(value); })
      .catch(() => { if (!canceled) setVersions([]); });
    return () => { canceled = true; };
  }, [courseId, latestJob?.status, latestJob?.updated_at]);

  async function createPlan() {
    if (!canBuild || planning || activeJob) return;
    setPlanning(true);
    setSubmitError("");
    try {
      const value = await previewCourseKnowledgeBuild(courseId);
      window.localStorage.setItem(storageKey(courseId), value.build_id);
      setPlan(value);
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : "生成知识库构建方案失败");
    } finally {
      setPlanning(false);
    }
  }

  async function submitBuild() {
    if (!canBuild || !plan || activeJob || submitting) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      registerCreatedJob(await startCourseKnowledgeBuild(courseId, plan.build_id));
      setPlan({ ...plan, status: "queued", phase: "queued", progress: 0 });
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : "提交知识库构建任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function rollbackVersion(version: number) {
    if (!canBuild || rollingBack !== null) return;
    if (!window.confirm(`确认将课程知识图谱回滚到版本 ${version}？系统会保留当前版本并创建新的发布版本。`)) return;
    setRollingBack(version);
    setSubmitError("");
    try {
      await rollbackCourseKnowledgeVersion(courseId, version);
      setVersions(await listCourseKnowledgeVersions(courseId));
      window.dispatchEvent(new CustomEvent("edu-ai:knowledge-document-updated", { detail: { courseId } }));
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : "回滚知识图谱版本失败");
    } finally {
      setRollingBack(null);
    }
  }

  const approvedSources = plan?.source_candidates.filter((item) => item.selected && item.review_status === "approved") ?? [];
  const rejectedCount = plan?.source_candidates.filter((item) => item.review_status === "rejected").length ?? 0;
  const status = activeJob ?? latestJob;
  const statusText = status
    ? PHASE_LABELS[status.step] || status.message || PHASE_LABELS[status.status] || status.status
    : "尚未启动构建";

  return (
    <section ref={cardRef} tabIndex={-1} className="knowledge-build-card" aria-labelledby="knowledge-build-title">
      <div className="knowledge-build-card__intro">
        <span><MaterialIcon name="auto_awesome" /></span>
        <div>
          <p>课程语义驱动建库</p>
          <h2 id="knowledge-build-title">{documentCount ? "更新课程知识库" : "一键构建课程知识库"}</h2>
          <small>先根据课程标题、目标、学段和语言生成知识主题，审核来源与许可，再在后台抓取、索引、质检并发布新版本。</small>
        </div>
      </div>

      {plan ? (
        <div className="knowledge-build-plan">
          <div className="knowledge-build-plan__summary">
            <span><strong>{plan.topics.length}</strong> 个知识主题</span>
            <span><strong>{approvedSources.length}</strong> 个审核通过来源</span>
            <span><strong>{rejectedCount}</strong> 个来源已拦截</span>
            {plan.quality_score != null ? <span><strong>{Math.round(plan.quality_score)}</strong> 质量分</span> : null}
          </div>
          <div className="knowledge-build-plan__topics" aria-label="课程知识主题">
            {plan.topics.map((topic) => <span key={topic.topic_id}>{topic.title}</span>)}
          </div>
          {approvedSources.length ? (
            <ul className="knowledge-build-plan__sources">
              {approvedSources.slice(0, 6).map((source) => (
                <li key={source.candidate_id}>
                  <MaterialIcon name="verified" />
                  <div><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a><small>{source.domain} · {source.license_name}</small></div>
                  <span>{Math.round(source.relevance_score * 100)}%</span>
                </li>
              ))}
            </ul>
          ) : <p className="knowledge-build-plan__empty">暂未找到通过许可与相关性审核的来源。可调整课程目标后重新规划，或上传已获授权的课程资料。</p>}
          {plan.warnings.length ? <div className="knowledge-build-plan__warnings">{plan.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div> : null}
          {plan.error?.message ? <div className="knowledge-build-card__error" role="alert">{plan.error.message}</div> : null}
        </div>
      ) : null}

      {status ? (
        <div className={`knowledge-build-card__status is-${status.status}`}>
          <div><strong>{statusText}</strong><span>{status.progress}%</span></div>
          <div className="knowledge-build-card__progress"><span style={{ width: `${Math.max(0, Math.min(100, status.progress))}%` }} /></div>
          {status.status === "failed" || status.status === "partially_succeeded" ? (
            <p>{status.error_message || status.error || "构建未完整完成，可在任务中心查看原因并重试。"}</p>
          ) : status.status === "succeeded" ? <p>质量门禁已通过，新知识图谱版本已发布，课程资料与问答检索已刷新。</p> : null}
        </div>
      ) : null}

      {versions.length ? (
        <div className="knowledge-build-versions">
          <div><strong>已发布版本</strong><small>回滚会复制目标版本为新的当前版本，历史记录不会被覆盖。</small></div>
          <ul>
            {versions.slice(0, 4).map((version, index) => (
              <li key={version.version}>
                <span>v{version.version}{index === 0 ? " · 当前" : ""}</span>
                <small>{version.node_count} 个节点 · {new Date(version.published_at || version.created_at).toLocaleString()}</small>
                {index > 0 && canBuild ? <button type="button" disabled={rollingBack !== null} onClick={() => void rollbackVersion(version.version)}>{rollingBack === version.version ? "回滚中…" : "回滚到此版本"}</button> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="knowledge-build-card__actions">
        {canBuild ? (
          plan?.status === "draft" && approvedSources.length ? (
            <button type="button" className="is-primary" disabled={Boolean(activeJob) || submitting} onClick={() => void submitBuild()}>
              {submitting ? "正在提交…" : "确认来源并开始构建"}
            </button>
          ) : (
            <button type="button" className="is-primary" disabled={Boolean(activeJob) || planning} onClick={() => void createPlan()}>
              {planning ? "正在搜索并审核来源…" : plan ? "重新生成构建方案" : "分析课程并生成方案"}
            </button>
          )
        ) : <p>你在这门课程中只有只读权限。</p>}
        {status ? <button type="button" onClick={() => window.dispatchEvent(new Event("edu-ai:open-job-center"))}>在任务中心查看</button> : null}
      </div>
      {submitError ? <div className="knowledge-build-card__error" role="alert">{submitError}</div> : null}
    </section>
  );
}
