import type { LearningJob } from './TaskCenter';
import type { JobRecord } from '../jobs/types';

export type PreparationTask = {
  preparation_id: string;
  status: string;
  stage: string;
  revision: number;
  attempt_no?: number;
  created_at?: string;
  error_code?: string | null;
  failure?: PreparationFailure | null;
  result_ref?: { course_ready: boolean; course_available?: boolean; path_available?: boolean; available_resources?: number; planned_resources?: number; course_id?: string; manifest_version?: number } | null;
};

export type PreparationFailure = {
  title: string; reason: string; next_step: string; stage: string;
  saved_resources: number; planned_resources: number;
  resource_issues: { resource_title: string; resource_type: string; step: string; reason: string }[];
};

export const preparationSteps = [
  { title: '理解需求', icon: 'book', stages: ['normalize', 'ingest'] },
  { title: '研究与规划', icon: 'search', stages: ['research_scope', 'plan', 'research_nodes'] },
  { title: '制作内容', icon: 'slides', stages: ['produce'] },
  { title: '检查与完善', icon: 'quiz', stages: ['review', 'repair'] },
  { title: '交付课程', icon: 'check', stages: ['commit'] },
];

const stageCopy: Record<string, [string, string]> = {
  normalize: ['理解你的学习目标', '梳理学习目标、已有基础与课程范围。'],
  ingest: ['正在阅读你的资料', '整理上传内容，提取与学习目标相关的知识。'],
  research_scope: ['查找与核验学习资料', '研究主题，核验来源，为课程建立可靠依据。'],
  plan: ['规划你的学习路径', '把目标拆成循序渐进的知识点，安排学习内容。'],
  research_nodes: ['完善知识点的资料', '补充各个知识点的依据与案例，检查内容覆盖。'],
  produce: ['正在制作学习内容', '为知识点生成讲解、练习和所需课堂内容。'],
  review: ['检查课程质量', '核对知识点覆盖、资料质量与课程完整性。'],
  repair: ['完善课程中的细节', '根据检查结果补充或修订内容，完成后再次检查。'],
  commit: ['整理并保存你的课程', '保存课程与学习入口，即将可以开始学习。'],
};

export function isPreparationActive(task: PreparationTask) {
  return !['succeeded', 'failed', 'canceled', 'cancelled'].includes(task.status);
}

export function preparationCopy(task?: PreparationTask) {
  if (!task) return ['正在提交学习目标', '任务接收后，这里会显示课程准备的实时阶段。'];
  if (task.result_ref?.course_available && !task.result_ref.course_ready) return [
    isPreparationActive(task) ? '已有资料可以开始学习' : '部分内容已完成，可以先学习',
    `已交付 ${task.result_ref.available_resources || 0} / ${task.result_ref.planned_resources || 0} 份资料。${isPreparationActive(task) ? '其他内容仍在准备中。' : '未完成的内容可单独重试，已有资料会保留。'}`,
  ];
  if (task.result_ref?.path_available && isPreparationActive(task)) return [
    '学习路径已就绪', '可以先查看课程目录。知识点资源完成后会自动开放，其余内容继续在后台生成。',
  ];
  if (task.status === 'failed') return ['课程暂未准备完成', '请查看下面的失败原因和处理建议。'];
  if (['canceled', 'cancelled'].includes(task.status)) return ['课程准备已取消', '本次任务已停止，你可以关闭窗口并重新安排学习。'];
  if (task.status === 'succeeded') return task.result_ref?.course_ready
    ? ['你的课程已准备好', '学习内容已保存，可以进入课堂开始学习。']
    : ['本次准备已完成', '当前结果尚未形成可进入的完整课程。'];
  if (['accepted', 'queued'].includes(task.status)) return ['任务已接收，等待开始', '课程准备会自动进行，你可以先继续浏览。'];
  return stageCopy[task.stage] || ['正在准备课程', '任务正在后台运行，下一阶段就绪后会自动更新。'];
}

export function preparationStepIndex(task?: PreparationTask) {
  if (!task || ['accepted', 'queued'].includes(task.status)) return -1;
  if (task.status === 'succeeded') return task.result_ref?.course_ready ? preparationSteps.length : -1;
  return preparationSteps.findIndex(step => step.stages.includes(task.stage));
}

export function mergePreparationTasks(previous: PreparationTask[], incoming: PreparationTask[]) {
  const byId = new Map(previous.map(task => [task.preparation_id, task]));
  for (const task of incoming) {
    const old = byId.get(task.preparation_id);
    if (!old || task.revision >= old.revision) byId.set(task.preparation_id, task);
  }
  return [...byId.values()];
}

