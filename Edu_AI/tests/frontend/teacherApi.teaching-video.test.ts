import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const api = readFileSync(new URL('../../src/services/teacher/api.ts', import.meta.url), 'utf8');

assert.match(api, /export interface TeachingVideoPptItem/, 'Teacher API should export the teaching video PPT item type');
assert.match(api, /export interface TeachingVideoTaskResponse/, 'Teacher API should export the teaching video task response type');
assert.match(api, /export const getTeachingVideoPpts = async\s*\(/, 'Teacher API should expose the teaching video PPT listing call');
assert.match(api, /\/teaching-videos\/ppts/, 'Teacher API should call the backend teaching video PPT listing endpoint');
assert.match(api, /export const createTeachingVideoTask = async\s*\(/, 'Teacher API should expose the teaching video creation call');
assert.match(api, /\/teaching-videos`/, 'Teacher API should call the backend teaching video creation endpoint');
assert.match(api, /export const getTeachingVideoTaskStatus = async\s*\(/, 'Teacher API should expose the teaching video task status call');
assert.match(api, /\/teaching-videos\/tasks\/\$\{taskId\}/, 'Teacher API should poll the backend teaching video task status endpoint');

console.log('teacherApi.teaching-video tests passed');
