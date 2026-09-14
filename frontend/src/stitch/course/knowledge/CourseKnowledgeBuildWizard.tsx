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

function firstKnowledgePointLabel(root?: KnowledgeGraphNode | null): string {
  if (!root) return "指定知识点";
  if (!root.children?.length) return root.label;
  for (const child of root.children) {
    const label = firstKnowledgePointLabel(child);
    if (label) return label;
  }
  return root.label;
}

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
  const isSupplement = Boolean(build.baseline_graph);
  const courseTitle = String(build.course_snapshot?.title || "本课程");
  const exampleKnowledgePoint = firstKnowledgePointLabel(build.baseline_graph);
  const requirementsPlaceholder = isSupplement
    ? `例如：本次只补充“${exampleKnowledgePoint}”知识点\n补充内容：概念辨析、2 个典型案例、3 道带解析的练习\n保留范围：保留现有目录，不重建其他章节\n资料偏好：优先使用已上传教材，资料不足时再检索公开来源`
    : `例如：${courseTitle}面向仅具备入门基础的本专业一年级学生，共 16 课时\n重点内容：基础概念、核心方法和典型应用\n学习资料：每个知识点配 1 个案例和 2 道练习\n不包含：暂不涉及进阶专题\n其他要求：优先使用已上传教材，内容使用简体中文`;
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
        <div><h2 id="kb-wizard-title">{isSupplement ? "更新课程知识库" : "创建课程知识库"}</h2></div>
        <button type="button" aria-label="关闭构建向导" onClick={onClose}><MaterialIcon name="close" /></button>
      </header>
      <nav className="course-kb-wizard__steps" aria-label="更新步骤">
        <span className={step === "textbooks" ? "is-active" : ""}>1 需求与教材</span>
        <span className={step === "proposal" ? "is-active" : ""}>2 {isSupplement ? "补充清单" : "大纲对比"}</span>
        <span className={step === "graph" ? "is-active" : ""}>3 确认目录</span>
      </nav>
      {step === "proposal" && build.knowledge_proposal ? (
        <CourseKnowledgeProposalView key={build.revision} proposal={build.knowledge_proposal} busy={saving} onSelect={selection => void chooseProposal(selection)} onBack={() => setStep("textbooks")} />
      ) : step === "textbooks" ? (<>
        <label className="course-kb-proposal__requirements">
          <strong>{isSupplement ? "这次想补充什么？" : "这门课面向谁，希望覆盖哪些内容？"}</strong>
          <textarea value={requirements} onChange={event => setRequirements(event.target.value)} maxLength={4000}
            placeholder={requirementsPlaceholder} />
        </label>
        <CourseKnowledgeTextbookStep
          textbooks={build.textbooks || []}
          uploading={uploading}
          generating={generating}
          generateLabel={isSupplement ? "分析补充建议" : "生成三份大纲"}
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
