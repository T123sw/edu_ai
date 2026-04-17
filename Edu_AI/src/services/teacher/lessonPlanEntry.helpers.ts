import type { ChatReplyRequestV2, LessonPlanEntryCard } from './chatV2';

export interface LessonPlanEntryConfigInput {
  topic: string;
  audience?: string;
  duration?: string;
  lessonType?: string;
  objective?: string;
  keyPoints?: string[] | string;
  difficultPoints?: string[] | string;
  afterClassTask?: string;
  styleHint?: string;
  extraRequirements?: string;
}

export function getDefaultLessonPlanPresetCards(): LessonPlanEntryCard[] {
  return [
    {
      card_id: 'preset-new-lesson',
      card_type: 'preset',
      title: '新授课教案',
      description: '适合围绕核心概念、关键材料和基础问题链展开单课时教学。',
      prompt_draft: '请基于已选文档生成一份贴近真实课堂的新授课教案，先输出可确认的大纲，再生成完整正文。',
      preset_key: 'new_lesson',
      prefill_config: {
        topic: '',
        audience: '',
        duration: '45分钟',
        lesson_type: '新授课',
        objective: '',
        style_hint: '突出问题链、材料使用和课堂产出',
      },
    },
    {
      card_id: 'preset-review-lesson',
      card_type: 'preset',
      title: '复习课教案',
      description: '适合围绕知识梳理、易错点辨析和当堂检测组织教学。',
      prompt_draft: '请基于已选文档生成一份复习课教案，突出知识结构、易错点和练习反馈。',
      preset_key: 'review_lesson',
      prefill_config: {
        topic: '',
        audience: '',
        duration: '45分钟',
        lesson_type: '复习课',
        objective: '',
        style_hint: '强化归纳整理、错因分析和当堂检测',
      },
    },
    {
      card_id: 'preset-practice-lesson',
      card_type: 'preset',
      title: '练习讲评教案',
      description: '适合围绕典型题、常见错误和方法迁移组织教学。',
      prompt_draft: '请基于已选文档生成一份练习讲评教案，突出典型问题、错因分析和巩固训练。',
      preset_key: 'practice_lesson',
      prefill_config: {
        topic: '',
        audience: '',
        duration: '45分钟',
        lesson_type: '讲评课',
        objective: '',
        style_hint: '突出错因辨析、示范讲解和分层练习',
      },
    },
  ];
}

export function groupLessonPlanEntryCards(cards: LessonPlanEntryCard[]): {
  presets: LessonPlanEntryCard[];
  recommended: LessonPlanEntryCard[];
} {
  return {
    presets: cards.filter((card) => card.card_type === 'preset'),
    recommended: cards.filter((card) => card.card_type === 'recommended'),
  };
}

function clean(value: unknown): string {
  return String(value || '').trim();
}

function cleanList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => clean(item)).filter(Boolean);
  }
  return clean(value)
    .split(/[,，;；、\n]+/)
    .map((item) => clean(item))
    .filter(Boolean);
}

export function buildLessonPlanEntryQuestion(options: {
  card: LessonPlanEntryCard;
  config: LessonPlanEntryConfigInput;
}): string {
  const { card, config } = options;
  const topic = clean(config.topic || card.prefill_config?.topic) || '当前主题';
  const audience = clean(config.audience || card.prefill_config?.audience);
  const duration = clean(config.duration || card.prefill_config?.duration) || '45分钟';
  const lessonType = clean(config.lessonType || card.prefill_config?.lesson_type) || '单课时教案';
  const objective = clean(config.objective || card.prefill_config?.objective);
  const keyPoints = cleanList(config.keyPoints || card.prefill_config?.key_points);
  const difficultPoints = cleanList(config.difficultPoints || card.prefill_config?.difficult_points);
  const afterClassTask = clean(config.afterClassTask || card.prefill_config?.after_class_task);
  const styleHint = clean(config.styleHint || card.prefill_config?.style_hint);
  const extraRequirements = clean(config.extraRequirements);

  const parts: string[] = [
    clean(card.prompt_draft) || '请基于已选文档生成一份教案。',
    `课题：${topic}。`,
    audience ? `适用对象：${audience}。` : '',
    duration ? `课时长度：${duration}。` : '',
    lessonType ? `课型：${lessonType}。` : '',
    objective ? `本课目标：${objective}。` : '',
    keyPoints.length ? `教学重点：${keyPoints.join('；')}。` : '',
    difficultPoints.length ? `教学难点：${difficultPoints.join('；')}。` : '',
    afterClassTask ? `课后任务：${afterClassTask}。` : '',
    styleHint ? `风格要求：${styleHint}。` : '',
    extraRequirements ? `补充要求：${extraRequirements}。` : '',
    '仅以我当前勾选的文档为依据，不承接历史对话上下文，不使用历史会话内容。',
    '请先输出可供确认的教案大纲，确认后再生成完整正文。',
  ];

  return parts.filter(Boolean).join('');
}

export function buildKnowledgeBaseLessonPlanReplyRequest(options: {
  card: LessonPlanEntryCard;
  config: LessonPlanEntryConfigInput;
  courseId?: string;
  selectedDocIds: string[];
}): ChatReplyRequestV2 {
  return {
    question: buildLessonPlanEntryQuestion({
      card: options.card,
      config: options.config,
    }),
    conversation_id: undefined,
    course_id: options.courseId,
    selected_doc_ids: options.selectedDocIds,
    action_hint: 'generate.lesson_plan',
    allow_rag: false,
    allow_web: false,
  };
}
