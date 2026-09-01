import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(
  new URL('../../src/stitch/pages/KnowledgeGraph.tsx', import.meta.url),
  'utf8',
);

assert.match(
  file,
  /writeWorkspaceScopeToSearch/,
  'stitch knowledge graph jump should use the shared workspace scope serializer',
);

assert.match(
  file,
  /const isCourseRootScope = activeNode\.parentId === null;/,
  'stitch knowledge graph jump should detect the course root node',
);

assert.match(
  file,
  /scopeType:\s*isCourseRootScope \? "course" : "knowledge_point"/,
  'stitch knowledge graph jump should route the root node to course scope and child nodes to knowledge-point scope',
);

assert.match(
  file,
  /scopeId:\s*isCourseRootScope \? undefined : activeNode\.id/,
  'stitch knowledge graph jump should not send a scopeId for the course root scope',
);

assert.doesNotMatch(
  file,
  /\?node=/,
  'stitch knowledge graph jump should not use the old node-only query parameter',
);

console.log('stitchKnowledgeGraph.scope-link tests passed');
