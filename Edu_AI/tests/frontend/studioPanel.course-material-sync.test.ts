import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync('d:/github/edu_ai/Edu_AI/src/components/teacher/StudioPanel.tsx', 'utf8');

assert.match(
  file,
  /const refreshCourseMaterials = React\.useCallback[\s\S]*addGeneratedFile\(/,
  'refreshCourseMaterials should sync persisted course materials back into generatedFiles',
);
assert.match(
  file,
  /useEffect\(\(\) => \{[\s\S]*void refreshCourseMaterials\(\)/,
  'StudioPanel should hydrate generated files from persisted course materials on mount/course change',
);

console.log('studioPanel.course-material-sync tests passed');
