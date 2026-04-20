import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const typesFile = readFileSync(new URL('../../src/stitch/api/types.ts', import.meta.url), 'utf8');
const coursesApiFile = readFileSync(new URL('../../src/stitch/api/courses.ts', import.meta.url), 'utf8');
const graphPageFile = readFileSync(new URL('../../src/stitch/pages/KnowledgeGraph.tsx', import.meta.url), 'utf8');

assert.match(
  typesFile,
  /hours\?\s*:\s*number/,
  'KnowledgeGraphNode.data should expose optional numeric hours',
);

assert.match(
  typesFile,
  /export type KnowledgeGraphHourAllocationRequest[\s\S]*total_hours:\s*number/,
  'types should define a total-hours allocation request',
);

assert.match(
  typesFile,
  /export type KnowledgeGraphHourAllocationResponse[\s\S]*allocation:/,
  'types should define an allocation response with metadata',
);

assert.match(
  coursesApiFile,
  /allocateKnowledgeGraphHours\(/,
  'courses API should expose allocateKnowledgeGraphHours',
);

assert.match(
  coursesApiFile,
  /\/api\/courses\/\$\{courseId\}\/knowledge-graph\/allocate-hours/,
  'courses API helper should call the backend allocation route',
);

assert.match(
  coursesApiFile,
  /method:\s*["']POST["']/,
  'allocation API helper should use POST',
);

assert.match(
  graphPageFile,
  /allocateKnowledgeGraphHours/,
  'KnowledgeGraphPage should call the backend allocation helper',
);

assert.match(
  graphPageFile,
  /hours:\s*typeof root\.data\?\.hours === ["']number["'] \? root\.data\.hours : null/,
  'flattenGraph should read data.hours into flat node state',
);

assert.match(
  graphPageFile,
  /data:\s*\{[\s\S]*hours:\s*node\.hours \?\? undefined/,
  'buildGraph should preserve flat node hours in node data',
);

assert.match(
  graphPageFile,
  /allocatingHours/,
  'KnowledgeGraphPage should expose a loading state while allocation runs',
);

console.log('knowledgeGraphHours frontend tests passed');
