import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(
  file,
  /const refreshCourseMaterials = React\.useCallback[\s\S]*replaceCourseMaterialGeneratedFiles\(/,
  'refreshCourseMaterials should replace course-material scoped generatedFiles from the backend snapshot',
);
assert.match(
  file,
  /useEffect\(\(\) => \{[\s\S]*void refreshCourseMaterials\(\)/,
  'StudioPanel should hydrate generated files from persisted course materials on mount/course change',
);

console.log('studioPanel.course-material-sync tests passed');
