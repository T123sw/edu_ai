import React, { useState } from 'react';
import { Collapse } from 'antd';
import type {
  AgentPlanV2,
  AgentPlanStepUpdateV2,
  AgentReflectV2,
  AgentToolCallV2,
  AgentToolResultV2,
} from '../../services/teacher/chatV2';

export interface AgentActivityState {
  plan?: AgentPlanV2;
  stepStatus: Record<number, AgentPlanStepUpdateV2['status']>;
  toolCalls: AgentToolCallV2[];
  toolResults: AgentToolResultV2[];
  reflects: AgentReflectV2[];
}

export const emptyAgentActivity = (): AgentActivityState => ({
  stepStatus: {},
  toolCalls: [],
  toolResults: [],
  reflects: [],
});

// One unified "task timeline" step combining info from this AND prior plans.
export interface MergedTimelineStep {
  index: number;
  user_title: string;
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped';
  /** 0 = current turn, 1 = previous, etc. */
  fromPriorTurn: boolean;
}

export interface MergedTimeline {
  subject: string;
  resource_type: string;
  steps: MergedTimelineStep[];
}

interface Props {
  activity: AgentActivityState;
  defaultExpanded?: boolean;
  /** If provided, render this combined timeline instead of activity.plan alone. */
  mergedTimeline?: MergedTimeline;
}

const TOOL_NAME_CN: Record<string, string> = {
  rag_search: '知识库检索',
  web_search: '联网搜索',
  draft_outline: '起草大纲',
  generate_report: '生成报告',
  generate_ppt: '生成PPT',
  generate_lesson_plan: '生成教案',
  generate_quiz: '生成练习题',
};

const STATUS_ICON: Record<string, string> = {
  pending: '○',
  running: '◐',
  done: '●',
  failed: '✗',
  skipped: '◌',
};

const STATUS_COLOR: Record<string, string> = {
  pending: '#bfbfbf',
  running: '#1677ff',
  done: '#52c41a',
  failed: '#ff4d4f',
  skipped: '#fa8c16',
};

const VERDICT_COLOR: Record<string, string> = {
  pass: '#52c41a',
  pass_with_warning: '#faad14',
  retry: '#fa8c16',
  replan: '#ff7a45',
  abort: '#ff4d4f',
};

const formatArgs = (args: Record<string, any>): string => {
  const pairs: string[] = [];
  for (const [k, v] of Object.entries(args || {})) {
    if (v === null || v === undefined || v === '' || (Array.isArray(v) && v.length === 0)) continue;
    let display: string;
    if (k === 'confirmed_outline' && typeof v === 'string') {
      display = `(${v.length}字大纲)`;
    } else if (typeof v === 'string' && v.length > 24) {
      display = `${v.slice(0, 24)}…`;
    } else {
      display = String(v);
    }
    pairs.push(`${k}=${display}`);
    if (pairs.length >= 3) break;
  }
  return pairs.join('  ');
};

// ─── Sub-components ──────────────────────────────────────────────────────────

