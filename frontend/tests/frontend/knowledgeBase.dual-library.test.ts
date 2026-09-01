import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(
  new URL('../../src/services/knowledgeBase.ts', import.meta.url),
  'utf8',
);

assert.match(
  file,
  /libraryType\?:\s*'course' \| 'personal'/,
  'knowledgeBase service should expose course/personal library selection',
);

assert.match(
  file,
  /includeDescendants\?:\s*boolean/,
  'knowledgeBase service should expose descendant inclusion for parent course-library queries',
);

assert.match(
  file,
  /params\.set\('library_type', options\.libraryType\)/,
  'document list requests should send library_type to the backend',
);

assert.match(
  file,
  /params\.set\('include_descendants', options\.includeDescendants \? 'true' : 'false'\)/,
  'document list requests should send include_descendants to the backend',
);

assert.match(
  file,
  /formData\.append\('library_type', options\.libraryType\)/,
  'uploads should persist the selected library type',
);

assert.match(
  file,
  /library_type:\s*options\?\.libraryType/,
  'promoting from RAG/personal documents should persist the target library type',
);

console.log('knowledgeBase.dual-library tests passed');
