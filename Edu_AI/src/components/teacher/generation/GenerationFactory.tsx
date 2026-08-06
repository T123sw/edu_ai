import { useEffect, useState } from "react";

import { getKnowledgeBaseDocuments } from "../../../stitch/api/courses";
import type { KnowledgeBaseDocument } from "../../../stitch/api/types";
import { MaterialIcon } from "../../../stitch/shared";
import { GenerationConfigShell } from "./GenerationConfigShell";
import { GenerationSourceSelector, type GenerationSourceSelection } from "./GenerationSourceSelector";
import { GenerationTaskStatus } from "./GenerationTaskStatus";
import { generationRegistry, getGenerationResource, type GenerationResourceType } from "./generationRegistry";
import { useGenerationSubmission, type GenerationDraft } from "./useGenerationSubmission";
import "./generationFactory.css";

export function GenerationFactory({ courseId }: { courseId?: string }) {
  const [step, setStep] = useState(1);
  const [resourceType, setResourceType] = useState<GenerationResourceType>("report");
  const [source, setSource] = useState<GenerationSourceSelection>({ mode: "course_auto", selectedDocumentIds: [] });
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("本科生");
  const [requirements, setRequirements] = useState("");
  const submission = useGenerationSubmission(courseId);
  const resource = getGenerationResource(resourceType);

  useEffect(() => {
    if (!courseId) return;
    void getKnowledgeBaseDocuments(courseId).then(setDocuments).catch(() => setDocuments([]));
  }, [courseId]);

  useEffect(() => {
    if (!submission.retainedDraft) return;
    const draft = submission.retainedDraft;
    setResourceType(draft.resourceType);
    setSource(draft.source);
    setTopic(draft.topic);
    setAudience(draft.audience);
    setRequirements(draft.requirements);
  }, [submission.retainedDraft]);

  const draft: GenerationDraft = { resourceType, source, topic, audience, requirements };
  const canContinue = step === 1 || (step === 2 ? source.mode !== "selected_documents" || source.selectedDocumentIds.length > 0 : topic.trim().length > 0);
  const footer = (
    <div className="generation-factory__footer">
      <button type="button" disabled={step === 1} onClick={() => setStep((current) => Math.max(1, current - 1))}>上一步</button>
      {step < 4 ? <button type="button" className="is-primary" disabled={!canContinue} onClick={() => setStep((current) => Math.min(4, current + 1))}>下一步</button> : <button type="button" className="is-primary" disabled={!topic.trim() || submission.submitting} onClick={() => void submission.submit(draft)}>{submission.submitting ? "正在提交…" : "开始后台生成"}</button>}
    </div>
  );

  return (
    <div className="generation-factory" data-testid="generation-factory">
      {step === 1 ? (
        <GenerationConfigShell step={step} title="选择资源类型" description="九类资源使用同一资料范围、配置和后台任务流程。" footer={footer}>
          <div className="generation-factory__registry">{generationRegistry.map((item) => <button key={item.resourceType} type="button" aria-pressed={resourceType === item.resourceType} onClick={() => setResourceType(item.resourceType)} style={{ "--resource-accent": item.accent } as React.CSSProperties}><MaterialIcon name={item.icon} /><strong>{item.label}</strong><small>{item.description}</small></button>)}</div>
        </GenerationConfigShell>
      ) : step === 2 ? (
        <GenerationConfigShell step={step} title="确认资料范围" description={`为“${resource.label}”选择本次生成可以使用的课程资料。`} footer={footer}><GenerationSourceSelector documents={documents} value={source} onChange={setSource} /></GenerationConfigShell>
      ) : step === 3 ? (
        <GenerationConfigShell step={step} title={`配置${resource.label}`} description="先填写最小必要信息；每类资源的精确配置会在此处展开。" footer={footer}>
          <div className="generation-factory__form"><label><span>主题 *</span><input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="输入本次资源的主题" /></label><label><span>适用对象</span><input value={audience} onChange={(event) => setAudience(event.target.value)} /></label><label><span>补充要求</span><textarea value={requirements} onChange={(event) => setRequirements(event.target.value)} placeholder="可选：重点、结构、风格或课堂要求" /></label></div>
        </GenerationConfigShell>
      ) : (
        <GenerationConfigShell step={step} title="确认并生成" description="任务提交后可以关闭页面；进度和结果会保留在课程任务中心。" footer={footer}>
          <dl className="generation-factory__summary"><div><dt>资源类型</dt><dd>{resource.label}</dd></div><div><dt>资料范围</dt><dd>{source.mode === "course_auto" ? "自动使用课程资料" : source.mode === "none" ? "不使用资料" : `仅使用 ${source.selectedDocumentIds.length} 份文档`}</dd></div><div><dt>主题</dt><dd>{topic}</dd></div><div><dt>适用对象</dt><dd>{audience}</dd></div></dl>
          {submission.error ? <p className="generation-factory__error" role="alert">{submission.error}</p> : null}
          <GenerationTaskStatus jobId={submission.jobId} />
          {submission.job?.cancelable ? <button type="button" onClick={() => void submission.cancel()}>取消任务</button> : null}
          {submission.job?.retryable && submission.retry ? <button type="button" onClick={() => void submission.retry?.()}>按当前配置重试</button> : null}
        </GenerationConfigShell>
      )}
    </div>
  );
}
