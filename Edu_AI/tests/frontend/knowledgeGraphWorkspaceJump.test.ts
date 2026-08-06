import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const graphPageFile = readFileSync(
  new URL('../../src/pages/teacher/KnowledgeGraphPage.tsx', import.meta.url),
  'utf8',
);
const stitchGraphPageFile = readFileSync(
  new URL('../../src/stitch/pages/KnowledgeGraph.tsx', import.meta.url),
  'utf8',
);

assert.match(
  graphPageFile,
  /const isCourseRootSelected = useMemo\(/,
  'KnowledgeGraphPage should track whether the selected node is the course root',
);

assert.match(
  graphPageFile,
  /const handleJumpToAiStudio = \(\) => \{[\s\S]*scopeType:\s*isCourseRootSelected\s*\?\s*'course'\s*:\s*'knowledge_point'/,
  'KnowledgeGraphPage should jump to the AI workspace with course scope when the root node is selected',
);

assert.match(
  graphPageFile,
  /const handleJumpToAiStudio = \(\) => \{[\s\S]*scopeId:\s*isCourseRootSelected\s*\?\s*undefined\s*:\s*selectedNodeId/,
  'KnowledgeGraphPage should omit scopeId when jumping from the course root node',
);

assert.doesNotMatch(
  graphPageFile,
  /const handleJumpToAiStudio = \(\) => \{[\s\S]*scopeType:\s*'knowledge_point'[\s\S]*scopeId:\s*selectedNodeId/,
  'KnowledgeGraphPage should not hard-code every AI workspace jump as a knowledge-point scope',
);

assert.match(
  stitchGraphPageFile,
  /buildTeacherCourseHash\("ai", courseId/,
  'Stitch knowledge graph jumps should preserve the URL-derived course identity',
);

console.log('knowledgeGraphWorkspaceJump frontend tests passed');
