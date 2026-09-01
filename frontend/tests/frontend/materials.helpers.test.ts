import assert from 'node:assert/strict';

import {
  clearConversationGeneratedFiles,
  formatArtifactVersionText,
  isArtifactReferenceEligible,
  normalizeGeneratedFileId,
  pinGeneratedFileInList,
  replaceCourseMaterialGeneratedFiles,
  replaceConversationGeneratedFiles,
  sortCourseMaterials,
  toGeneratedFileFromCourseMaterial,
  upsertGeneratedFileInList,
} from '../../src/services/teacher/materials.helpers.ts';

const materials = sortCourseMaterials([
  {
    id: 'report-1',
    name: 'regular-report',
    type: 'report',
    addedAt: '2026-04-06T10:00:00',
  },
  {
    id: 'report-2',
    name: 'pinned-report',
    type: 'report',
    addedAt: '2026-04-06T09:00:00',
    isPinned: true,
    pinnedAt: '2026-04-06T11:00:00',
  },
] as any);

assert.deepEqual(materials.map((item) => item.id), ['report-2', 'report-1']);

const pinnedFiles = pinGeneratedFileInList(
  [
    {
      id: 'report-1',
      name: 'newer-report',
      type: 'report',
      meta: {
        addedAt: '2026-04-06T12:00:00',
      },
    },
    {
      id: 'report-2',
      name: 'older-report',
      type: 'report',
      meta: {
        addedAt: '2026-04-06T09:00:00',
      },
    },
  ] as any,
  'report-2',
  true,
  '2026-04-06T13:00:00',
);

assert.deepEqual(pinnedFiles.map((item) => item.id), ['report-2', 'report-1']);
assert.equal(pinnedFiles[0].meta?.isPinned, true);
assert.equal(pinnedFiles[0].meta?.pinnedAt, '2026-04-06T13:00:00');

assert.equal(normalizeGeneratedFileId('conv-887d71fab7b1:content'), 'conv-887d71fab7b1__content');

const generatedFromMaterial = toGeneratedFileFromCourseMaterial({
  id: 'conv-887d71fab7b1__content',
  name: 'physics-observation-report.md',
  type: 'report',
  content: '# report\n\nbody',
  addedAt: '2026-04-06T18:05:40.447755',
  courseId: 'course-1',
  scopeType: 'course',
  scopeId: undefined,
  isPinned: true,
  pinnedAt: '2026-04-06T18:06:00.000000',
} as any);

assert.equal(generatedFromMaterial?.id, 'conv-887d71fab7b1__content');
assert.equal(generatedFromMaterial?.meta?.courseId, 'course-1');
assert.equal(generatedFromMaterial?.meta?.scopeType, 'course');
assert.equal(generatedFromMaterial?.meta?.scopeId, undefined);
assert.equal(generatedFromMaterial?.meta?.isPinned, true);
assert.equal(generatedFromMaterial?.meta?.origin, 'course_material');

const generatedFromKnowledgePointMaterial = toGeneratedFileFromCourseMaterial({
  id: 'kp-report-1',
  name: 'kp-report.md',
  type: 'report',
  content: '# kp report',
  courseId: 'course-1',
  scopeType: 'knowledge_point',
  scopeId: 'kp-001',
} as any);

assert.equal(generatedFromKnowledgePointMaterial?.meta?.scopeType, 'knowledge_point');
assert.equal(generatedFromKnowledgePointMaterial?.meta?.scopeId, 'kp-001');

assert.equal(isArtifactReferenceEligible({ id: 'report-1', type: 'report', meta: { kind: 'final_report' } } as any), true);
assert.equal(isArtifactReferenceEligible({ id: 'outline-1', type: 'report', meta: { kind: 'outline' } } as any), true);
assert.equal(isArtifactReferenceEligible({ id: 'quiz-1', type: 'quiz', meta: {} } as any), false);

const replacedConversationFiles = replaceConversationGeneratedFiles(
  [
    { id: 'course-report', name: 'course-report', type: 'report', meta: { origin: 'course_material' } },
    { id: 'conv-old', name: 'old-conversation-report', type: 'report', meta: { origin: 'conversation', conversationId: 'conv-old' } },
  ] as any,
  [
    { id: 'conv-new', name: 'new-conversation-report', type: 'report', meta: { origin: 'conversation', conversationId: 'conv-new' } },
  ] as any,
);

assert.deepEqual(replacedConversationFiles.map((item) => item.id), ['conv-new', 'course-report']);

const clearedConversationFiles = clearConversationGeneratedFiles(
  [
    { id: 'course-report', name: 'course-report', type: 'report', meta: { origin: 'course_material' } },
    { id: 'conv-new', name: 'new-conversation-report', type: 'report', meta: { origin: 'conversation', conversationId: 'conv-new' } },
  ] as any,
);

assert.deepEqual(clearedConversationFiles.map((item) => item.id), ['course-report']);

const replacedCourseMaterialFiles = replaceCourseMaterialGeneratedFiles(
  [
    { id: 'course-old', name: 'old-course-report', type: 'report', meta: { origin: 'course_material', addedAt: '2026-04-05T10:00:00' } },
    { id: 'conv-new', name: 'conversation-report', type: 'report', meta: { origin: 'conversation', conversationId: 'conv-new', addedAt: '2026-04-06T12:00:00' } },
  ] as any,
  [
    { id: 'course-fresh', name: 'fresh-course-report', type: 'report', meta: { origin: 'course_material', addedAt: '2026-04-06T13:00:00' } },
  ] as any,
);

assert.deepEqual(replacedCourseMaterialFiles.map((item) => item.id), ['course-fresh', 'conv-new']);

const sortedGeneratedFiles = upsertGeneratedFileInList(
  [
    {
      id: 'report-old',
      name: 'old-report.md',
      type: 'report',
      meta: {
        addedAt: '2026-04-06T10:00:00',
      },
    },
  ] as any,
  {
    id: 'report-new',
    name: 'new-report.md',
    type: 'report',
    meta: {
      addedAt: '2026-04-06T12:00:00',
    },
  } as any,
);

assert.deepEqual(sortedGeneratedFiles.map((item) => item.id), ['report-new', 'report-old']);

const generatedFilesStillSortByAddedAt = upsertGeneratedFileInList(
  [
    {
      id: 'report-pinned-old',
      name: 'old-pinned-report.md',
      type: 'report',
      meta: {
        isPinned: true,
        pinnedAt: '2026-04-06T13:00:00',
        addedAt: '2026-04-06T08:00:00',
      },
    },
  ] as any,
  {
    id: 'report-newest',
      name: 'newest-report.md',
      type: 'report',
      meta: {
        addedAt: '2026-04-06T14:00:00',
      },
  } as any,
);

assert.deepEqual(generatedFilesStillSortByAddedAt.map((item) => item.id), ['report-newest', 'report-pinned-old']);

assert.equal(
  formatArtifactVersionText({
    versionId: 'v2',
    versionNumber: 2,
  }),
  'v2（基于v1 修改）',
);

assert.equal(
  formatArtifactVersionText({
    versionId: 'v1',
    versionNumber: 1,
  }),
  'v1',
);

assert.equal(
  formatArtifactVersionText({
    versionNumber: 3,
  }),
  'v3（基于v2 修改）',
);

console.log('materials.helpers tests passed');
