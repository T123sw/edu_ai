import type { ReactNode } from "react";
import type { CourseKnowledgeIntent } from "../../api/types";

const artifactNames: Record<string, string> = {
  concept_explanation: "概念讲解",
  worked_case: "完整案例",
  exercise_with_solution: "带答案和解析的练习",
  lab: "实验",
  comparison: "对比分析",
  glossary: "术语表",
};

const bloomNames: Record<string, string> = {
  understand: "理解",
  apply: "应用",
  analyze: "分析",
};

function Value({ label, children }: { label: string; children: ReactNode }) {
  if (!children) return null;
  return <div><dt>{label}</dt><dd>{children}</dd></div>;
}

export function CourseKnowledgeIntentReview({ intent }: { intent: CourseKnowledgeIntent }) {
  const sourceDomains = intent.source_policy.required_domains.length
    ? intent.source_policy.required_domains
    : intent.source_policy.preferred_domains;
  const sourceLabel = intent.source_policy.required_domains.length ? "限定来源" : "优先来源";
  const duration = intent.course_profile.duration_lessons
    ? `${intent.course_profile.duration_lessons} 课时`
    : intent.course_profile.duration_minutes
      ? `${intent.course_profile.duration_minutes} 分钟`
      : "";
  return <section className="course-kb-intent" aria-labelledby="course-kb-intent-title">
    <div className="course-kb-intent__heading">
      <div><h4 id="course-kb-intent-title">请确认 Agent 对需求的理解</h4><p>下列内容会直接控制检索、内容生成和发布验收；如有偏差，请返回修改需求。</p></div>
      <span>待教师确认</span>
    </div>
    <dl className="course-kb-intent__grid">
      <Value label="教学对象">{intent.course_profile.audience}</Value>
      <Value label="课程时长">{duration}</Value>
      <Value label="内容范围">{intent.scope.include_topics.join("、")}</Value>
      <Value label="教学深度">{[
        intent.depth_profile.conceptual_rigor,
        ...intent.depth_profile.target_bloom_levels.map(level => bloomNames[level] || level),
        intent.depth_profile.example_complexity,
      ].filter(Boolean).join(" · ")}</Value>
      <Value label={sourceLabel}>{sourceDomains.join("、")}</Value>
      <Value label="交付物">{intent.deliverables.map(item => `${item.count} 个${artifactNames[item.type] || item.type}`).join("、")}</Value>
      <Value label="增量保护">{[
        intent.scope.preserve_existing_graph ? "保留现有目录" : "",
        intent.scope.preserve_existing_documents ? "保留已有资料" : "",
      ].filter(Boolean).join("、")}</Value>
      <Value label="资料降级">{[
        intent.source_policy.allow_community_fallback ? "允许社区来源" : "不允许社区来源",
        intent.source_policy.allow_ai_fallback ? "允许 AI 补充" : "不允许 AI 补充",
      ].join("、")}</Value>
    </dl>
    {intent.assumptions.length > 0 && <div className="course-kb-intent__notice"><strong>待注意的假设</strong>{intent.assumptions.join("；")}</div>}
  </section>;
}
