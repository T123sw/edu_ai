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

console.log('courseMaterialToMarkdown tests passed');
