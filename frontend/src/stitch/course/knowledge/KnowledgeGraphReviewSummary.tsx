import type { GraphDraftStats, GraphReviewFilter, GraphReviewIssue } from "./courseKnowledgeGraphDraft";

type Props = {
  stats: GraphDraftStats;
  newCount: number;
  issues: GraphReviewIssue[];
  activeFilter: GraphReviewFilter;
  dirty: boolean;
  onFilterChange: (filter: GraphReviewFilter) => void;
  onSelectIssue: (nodeId: string) => void;
};

const FILTERS: Array<{ value: GraphReviewFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "new", label: "本次新增" },
  { value: "issues", label: "待完善" },
  { value: "mapped", label: "已映射教材" },
];

export function KnowledgeGraphReviewSummary({
  stats,
  newCount,
  issues,
  activeFilter,
  dirty,
  onFilterChange,
  onSelectIssue,
}: Props) {
  const metrics = [
    ["全部节点", stats.nodeCount],
    ["模块", stats.moduleCount],
    ["知识点", stats.leafCount],
    ["教材映射", stats.mappedOutlineCount],
    ["本次新增", newCount],
    ["待完善", issues.length],
  ] as const;

  return (
    <section className="course-kb-graph__summary" aria-label="图谱审核概览">
      <div className="course-kb-graph__stats">
        {metrics.map(([label, value]) => (
          <span key={label}><small>{label}</small><strong>{value}</strong></span>
        ))}
      </div>
      <div className="course-kb-graph__summary-row">
        <div className="course-kb-graph__filters" aria-label="图谱筛选">
          {FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              aria-pressed={activeFilter === filter.value}
              onClick={() => onFilterChange(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <span className={`course-kb-graph__save-status${dirty ? " is-dirty" : ""}`} aria-live="polite">
          {dirty ? "有未保存修改" : "已保存"}
        </span>
      </div>
      {issues.length ? (
        <div className="course-kb-graph__issues" role="status">
          <strong>需要处理的问题</strong>
          <div>
            {issues.map((issue) => (
              <button key={`${issue.code}:${issue.nodeId}`} type="button" onClick={() => onSelectIssue(issue.nodeId)}>
                {issue.message}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="course-kb-graph__issues is-clear" role="status">未发现待处理问题</div>
      )}
    </section>
  );
}