const StepRow: React.FC<{ step: MergedTimelineStep; isLast: boolean }> = ({ step, isLast }) => {
  const icon = STATUS_ICON[step.status] || STATUS_ICON.pending;
  const color = STATUS_COLOR[step.status] || STATUS_COLOR.pending;
  const dim = step.status === 'pending';
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', position: 'relative', paddingBottom: isLast ? 0 : 10 }}>
      <div style={{ width: 18, display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <span style={{ color, fontSize: 14, lineHeight: 1, marginTop: 2 }}>{icon}</span>
        {!isLast && (
          <div style={{ width: 1, flex: 1, background: '#e8e8e8', marginTop: 2, minHeight: 10 }} />
        )}
      </div>
      <div style={{ marginLeft: 8, fontSize: 13, lineHeight: 1.5, color: dim ? '#999' : '#333', flex: 1 }}>
        {step.user_title}
        {step.fromPriorTurn && (
          <span style={{ marginLeft: 6, fontSize: 11, color: '#bfbfbf' }}>· 上一轮</span>
        )}
      </div>
    </div>
  );
};

// ─── Main component ──────────────────────────────────────────────────────────

export const AgentActivityPanel: React.FC<Props> = ({
  activity,
  defaultExpanded = true,  // default to expanded — users want to see the activity
  mergedTimeline,
}) => {
  const [expanded, setExpanded] = useState<string[]>(defaultExpanded ? ['1'] : []);
  const { plan, stepStatus, toolCalls, toolResults, reflects } = activity;

  const hasContent = plan || mergedTimeline || toolCalls.length > 0 || reflects.length > 0;
  if (!hasContent) return null;

  // Build timeline steps from either mergedTimeline or activity.plan
  const timelineSteps: MergedTimelineStep[] = (() => {
    if (mergedTimeline) return mergedTimeline.steps;
    if (plan) {
      return plan.steps.map((s) => ({
        index: s.index,
        user_title: s.user_title,
        status: (stepStatus[s.index] || s.status || 'pending') as MergedTimelineStep['status'],
        fromPriorTurn: false,
      }));
    }
    return [];
  })();

  const displaySubject = mergedTimeline?.subject || plan?.subject || '';
  const displayResourceType = mergedTimeline?.resource_type || plan?.resource_type || '';
  const doneCount = timelineSteps.filter((s) => s.status === 'done').length;
  const runningCount = timelineSteps.filter((s) => s.status === 'running').length;
  const totalSteps = timelineSteps.length;

  const headerText = totalSteps > 0
    ? `${doneCount}/${totalSteps} 步完成${runningCount > 0 ? ' · 进行中' : ''}`
    : `调用 ${toolCalls.length} 个工具`;

  return (
    <div style={{ marginBottom: 8 }}>
      <Collapse
        size="small"
        bordered={false}
        activeKey={expanded}
        onChange={(keys) => setExpanded(Array.isArray(keys) ? keys : [keys])}
        style={{ background: '#fafafa', borderRadius: 8 }}
        items={[
          {
            key: '1',
            label: (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#666' }}>
                <span style={{ fontSize: 14 }}>🤖</span>
                <span style={{ fontWeight: 500 }}>智能体执行</span>
                <span style={{ color: '#999' }}>· {headerText}</span>
                {displaySubject && (
                  <span style={{ color: '#bfbfbf' }}>· {displaySubject}</span>
                )}
              </div>
            ),
            children: (
              <div style={{ fontSize: 13, lineHeight: 1.6 }}>
                {timelineSteps.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    {displaySubject && (
                      <div style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>
                        执行计划：<span style={{ color: '#333' }}>{displaySubject}</span>
                        {displayResourceType && (
                          <span style={{
                            marginLeft: 6,
                            padding: '0 6px',
                            borderRadius: 3,
                            background: '#e6f4ff',
                            color: '#1677ff',
                            fontSize: 11,
                          }}>{displayResourceType}</span>
                        )}
                      </div>
                    )}
                    <div style={{ paddingLeft: 4 }}>
                      {timelineSteps.map((step, i) => (
                        <StepRow key={`${step.index}-${i}`} step={step} isLast={i === timelineSteps.length - 1} />
                      ))}
                    </div>
                  </div>
                )}

                {toolCalls.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>工具调用</div>
                    {toolCalls.map((call, i) => {
                      const result = toolResults[i];
                      const cn = TOOL_NAME_CN[call.tool] || call.tool;
                      return (
                        <div key={i} style={{
                          paddingLeft: 4,
                          fontSize: 12,
                          color: '#666',
                          marginBottom: 2,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          flexWrap: 'wrap',
                        }}>
                          <span style={{ color: '#333', fontWeight: 500 }}>{cn}</span>
                          <span style={{ color: '#bfbfbf', fontSize: 11 }}>{formatArgs(call.args)}</span>
                          {result && (
                            <span style={{
                              color: result.ok ? '#52c41a' : '#ff4d4f',
                              fontSize: 11,
                            }}>
                              {result.ok ? '✓' : '✗'} {result.summary?.slice(0, 30)}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {reflects.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>质量自检</div>
                    {reflects.map((r, i) => (
                      <div key={i} style={{
                        paddingLeft: 4,
                        fontSize: 12,
                        color: VERDICT_COLOR[r.verdict] || '#666',
                      }}>
                        {TOOL_NAME_CN[r.tool] || r.tool} · {r.verdict} · {r.issue?.slice(0, 50)}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ),
          },
        ]}
      />
    </div>
  );
};
