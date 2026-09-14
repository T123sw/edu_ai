import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { registerCreatedJob, useCourseJobs } from "../../../jobs/jobStore";
import { isActiveJob } from "../../../jobs/types";
import {
  createCourseKnowledgeBuildDraft,
  getCourseKnowledgeBuild,
  listCourseKnowledgeVersions,
  retryCourseKnowledgeBuild,
} from "../../api/courses";
import type { CourseKnowledgeBuild, CourseKnowledgeGraphVersion } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { CourseKnowledgeBuildWizard } from "./CourseKnowledgeBuildWizard";
import { LearningResourceGenerationPanel } from "./LearningResourceGenerationPanel";
import "./CourseKnowledgeBuildCard.css";

const PHASE_LABELS: Record<string, string> = {
  queued: "正在排队",
  running: "正在更新知识库",
  textbook_discovery: "正在发现完整教材",
  textbook_ingestion: "正在整理教材",
  textbook_mapping: "正在将教材映射到知识点",
  gap_search: "正在补充知识点网页",
  ai_fallback: "正在补充知识内容",
  source_audit: "正在查找合适的课程资料",
  indexing: "正在整理课程资料",
  model_fallback: "正在补充缺少的内容",
  quality_check: "正在检查内容质量",
  quality_blocked: "内容需要进一步完善",
  publishing: "即将完成",
  completed: "更新完成",
};

const QUALITY_LABELS: Record<string, string> = {
  graph_schema: "目录结构",
  graph_scale: "课程规模",
  textbook_mapping_quality: "教材映射",
  non_ai_coverage: "外部资料覆盖",
  content_sufficiency: "内容充足度",
  ai_fallback_policy: "AI 补充策略",
  provenance_integrity: "来源追溯",
  index_integrity: "索引完整性",
  publication_atomicity: "发布完整性",
  required_source_policy: "限定来源",
  preferred_source_policy: "优先来源",
  intent_adherence: "教师交付要求",
};

function qualityDetail(check: NonNullable<CourseKnowledgeBuild["quality_checks"]>[number]) {
  if (check.status === "passed") return "已满足";
  const decision = String(check.details?.decision || "").trim();
  if (decision) return decision;
  const missing = Array.isArray(check.details?.missing_deliverables)
    ? check.details.missing_deliverables as Array<{ type?: string; required?: number; actual?: number }>
    : [];
  if (missing.length) {
    return missing.map(item => `${item.type || "交付物"}：需要 ${item.required || 0}，已有 ${item.actual || 0}`).join("；");
  }
  return "未满足，需调整需求或补齐内容";
}

type Props = {
  courseId: string;
  documentCount: number;
  canBuild: boolean;
  requestedAction?: string | null;
  title?: string;
  toolbarEnd?: ReactNode;
};

function storageKey(courseId: string) {
  return `edu-ai:course-kb-build:${courseId}`;
}

