import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/pages/teacher/CourseMaterialsPage.tsx', import.meta.url), 'utf8');
const api = readFileSync(new URL('../../src/services/teacher/api.ts', import.meta.url), 'utf8');

assert.match(page, /key:\s*'ppt'/, 'Course materials page should register a PPT tab');
assert.match(page, /FilePptOutlined/, 'Course materials page should use a PPT icon');
assert.match(api, /type === 'ppt'/, 'Course material normalization should recognize persisted PPT materials');

console.log('courseMaterials.ppt tests passed');
