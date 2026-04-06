import assert from 'node:assert/strict';

import {
  formatArtifactVersionText,
  normalizeGeneratedFileId,
  upsertGeneratedFileInList,
  pinGeneratedFileInList,
  sortCourseMaterials,
  toGeneratedFileFromCourseMaterial,
} from '../../src/services/teacher/materials.helpers.ts';

const materials = sortCourseMaterials([
  {
    id: 'report-1',
    name: '普通报告',
    type: 'report',
    addedAt: '2026-04-06T10:00:00',
  },
  {
    id: 'report-2',
    name: '置顶报告',
    type: 'report',
    addedAt: '2026-04-06T09:00:00',
    isPinned: true,
    pinnedAt: '2026-04-06T11:00:00',
  },
] as any);

assert.deepEqual(materials.map((item) => item.id), ['report-2', 'report-1']);

const pinnedFiles = pinGeneratedFileInList(
  [
    { id: 'report-1', name: '普通报告', type: 'report', meta: {} },
    { id: 'report-2', name: '置顶报告', type: 'report', meta: {} },
  ] as any,
  'report-2',
  true,
  '2026-04-06T11:00:00',
);

assert.equal(pinnedFiles[0].id, 'report-2');
assert.equal(pinnedFiles[0].meta?.isPinned, true);
assert.equal(pinnedFiles[0].meta?.pinnedAt, '2026-04-06T11:00:00');

assert.equal(normalizeGeneratedFileId('conv-887d71fab7b1:content'), 'conv-887d71fab7b1__content');

const generatedFromMaterial = toGeneratedFileFromCourseMaterial({
  id: 'conv-887d71fab7b1__content',
  name: '高一物理课堂观察报告.md',
  type: 'report',
  content: '# 高一物理课堂观察报告\n\n正文',
  addedAt: '2026-04-06T18:05:40.447755',
  courseId: 'course-1',
  isPinned: true,
  pinnedAt: '2026-04-06T18:06:00.000000',
} as any);

assert.equal(generatedFromMaterial?.id, 'conv-887d71fab7b1__content');
assert.equal(generatedFromMaterial?.meta?.courseId, 'course-1');
assert.equal(generatedFromMaterial?.meta?.isPinned, true);

const sortedGeneratedFiles = upsertGeneratedFileInList(
  [
    {
      id: 'report-old',
      name: '旧报告.md',
      type: 'report',
      meta: {
        addedAt: '2026-04-06T10:00:00',
      },
    },
  ] as any,
  {
    id: 'report-new',
    name: '新报告.md',
    type: 'report',
    meta: {
      addedAt: '2026-04-06T12:00:00',
    },
  } as any,
);

assert.deepEqual(sortedGeneratedFiles.map((item) => item.id), ['report-new', 'report-old']);

assert.equal(
  formatArtifactVersionText({
    versionId: 'v2',
    versionNumber: 2,
  }),
  'v2（基于 v1 修改）',
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
  'v3（基于 v2 修改）',
);

console.log('materials.helpers tests passed');