export function CourseKnowledgeBuildCard({ courseId, documentCount, canBuild, requestedAction, title = "课程知识库", toolbarEnd }: Props) {
  const jobs = useCourseJobs(courseId, "build_knowledge_index");
  const activeJob = useMemo(() => jobs.find(isActiveJob) ?? null, [jobs]);
  const latestJob = jobs[0] ?? null;
  const [plan, setPlan] = useState<CourseKnowledgeBuild | null>(null);
  const [planning, setPlanning] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [resourceConfigOpen, setResourceConfigOpen] = useState(false);
  const [versions, setVersions] = useState<CourseKnowledgeGraphVersion[]>([]);
  const [retrying, setRetrying] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const cardRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (requestedAction !== "build") return;
    cardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    cardRef.current?.focus({ preventScroll: true });
  }, [requestedAction]);

  const linkedBuildId = new URLSearchParams(window.location.hash.split("?")[1] || "").get("build_id");

  useEffect(() => {
    const buildId = linkedBuildId || window.localStorage.getItem(storageKey(courseId));
    if (linkedBuildId) setWizardOpen(true);
    if (!buildId) {
      setPlan(null);
      return;
    }
    let canceled = false;
    void getCourseKnowledgeBuild(courseId, buildId)
      .then((value) => { if (!canceled) { setPlan(value); window.localStorage.setItem(storageKey(courseId), value.build_id); } })
      .catch(() => { window.localStorage.removeItem(storageKey(courseId)); });
    return () => { canceled = true; };
  }, [courseId, linkedBuildId, latestJob?.status, latestJob?.updated_at]);

  useEffect(() => {
    let canceled = false;
    void listCourseKnowledgeVersions(courseId)
      .then((value) => { if (!canceled) setVersions(value); })
      .catch(() => { if (!canceled) setVersions([]); });
    return () => { canceled = true; };
  }, [courseId, linkedBuildId, latestJob?.status, latestJob?.updated_at]);

  async function buildKnowledgeBase() {
    if (!canBuild || planning || activeJob) return;
    setSubmitError("");

    try {
      if (plan?.status === "draft") {
        setResourceConfigOpen(false);
        setWizardOpen(true);
        return;
      }
      setPlanning(true);
      const buildPlan = await createCourseKnowledgeBuildDraft(courseId);
      window.localStorage.setItem(storageKey(courseId), buildPlan.build_id);
      setPlan(buildPlan);
      setResourceConfigOpen(false);
      setWizardOpen(true);
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : "知识库更新失败，请稍后重试。");
    } finally {
      setPlanning(false);
    }
  }

  async function retryBuild() {
    if (!plan || !["blocked", "failed"].includes(plan.status) || retrying) return;
    setRetrying(true);
    setSubmitError("");
    try {
      const job = await retryCourseKnowledgeBuild(courseId, plan.build_id);
      registerCreatedJob(job);
      setPlan(await getCourseKnowledgeBuild(courseId, plan.build_id));
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : "重试构建失败，请稍后再试。");
    } finally {
      setRetrying(false);
    }
  }

  const status = activeJob ?? latestJob;
  const isWorking = Boolean(activeJob) || planning;
  const failed = status?.status === "failed" || status?.status === "partially_succeeded";
  const succeeded = status?.status === "succeeded";
  const hasKnowledgeBase = documentCount > 0 || versions.length > 0;
  const statusText = planning
    ? "正在分析课程内容"
    : status
        ? PHASE_LABELS[status.step] || PHASE_LABELS[status.status] || status.message || "正在处理"
        : documentCount
          ? "知识库已可用"
          : "尚未构建";
  const buttonText = planning
    ? "正在准备…"
    : activeJob
      ? "正在更新…"
      : plan?.status === "draft"
        ? "继续构建方案"
        : plan && ["blocked", "failed"].includes(plan.status)
          ? "新建方案调整配置"
      : hasKnowledgeBase
          ? "更新知识库"
          : "一键构建知识库";

  return (
    <section ref={cardRef} tabIndex={-1} className="course-kb-builder" aria-labelledby="course-kb-builder-title">
      <header className="course-kb-builder__header">
        <span className="course-kb-builder__icon" aria-hidden="true">
          <MaterialIcon name="auto_awesome" />
        </span>
        <div className="course-kb-builder__heading">
          <h2 id="course-kb-builder-title">{title}</h2>
        </div>
        <span className={`course-kb-builder__badge${isWorking ? " is-working" : succeeded ? " is-success" : failed ? " is-error" : ""}`}>
          {isWorking ? "更新中" : hasKnowledgeBase || succeeded ? "已构建" : "未构建"}
        </span>
      </header>

      {isWorking ? (
        <div className="course-kb-builder__progress" aria-live="polite">
          <div>
            <span>{statusText}</span>
            <strong>{status?.progress ?? 0}%</strong>
          </div>
          <div className="course-kb-builder__progress-track">
            <span style={{ width: `${Math.max(4, Math.min(100, status?.progress ?? 4))}%` }} />
          </div>
          <small>可以离开此页面，完成后系统会通知你。</small>
        </div>
      ) : failed ? (
        <div className="course-kb-builder__notice is-error" role="alert">
          <MaterialIcon name="error" />
          <div><strong>本次更新未完成</strong><span>{status?.error_message || status?.error || "请稍后重试。"}</span></div>
        </div>
      ) : null}

      {plan?.quality_checks?.length ? (
        <section className="course-kb-builder__quality" aria-label="知识库质量检查">
          <h3>本次构建质量检查{plan.quality_score != null ? ` · ${plan.quality_score} 分` : ""}</h3>
          <ul>{plan.quality_checks.map(check => <li key={check.check_type} className={check.status === "passed" ? "is-passed" : check.status === "needs_teacher_decision" ? "is-decision" : "is-failed"}>
            <MaterialIcon name={check.status === "passed" ? "check_circle" : check.status === "needs_teacher_decision" ? "help" : "error"} />
            <strong>{QUALITY_LABELS[check.check_type] || check.check_type}</strong>
            <span>{qualityDetail(check)}</span>
          </li>)}</ul>
        </section>
      ) : null}

      <div className="course-kb-builder__actions">
        {canBuild && plan && ["blocked", "failed"].includes(plan.status) ? (
          <button type="button" className="course-kb-builder__primary" disabled={retrying || isWorking} onClick={() => void retryBuild()}>
            <MaterialIcon name="replay" />
            {retrying ? "正在重新排队…" : "重试本方案"}
          </button>
        ) : null}
        {canBuild ? (
          <button type="button" className="course-kb-builder__primary" disabled={isWorking} onClick={() => void buildKnowledgeBase()}>
            <MaterialIcon name={documentCount ? "refresh" : "auto_awesome"} />
            {buttonText}
          </button>
        ) : null}
        {canBuild ? (
          <button
            type="button"
            className="course-kb-builder__secondary"
            aria-expanded={resourceConfigOpen}
            onClick={() => {
              setWizardOpen(false);
              setResourceConfigOpen((open) => !open);
            }}
          >
            <MaterialIcon name="auto_awesome" />
            学习资源生成
          </button>
        ) : null}
      </div>

      {toolbarEnd && <div className="course-kb-builder__toolbar-end">{toolbarEnd}</div>}

      {resourceConfigOpen ? (
        <LearningResourceGenerationPanel onClose={() => setResourceConfigOpen(false)} />
      ) : null}

      {wizardOpen && plan?.status === "draft" ? (
        <CourseKnowledgeBuildWizard
          courseId={courseId}
          build={plan}
          onBuildChange={setPlan}
          onClose={() => setWizardOpen(false)}
        />
      ) : null}

      {plan?.error?.message ? <div className="course-kb-builder__error" role="alert">{plan.error.message}</div> : null}
      {submitError ? <div className="course-kb-builder__error" role="alert">{submitError}</div> : null}
    </section>
  );
}
