import { useEffect, useMemo, useRef, useState } from "react";

import { registerCreatedJob, useCourseJobs } from "../../../jobs/jobStore";
import { isActiveJob } from "../../../jobs/types";
import {
  confirmCourseKnowledgeGraph,
  generateCourseKnowledgeGraphDraft,
  getCourseKnowledgeBuild,
  removeCourseKnowledgeTextbook,
  retryCourseKnowledgeTextbook,
  saveCourseKnowledgeGraphDraft,
  startCourseKnowledgeBuild,
  updateCourseKnowledgeBuildDraft,
  uploadCourseKnowledgeTextbook,
} from "../../api/courses";
import { ApiError } from "../../api/client";
import type { CourseKnowledgeBuild, CourseKnowledgeBuildConfig, KnowledgeGraphNode } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { CourseKnowledgeBuildConfigStep } from "./CourseKnowledgeBuildConfigStep";
import { CourseKnowledgeGraphReviewStep } from "./CourseKnowledgeGraphReviewStep";
import { CourseKnowledgeTextbookStep } from "./CourseKnowledgeTextbookStep";
import { DEFAULT_COURSE_KNOWLEDGE_CONFIG } from "./courseKnowledgeBuildState";
import { graphDraftEqual } from "./courseKnowledgeGraphDraft";

type Props = {
  courseId: string;
  build: CourseKnowledgeBuild;
  onBuildChange: (build: CourseKnowledgeBuild) => void;
  onClose: () => void;
};

