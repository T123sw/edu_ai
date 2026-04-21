import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const coursesApiFile = readFileSync(
  new URL('../../src/stitch/api/courses.ts', import.meta.url),
  'utf8',
);

assert.match(
  coursesApiFile,
  /function hasTextContent\(value: unknown\): value is string/,
  'courses api should define a string guard before trimming markdown content',
);

assert.match(
  coursesApiFile,
  /hasTextContent\(material\.content\)/,
  'courseMaterialToMarkdown should guard non-string material.content values before trimming',
);

assert.match(
  coursesApiFile,
  /function formatPptDeckMarkdown\(/,
  'courses api should define a dedicated PPT deck to markdown formatter',
);

assert.match(
  coursesApiFile,
  /material\.material_type === "ppt"/,
  'courseMaterialToMarkdown should detect PPT materials explicitly',
);

assert.match(
  coursesApiFile,
  /record\.deck_title|record\.title/,
  'courseMaterialToMarkdown should build markdown from PPT deck title metadata when no direct markdown exists',
);

assert.match(
  coursesApiFile,
  /Array\.isArray\(record\.slides\)/,
  'courseMaterialToMarkdown should extract slide content from PPT deck metadata',
);

assert.match(
  coursesApiFile,
  /materialRecord\.report|topLevelCandidates = \[[\s\S]*materialRecord\.report/,
  'courseMaterialToMarkdown should read persisted top-level report markdown fields',
);

assert.match(
  coursesApiFile,
  /function formatQuizMarkdown\(/,
  'courses api should define a dedicated quiz to markdown formatter',
);

assert.match(
  coursesApiFile,
  /material\.material_type === "quiz"/,
  'courseMaterialToMarkdown should detect quiz materials explicitly',
);

assert.match(
  coursesApiFile,
  /Array\.isArray\(material\.questions\)/,
  'courseMaterialToMarkdown should render persisted quiz questions when no markdown exists',
);

assert.match(
  coursesApiFile,
  /function formatLessonPlanMarkdown\(/,
  'courses api should define a dedicated lesson plan to markdown formatter',
);

assert.match(
  coursesApiFile,
  /material\.material_type === "lesson_plan"/,
  'courseMaterialToMarkdown should detect lesson plan materials explicitly',
);

assert.match(
  coursesApiFile,
  /plan\.process/,
  'courseMaterialToMarkdown should render persisted lesson plan process blocks',
);

console.log('courseMaterialToMarkdown tests passed');
