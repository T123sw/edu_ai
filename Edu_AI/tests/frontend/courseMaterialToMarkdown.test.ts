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

console.log('courseMaterialToMarkdown tests passed');
