import assert from 'node:assert/strict';

import {
  buildKnowledgeBaseLessonPlanReplyRequest,
  buildLessonPlanEntryQuestion,
  getDefaultLessonPlanPresetCards,
} from '../../src/services/teacher/lessonPlanEntry.helpers.ts';

const presetCards = getDefaultLessonPlanPresetCards();
assert.ok(presetCards.length >= 3, 'lesson plan presets should include multiple teaching scenarios');
assert.equal(presetCards[0].card_type, 'preset');

const selectedCard = {
  card_id: 'preset-new-lesson',
  card_type: 'preset' as const,
  title: '新授课教案',
  description: '面向单课时新授课。',
  prompt_draft: '请基于已选文档生成一份新授课教案。',
  preset_key: 'new_lesson' as const,
  prefill_config: {
    topic: '关羽的战绩与历史评价',
    audience: '初中历史',
    duration: '45分钟',
    lesson_type: '新授课',
    objective: '梳理关羽主要战绩并进行历史评价',
  },
};

const question = buildLessonPlanEntryQuestion({
  card: selectedCard,
  config: {
    topic: '关羽的战绩与历史评价',
    audience: '初中历史',
    duration: '45分钟',
    lessonType: '新授课',
    objective: '梳理关羽主要战绩并进行历史评价',
    extraRequirements: '先给出可确认的大纲，再生成完整正文。',
  },
});

assert.match(question, /关羽的战绩与历史评价/);
assert.match(question, /初中历史/);
assert.match(question, /45分钟/);
assert.match(question, /先给出可确认的大纲/);
assert.match(question, /仅以我当前勾选的文档为依据/);

const request = buildKnowledgeBaseLessonPlanReplyRequest({
  card: selectedCard,
  config: {
    topic: '关羽的战绩与历史评价',
    audience: '初中历史',
    duration: '45分钟',
    lessonType: '新授课',
    objective: '梳理关羽主要战绩并进行历史评价',
    extraRequirements: '贴近真实课堂。',
  },
  courseId: 'course-1',
  selectedDocIds: ['doc-1', 'doc-2'],
});

assert.equal(request.action_hint, 'generate.lesson_plan');
assert.equal(request.course_id, 'course-1');
assert.deepEqual(request.selected_doc_ids, ['doc-1', 'doc-2']);
assert.equal(request.conversation_id, undefined);
assert.match(String(request.question), /贴近真实课堂/);

console.log('lessonPlanEntry.helpers tests passed');