export function CourseKnowledgeBuildWizard({ courseId, build, onBuildChange, onClose }: Props) {
  const [step, setStep] = useState<"config" | "textbooks" | "graph">(
    build.graph_draft ? "graph" : build.textbooks?.length ? "textbooks" : "config",
  );
  const [config, setConfig] = useState<CourseKnowledgeBuildConfig>(build.config || DEFAULT_COURSE_KNOWLEDGE_CONFIG);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [submittingGraph, setSubmittingGraph] = useState(false);
  const [graphDraft, setGraphDraft] = useState<KnowledgeGraphNode | null>(build.graph_draft || null);
  const lastSavedGraph = useRef<KnowledgeGraphNode | null>(build.graph_draft || null);
  const [graphBusy, setGraphBusy] = useState(false);
  const [error, setError] = useState("");
  const jobs = useCourseJobs(courseId);
  const relevantJobs = useMemo(
    () => jobs.filter((job) => String(job.input_summary?.build_id || "") === build.build_id),
    [build.build_id, jobs],
  );
  const activeGraphJob = relevantJobs.find((job) => job.kind === "generate_graph" && isActiveJob(job));
  const latestRelevantJob = relevantJobs[0];

  useEffect(() => {
    if (build.config) setConfig(build.config);
  }, [build.config]);

  useEffect(() => {
    if (!build.graph_draft) return;
    const incomingGraphDraft = build.graph_draft;
    const previouslySaved = lastSavedGraph.current;
    lastSavedGraph.current = incomingGraphDraft;
    setGraphDraft((current) => {
      if (!current || !previouslySaved || graphDraftEqual(current, previouslySaved)) {
        return incomingGraphDraft;
      }
      return current;
    });
    setStep("graph");
  }, [build.graph_draft]);

  useEffect(() => {
    if (!latestRelevantJob) return;
    let canceled = false;
    void getCourseKnowledgeBuild(courseId, build.build_id)
      .then((current) => {
        if (!canceled) {
          onBuildChange(current);
          if (current.graph_draft) {
            setSubmittingGraph(false);
            setStep("graph");
          }
        }
      })
      .catch(() => undefined);
    return () => { canceled = true; };
  }, [build.build_id, courseId, latestRelevantJob, onBuildChange]);

  function explain(reason: unknown, fallback: string) {
    if (reason instanceof ApiError && reason.status === 409) {
      return "方案已在其他页面或后台任务中更新，请重新加载最新版本后再操作。";
    }
    return reason instanceof Error ? reason.message : fallback;
  }

  async function saveAndContinue() {
    setSaving(true);
    setError("");
    try {
      const latest = await getCourseKnowledgeBuild(courseId, build.build_id);
      const updated = await updateCourseKnowledgeBuildDraft(
        courseId,
        build.build_id,
        latest.revision,
        config,
      );
      onBuildChange(updated);
      setStep("textbooks");
    } catch (reason) {
      setError(explain(reason, "保存构建配置失败"));
    } finally {
      setSaving(false);
    }
  }

  async function upload(files: File[]) {
    setUploading(true);
    setError("");
    try {
      for (const file of files) {
        const latest = await getCourseKnowledgeBuild(courseId, build.build_id);
        const response = await uploadCourseKnowledgeTextbook(
          courseId,
          build.build_id,
          latest.revision,
          file,
        );
        registerCreatedJob(response.job);
        onBuildChange(response.build);
      }
    } catch (reason) {
      setError(explain(reason, "上传教材失败"));
    } finally {
      setUploading(false);
    }
  }

  async function retry(textbookId: string) {
    setError("");
    try {
      const latest = await getCourseKnowledgeBuild(courseId, build.build_id);
      const response = await retryCourseKnowledgeTextbook(
        courseId,
        build.build_id,
        textbookId,
        latest.revision,
      );
      registerCreatedJob(response.job);
      onBuildChange(response.build);
    } catch (reason) {
      setError(explain(reason, "重试教材解析失败"));
    }
  }

  async function remove(textbookId: string) {
    setError("");
    try {
      const latest = await getCourseKnowledgeBuild(courseId, build.build_id);
      onBuildChange(await removeCourseKnowledgeTextbook(
        courseId,
        build.build_id,
        textbookId,
        latest.revision,
      ));
    } catch (reason) {
      setError(explain(reason, "移除教材失败"));
    }
  }

  async function generateGraph(targetModuleId?: string) {
    setSubmittingGraph(true);
    setError("");
    try {
      const latest = await getCourseKnowledgeBuild(courseId, build.build_id);
      onBuildChange(latest);
      const job = await generateCourseKnowledgeGraphDraft(
        courseId,
        build.build_id,
        latest.revision,
        targetModuleId,
      );
      registerCreatedJob(job);
    } catch (reason) {
      setSubmittingGraph(false);
      setError(explain(reason, "生成知识图谱草案失败"));
    }
  }

  async function saveGraph(root: KnowledgeGraphNode) {
    setGraphBusy(true);
    setError("");
    try {
      const latest = await getCourseKnowledgeBuild(courseId, build.build_id);
      const updated = await saveCourseKnowledgeGraphDraft(
        courseId,
        build.build_id,
        latest.revision,
        root,
      );
      onBuildChange(updated);
      setGraphDraft(updated.graph_draft || root);
      return updated.graph_draft || root;
    } catch (reason) {
      setError(explain(reason, "保存知识图谱草案失败"));
      return root;
    } finally {
      setGraphBusy(false);
    }
  }

  async function confirmAndStart(root: KnowledgeGraphNode) {
    setGraphBusy(true);
    setError("");
    try {
      let latest = await getCourseKnowledgeBuild(courseId, build.build_id);
      if (!latest.graph_draft || !graphDraftEqual(root, latest.graph_draft)) {
        latest = await saveCourseKnowledgeGraphDraft(
          courseId,
          build.build_id,
          latest.revision,
          root,
        );
      }
      const confirmed = await confirmCourseKnowledgeGraph(
        courseId,
        build.build_id,
        latest.revision,
      );
      onBuildChange(confirmed);
      const job = await startCourseKnowledgeBuild(courseId, build.build_id);
      registerCreatedJob(job);
      onClose();
    } catch (reason) {
      setError(explain(reason, "确认图谱并启动构建失败"));
    } finally {
      setGraphBusy(false);
    }
  }

  const generating = submittingGraph || Boolean(activeGraphJob);

  return (
    <div className="course-kb-wizard" role="dialog" aria-modal="false" aria-labelledby="kb-wizard-title">
      <header className="course-kb-wizard__header">
        <div><span>构建方案 · 修订 {build.revision}</span><h2 id="kb-wizard-title">{build.baseline_graph ? "课程知识库增量更新向导" : "课程知识库构建向导"}</h2></div>
        <button type="button" aria-label="关闭构建向导" onClick={onClose}><MaterialIcon name="close" /></button>
      </header>
      <nav className="course-kb-wizard__steps" aria-label="构建步骤">
        <span className={step === "config" ? "is-active" : "is-done"}>1 配置</span>
        <span className={step === "textbooks" ? "is-active" : step === "graph" ? "is-done" : ""}>2 教材（可选）</span>
        <span className={step === "graph" ? "is-active" : build.graph_draft ? "is-done" : ""}>3 图谱审核</span>
      </nav>

      {step === "config" ? (
        <CourseKnowledgeBuildConfigStep config={config} saving={saving} onChange={setConfig} onContinue={() => void saveAndContinue()} />
      ) : step === "textbooks" ? (
        <CourseKnowledgeTextbookStep
          textbooks={build.textbooks || []}
          uploading={uploading}
          generating={generating}
          onBack={() => setStep("config")}
          onUpload={(files) => void upload(files)}
          onRetry={(id) => void retry(id)}
          onRemove={(id) => void remove(id)}
          onGenerate={() => void generateGraph()}
        />
      ) : graphDraft && build.graph_draft ? (
        <CourseKnowledgeGraphReviewStep
          root={graphDraft}
          savedRoot={build.graph_draft}
          baselineRoot={build.baseline_graph || null}
          config={build.config || config}
          textbooks={build.textbooks || []}
          busy={graphBusy || generating}
          onChange={setGraphDraft}
          onBack={() => setStep("textbooks")}
          onSave={saveGraph}
          onRegenerate={(moduleId) => void generateGraph(moduleId)}
          onConfirmAndStart={(root) => void confirmAndStart(root)}
        />
      ) : null}

      {build.graph_draft && step !== "graph" ? <div className="course-kb-wizard__ready"><MaterialIcon name="account_tree" /><div><strong>模型图谱草案已生成</strong><span>进入图谱审核后可编辑并确认，确认前不会搜索网络或正式入库。</span></div><button type="button" onClick={() => setStep("graph")}>开始审核</button></div> : null}
      {build.graph_generation_error?.message ? <div className="course-kb-wizard__error" role="alert">{build.graph_generation_error.message}</div> : null}
      {error ? <div className="course-kb-wizard__error" role="alert">{error}</div> : null}
    </div>
  );
}
