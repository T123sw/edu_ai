import type { DirectQuizConfigV2, KnowledgeBaseDirectQuizRequestV2, QuizQuestionTypeV2 } from './chatV2';

export const QUIZ_PROMPT_DRAFT =
  '请基于已选文档生成一组高质量中文习题。题目要覆盖核心概念、关键事实、因果关系与易错点，避免脱离文档自由发挥。';

export const DEFAULT_QUIZ_CONFIG: DirectQuizConfigV2 = {
  topic: '',
  hard_points: [],
  difficulty: 'medium',
  question_count: 5,
  question_types: ['choice', 'judge'],
  include_answers: true,
  include_explanations: true,
};

const QUESTION_TYPE_LABELS: Record<QuizQuestionTypeV2, string> = {
  choice: '选择题',
  blank: '填空题',
  short: '简答题',
  judge: '判断题',
};

export function buildQuizQuestionFromConfig(config: DirectQuizConfigV2): string {
  const typeLabels = (config.question_types || []).map((item) => QUESTION_TYPE_LABELS[item] || item).join('、');
  const hardPoints = (config.hard_points || []).filter(Boolean).join('、');
  return [
    `请基于已选文档生成 ${config.question_count} 道习题。`,
    config.topic ? `主题：${config.topic}。` : '',
    config.difficulty ? `难度：${config.difficulty}。` : '',
    typeLabels ? `题型：${typeLabels}。` : '',
    hardPoints ? `重点难点：${hardPoints}。` : '',
    `附答案：${config.include_answers ? '是' : '否'}。`,
    `附解析：${config.include_explanations ? '是' : '否'}。`,
  ]
    .filter(Boolean)
    .join('');
}

export function buildKnowledgeBaseQuizRequest(options: {
  courseId?: string;
  selectedDocIds: string[];
  config: DirectQuizConfigV2;
}): KnowledgeBaseDirectQuizRequestV2 {
  return {
    course_id: options.courseId,
    selected_doc_ids: options.selectedDocIds,
    quiz_config: options.config,
    prompt_draft: QUIZ_PROMPT_DRAFT,
    final_user_prompt: buildQuizQuestionFromConfig(options.config),
  };
}
