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

// Only running steps describe current work; pending steps stay internal.
export const getAgentStepStatusText = (
  activity: AgentActivityState,
  update: AgentPlanStepUpdateV2,
): string | undefined => {
  if (update.status !== 'running') return undefined;
  const title = (update.user_title || activity.plan?.steps.find(
    (step) => step.index === update.step_index,
  )?.user_title || '').trim();
  if (!title) return '正在处理...';
  return `${title.startsWith('正在') ? title : `正在${title}`}${/[。.!！…]$/.test(title) ? '' : '...'}`;
};

const TOOL_STATUS_TEXT: Record<string, string> = {
  rag_search: '正在检索知识库...',
  web_search: '正在联网搜索...',
  draft_outline: '正在起草大纲...',
  generate_report: '正在生成报告...',
  generate_lesson_plan: '正在生成教案...',
  generate_quiz: '正在生成练习题...',
  generate_classroom: '正在生成 AI 课堂...',
  generate_mindmap: '正在生成思维导图...',
  generate_podcast: '正在生成教学播客...',
};

export const getAgentToolStatusText = (tool: string): string => (
  TOOL_STATUS_TEXT[tool] || '正在处理请求...'
);
