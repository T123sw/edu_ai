import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync('d:/github/edu_ai/Edu_AI/src/components/teacher/StudioPanel.tsx', 'utf8');

const refreshDeclaration = file.indexOf('const refreshCourseMaterials = React.useCallback');
const effectDependencyUsage = file.indexOf('refreshCourseMaterials]);');

assert.notEqual(refreshDeclaration, -1, 'refreshCourseMaterials declaration should exist');
assert.notEqual(effectDependencyUsage, -1, 'refreshCourseMaterials dependency usage should exist');
assert.ok(
  refreshDeclaration < effectDependencyUsage,
  'refreshCourseMaterials must be declared before any hook dependency references it',
);

console.log('studioPanel.refresh-order tests passed');
