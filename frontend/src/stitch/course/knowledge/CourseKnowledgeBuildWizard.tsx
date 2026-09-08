import { useEffect, useMemo, useRef, useState } from "react";

import { registerCreatedJob, useCourseJobs } from "../../../jobs/jobStore";
import { isActiveJob } from "../../../jobs/types";
import {
  confirmCourseKnowledgeGraph,
  generateCourseKnowledgeProposal,
  selectCourseKnowledgeProposal,
  getCourseKnowledgeBuild,
  removeCourseKnowledgeTextbook,
  retryCourseKnowledgeTextbook,
  saveCourseKnowledgeGraphDraft,
  startCourseKnowledgeBuild,
  uploadCourseKnowledgeTextbook,
} from "../../api/courses";
import { ApiError } from "../../api/client";
import type { CourseKnowledgeBuild, KnowledgeGraphNode } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { CourseKnowledgeProposalView } from "./CourseKnowledgeProposalView";
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
  const [step, setStep] = useState<"proposal" | "textbooks" | "graph">(
    build.graph_draft ? "graph" : build.knowledge_proposal ? "proposal" : "textbooks",
  );
  const config = build.config || DEFAULT_COURSE_KNOWLEDGE_CONFIG;
  const [requirements, setRequirements] = useState(build.knowledge_proposal?.requirements || "");
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

  async function chooseProposal(selection: { option_id?: string; item_ids?: string[] }) {
    setSaving(true); setError("");
    try {
      const updated = await selectCourseKnowledgeProposal(courseId, build.build_id, build.revision, selection);
      onBuildChange(updated); setGraphDraft(updated.graph_draft || null); setStep("graph");
    } catch (reason) { setError(explain(reason, "选择方案失败")); }
    finally { setSaving(false); }
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

  async function generateGraph() {
    setSubmittingGraph(true); setError("");
    try {
      const updated = await generateCourseKnowledgeProposal(courseId, build.build_id, build.revision, requirements);
      onBuildChange(updated); setGraphDraft(null); setStep("proposal");
    } catch (reason) { setError(explain(reason, "生成方案失败")); }
    finally { setSubmittingGraph(false); }
  }

  async function saveGraph(root: KnowledgeGraphNode) {
    setGraphBusy(true);
    setError("");
    try {
      const updated = await saveCourseKnowledgeGraphDraft(
        courseId,
        build.build_id,
        build.revision,
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
      let latest = build;
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
        <div><h2 id="kb-wizard-title">{build.baseline_graph ? "更新课程知识库" : "创建课程知识库"}</h2></div>
        <button type="button" aria-label="关闭构建向导" onClick={onClose}><MaterialIcon name="close" /></button>
      </header>
      <nav className="course-kb-wizard__steps" aria-label="更新步骤">
        <span className={step === "textbooks" ? "is-active" : ""}>1 需求与教材</span>
        <span className={step === "proposal" ? "is-active" : ""}>2 {build.baseline_graph ? "补充清单" : "大纲对比"}</span>
        <span className={step === "graph" ? "is-active" : ""}>3 确认目录</span>
      </nav>
      {step === "proposal" && build.knowledge_proposal ? (
        <CourseKnowledgeProposalView key={build.revision} proposal={build.knowledge_proposal} busy={saving} onSelect={selection => void chooseProposal(selection)} onBack={() => setStep("textbooks")} />
      ) : step === "textbooks" ? (<>
        <label className="course-kb-proposal__requirements">{build.baseline_graph ? "这次想补充什么？" : "这门课面向谁，希望覆盖哪些内容？"}
          <textarea value={requirements} onChange={event => setRequirements(event.target.value)} maxLength={4000}
            placeholder={build.baseline_graph ? "例如：检查现有资料，只补充循环结构的练习。留空则检查整体缺口。" : "可填写授课对象、学时或重点。留空则根据课程介绍和教学目标规划。"} />
        </label>
        <CourseKnowledgeTextbookStep
          textbooks={build.textbooks || []}
          uploading={uploading}
          generating={generating}
          generateLabel={build.baseline_graph ? "分析补充建议" : "生成三份大纲"}
          onBack={onClose}
          onUpload={(files) => void upload(files)}
          onRetry={(id) => void retry(id)}
          onRemove={(id) => void remove(id)}
          onGenerate={() => void generateGraph()}
        />
      </>) : graphDraft && build.graph_draft ? (
        <CourseKnowledgeGraphReviewStep
          flexiblePlanning={Boolean(build.knowledge_proposal)}
          root={graphDraft}
          savedRoot={build.graph_draft}
          baselineRoot={build.baseline_graph || null}
          config={build.config || config}
          textbooks={build.textbooks || []}
          busy={graphBusy || generating}
          onChange={setGraphDraft}
          onBack={() => setStep(build.knowledge_proposal ? "proposal" : "textbooks")}
          onSave={saveGraph}
          onRegenerate={() => void generateGraph()}
          onConfirmAndStart={(root) => void confirmAndStart(root)}
        />
      ) : null}

      {build.graph_draft && step !== "graph" ? <div className="course-kb-wizard__ready"><MaterialIcon name="account_tree" /><div><strong>课程目录已准备好</strong><span>请检查课程目录，确认后开始补充学习资料。</span></div><button type="button" onClick={() => setStep("graph")}>开始审核</button></div> : null}
      {build.graph_generation_error?.message ? <div className="course-kb-wizard__error" role="alert">{build.graph_generation_error.message}</div> : null}
      {error ? <div className="course-kb-wizard__error" role="alert">{error}</div> : null}
    </div>
  );
}