export function preparationJob(task: PreparationTask): LearningJob {
  return {
    edu_job_id: task.preparation_id,
    preparation_id: task.preparation_id,
    preparation: task,
    created_at: task.created_at,
    status: task.status === 'failed' && task.result_ref?.course_available ? 'partially_succeeded'
      : ['accepted', 'queued'].includes(task.status) ? 'queued' : task.status === 'checking' ? 'running' : task.status,
    kind: 'course_preparation',
    message: preparationCopy(task)[0],
    course_id: task.result_ref?.course_ready || task.result_ref?.course_available ? task.result_ref.course_id : undefined,
    error_message: task.status === 'failed' ? preparationFailure(task).reason : undefined,
  };
}

export function preparationGlobalJob(task: PreparationTask, owner: string): JobRecord {
  const job = preparationJob(task);
  return {
    ...job, preparation: task, schema_version: 2, version: task.revision,
    kind: 'course_preparation', status: job.status as JobRecord['status'], step: task.stage,
    progress: 0, message: job.message || '', owner_user_id: owner, scope_type: 'personal',
    input_summary: { title: '课程准备' }, result_ref: task.result_ref,
    retryable: false, cancelable: false, created_at: task.created_at || '', updated_at: '',
  };
}

export function preparationError(code?: string | null) {
  return preparationFailure({ error_code: code }).reason;
}

export function preparationFailure(task?: Pick<PreparationTask, 'failure' | 'error_code'> & { stage?: string }): PreparationFailure {
  if (task?.failure) return task.failure;
  const code = (task?.error_code || '').split(':')[0];
  let title = '课程准备遇到问题';
  let reason = '本次课程准备中断，目前没有足够信息确认更具体的原因。';
  let next_step = '请稍后重试；如果再次失败，请联系维护人员查看这条任务。';
  if (['CONTEXT_BUDGET_EXCEEDED', 'RESEARCH_CONTEXT_BUDGET'].includes(code)) {
    title = '一次处理的内容过多';
    reason = '系统在这一步一次装入的资料或页面内容过多，超过了当前单次处理上限。';
    next_step = '直接重试可能再次遇到同样问题。可以先缩小课程范围重新创建，或联系维护人员调整生成方式。';
  } else if (code === 'DEADLINE_EXCEEDED') {
    title = '本次准备时间已用完';
    reason = '课程还没有全部准备好，但本次执行已达到系统设置的时间上限。';
    next_step = '可以点击“继续重试”，从已保存的进度继续；若仍反复超时，可减少本次知识点数量。';
  } else if (code === 'BUDGET_EXHAUSTED') {
    title = '本次生成额度不足';
    reason = '本次制作已达到系统设置的生成额度或执行限制，剩余内容没有完成。';
    next_step = '重试不会清零已经使用的生成额度。可以减少本次课程范围重新创建，或联系维护人员调整任务额度。';
  } else if (['RESOURCE_CONTENT_REJECTED', 'QUALITY_GATE_FAILED', 'COURSE_CONTRACT_INVALID'].includes(code)) {
    title = '部分学习内容仍需修正';
    reason = '系统检查发现部分内容不够完整或前后不一致，尚未形成可交付的课程。';
  } else if (['PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE', 'HARNESS_UNAVAILABLE', 'MODEL_UNAVAILABLE'].includes(code)) {
    title = '生成服务暂时没有完成响应';
    reason = '生成服务响应超时或暂时不可用，本次课程准备已停止。';
    next_step = '请稍后点击“继续重试”。已经保存的进度会保留。';
  } else if (['COURSE_REVIEW_UNKNOWN_RESOURCE', 'COURSE_REVIEW_INCOMPLETE', 'COURSE_REVIEW_INVALID', 'MODEL_RESPONSE_INVALID', 'CLASSROOM_BINDINGS_INVALID'].includes(code)) {
    title = '生成结果暂时无法继续处理';
    reason = '生成服务返回的结果不完整或与当前资料不匹配，系统无法继续完成课程。';
  } else if (['SOURCE_OR_OWNER_UNAVAILABLE', 'RESOURCE_PERMISSION_DENIED'].includes(code)) {
    title = '参考资料暂时无法访问';
    reason = '本次课程需要的资料已不可用，或当前账号没有访问权限。';
    next_step = '请确认资料仍然存在且可以打开，再重试或重新上传资料。';
  } else if (['NO_PROGRESS', 'AGENT_NO_PROGRESS'].includes(code)) {
    title = '多次尝试后仍未完成';
    reason = '系统多次尝试整理或补充内容，但没有取得足够进展，因此停止了本次准备。';
    next_step = '可以重试，或把学习目标写得更具体、缩小本次范围后重新创建。';
  }
  return { title, reason, next_step, stage: task?.stage ? stageCopy[task.stage]?.[0] || '准备课程' : '准备课程',
    saved_resources: 0, planned_resources: 0, resource_issues: [] };
}
