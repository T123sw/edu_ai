import React, { useState } from 'react';
import { Collapse, Tag, Tooltip } from 'antd';
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

interface Props {
  activity: AgentActivityState;
  /** Whether to start expanded (true while AI is still streaming). */
  defaultExpanded?: boolean;
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

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  pending: { text: '等待', color: 'default' },
  running: { text: '进行中', color: 'processing' },
  done: { text: '完成', color: 'success' },
  failed: { text: '失败', color: 'error' },
  skipped: { text: '跳过', color: 'warning' },
};

const VERDICT_LABEL: Record<string, { text: string; color: string }> = {
  pass: { text: '通过', color: 'success' },
  pass_with_warning: { text: '提示', color: 'warning' },
  retry: { text: '需重试', color: 'orange' },
  replan: { text: '需重新规划', color: 'volcano' },
  abort: { text: '中止', color: 'error' },
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

export const AgentActivityPanel: React.FC<Props> = ({ activity, defaultExpanded = false }) => {
  const [expanded, setExpanded] = useState<string[]>(defaultExpanded ? ['1'] : []);
  const { plan, stepStatus, toolCalls, toolResults, reflects } = activity;

  const hasContent = plan || toolCalls.length > 0 || toolResults.length > 0 || reflects.length > 0;
  if (!hasContent) return null;

  const planStepsRunning = plan?.steps.filter((s) => stepStatus[s.index] === 'running').length || 0;
  const planStepsDone = plan?.steps.filter((s) => stepStatus[s.index] === 'done').length || 0;
  const planTotal = plan?.steps.length || 0;

  const headerText = plan
    ? `智能体执行 · ${planStepsDone}/${planTotal} 步完成${planStepsRunning > 0 ? '（进行中）' : ''}`
    : `智能体执行 · 调用 ${toolCalls.length} 个工具`;

  return (
    <div style={{ marginBottom: 8 }}>
      <Collapse
        size="small"
        activeKey={expanded}
        onChange={(keys) => setExpanded(Array.isArray(keys) ? keys : [keys])}
        items={[
          {
            key: '1',
            label: (
              <span style={{ fontSize: 12, color: '#666' }}>
                <span style={{ marginRight: 6 }}>🤖</span>
                {headerText}
              </span>
            ),
            children: (
              <div style={{ fontSize: 12, lineHeight: 1.7 }}>
                {plan && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontWeight: 500, marginBottom: 4 }}>
                      执行计划：{plan.subject}
                      <Tag style={{ marginLeft: 6 }}>{plan.resource_type}</Tag>
                    </div>
                    <ol style={{ paddingLeft: 20, margin: 0 }}>
                      {plan.steps.map((step) => {
                        const status = stepStatus[step.index] || step.status || 'pending';
                        const label = STATUS_LABEL[status] || STATUS_LABEL.pending;
                        return (
                          <li key={step.index} style={{ marginBottom: 2 }}>
                            <Tag color={label.color}>{label.text}</Tag>
                            {step.user_title}
                          </li>
                        );
                      })}
                    </ol>
                  </div>
                )}

                {toolCalls.length > 0 && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontWeight: 500, marginBottom: 4 }}>工具调用：</div>
                    {toolCalls.map((call, i) => {
                      const result = toolResults[i];
                      const cn = TOOL_NAME_CN[call.tool] || call.tool;
                      return (
                        <div key={i} style={{ paddingLeft: 8, color: '#555' }}>
                          <span style={{ fontFamily: 'monospace' }}>{cn}</span>
                          <span style={{ color: '#999', marginLeft: 6 }}>{formatArgs(call.args)}</span>
                          {result && (
                            <Tag color={result.ok ? 'green' : 'red'} style={{ marginLeft: 6 }}>
                              {result.ok ? '✓' : '✗'} {result.summary?.slice(0, 30)}
                            </Tag>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {reflects.length > 0 && (
                  <div>
                    <div style={{ fontWeight: 500, marginBottom: 4 }}>质量自检：</div>
                    {reflects.map((r, i) => {
                      const v = VERDICT_LABEL[r.verdict] || { text: r.verdict, color: 'default' };
                      return (
                        <div key={i} style={{ paddingLeft: 8 }}>
                          <Tag color={v.color}>{v.text}</Tag>
                          <Tooltip title={r.issue}>
                            <span style={{ color: '#555' }}>
                              {(TOOL_NAME_CN[r.tool] || r.tool)} · {r.issue?.slice(0, 40)}
                            </span>
                          </Tooltip>
                        </div>
                      );
                    })}
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
