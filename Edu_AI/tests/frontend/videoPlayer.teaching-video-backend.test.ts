import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');
const coursesApi = readFileSync(new URL('../../src/stitch/api/courses.ts', import.meta.url), 'utf8');
const types = readFileSync(new URL('../../src/stitch/api/types.ts', import.meta.url), 'utf8');

assert.match(types, /export type TeachingVideoPptItem/, 'stitch API types should include teaching-video PPT items');
assert.match(types, /export type TeachingVideoTaskResponse/, 'stitch API types should include teaching-video task status');
assert.match(coursesApi, /getTeachingVideoPpts\(courseId: string\)/, 'stitch courses API should list PPTs available for teaching video generation');
assert.match(coursesApi, /\/teaching-videos\/ppts/, 'stitch courses API should call the backend PPT listing endpoint');
assert.match(coursesApi, /createTeachingVideoTask\(courseId: string,\s*payload: \{ ppt_material_id: string \}\)/, 'stitch courses API should create teaching-video tasks through the course backend');
assert.match(coursesApi, /\/teaching-videos`/, 'stitch courses API should call the backend task creation endpoint');
assert.match(coursesApi, /getTeachingVideoTaskStatus\(courseId: string,\s*taskId: string\)/, 'stitch courses API should expose backend task polling');
assert.match(page, /getTeachingVideoPpts/, 'VideoPlayer should load backend-ready PPT candidates');
assert.match(page, /createTeachingVideoTask\(course\.id,\s*\{\s*ppt_material_id: selectedOfflinePptId\s*\}\)/, 'VideoPlayer should submit offline generation through the course backend bridge');
assert.match(page, /getTeachingVideoTaskStatus\(course\.id,\s*offlineTaskId\)/, 'VideoPlayer should poll offline task status through the course backend bridge');
assert.doesNotMatch(page, /offlineImageRoot/, 'VideoPlayer should not ask users for local slide image directories');
assert.doesNotMatch(page, /generateAiLecturerFullVideo/, 'VideoPlayer should not call the AI Lecturer offline API directly from the new frontend');

