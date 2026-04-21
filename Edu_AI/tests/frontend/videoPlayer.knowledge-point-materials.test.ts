import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const api = readFileSync(new URL('../../src/stitch/api/courses.ts', import.meta.url), 'utf8');
const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');

assert.match(
  api,
  /type\s+CourseMaterialsScopeOptions/,
  'stitch course materials API should expose scope query options',
);

assert.match(
  api,
  /params\.set\("scope_type",\s*options\.scopeType\)/,
  'stitch course materials API should send scope_type to the backend',
);

assert.match(
  api,
  /params\.set\("scope_id",\s*options\.scopeId\)/,
  'stitch course materials API should send scope_id to the backend',
);

assert.match(
  page,
  /selectedMaterialScope/,
  'course learning page should derive a selected material scope from the clicked knowledge point',
);

assert.match(
  page,
  /getCourseMaterials\(course\.id,\s*selectedMaterialScope\)/,
  'course learning page should reload generated materials with the selected knowledge-point scope',
);

assert.match(
  page,
  /scopeType:\s*"knowledge_point"/,
  'course learning page should use knowledge_point scope for non-root graph nodes',
);

console.log('videoPlayer.knowledge-point-materials tests passed');
