import assert from 'node:assert/strict';

import {
  getAiStudioCourseLabel,
  getAiStudioKnowledgePointLabel,
} from '../../src/pages/teacher/aiStudioContext.ts';

assert.equal(
  getAiStudioCourseLabel({ title: '操作系统' } as any, 'course-1'),
  '操作系统',
);

assert.equal(
  getAiStudioCourseLabel(null, 'course-1'),
  'course-1',
);

assert.equal(
  getAiStudioCourseLabel(null, ''),
  '未指定课程',
);

assert.equal(
  getAiStudioKnowledgePointLabel({ topics: ['进程调度', '线程'] } as any),
  '进程调度',
);

assert.equal(
  getAiStudioKnowledgePointLabel({ topics: ['   ', '线程'] } as any),
  '线程',
);

assert.equal(
  getAiStudioKnowledgePointLabel(null),
  '未指定知识点',
);

console.log('aiStudioContext tests passed');
