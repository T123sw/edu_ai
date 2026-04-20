import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const api = readFileSync(new URL('../../src/services/teacher/api.ts', import.meta.url), 'utf8');

assert.match(api, /export interface AiLectureSessionMaterialResponse/, 'Teacher API should expose the AI lecture session material response type');
assert.match(api, /export const createAiLectureSession = async\s*\(/, 'Teacher API should expose AI lecture session creation');
assert.match(api, /\/api\/courses\/\$\{courseId\}\/lecture-sessions/, 'Teacher API should call the lecture session backend endpoint');
assert.match(api, /source_ppt_material_id/, 'Teacher API should send the selected PPT material id');

console.log('teacherApi.ai-lecture-session tests passed');
