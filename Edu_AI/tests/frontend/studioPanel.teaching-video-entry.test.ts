import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(
  studioPanel,
  /import\s+TeachingVideoEntryModal\s+from\s+['"]\.\/TeachingVideoEntryModal['"]/,
  'StudioPanel should import the teaching video entry modal',
);
assert.match(
  studioPanel,
  /if\s*\(type\s*===\s*'video'\)\s*\{[\s\S]*setTeachingVideoEntryVisible\(true\)/,
  'StudioPanel should open the teaching video entry modal for the video action',
);
assert.match(
  studioPanel,
  /createTeachingVideoTask\(/,
  'StudioPanel should submit teaching video tasks through the teaching video API',
);
assert.match(
  studioPanel,
  /getTeachingVideoTaskStatus\(/,
  'StudioPanel should poll teaching video task status after submission',
);
assert.match(
  studioPanel,
  /viewingFile\.type === 'video'/,
  'StudioPanel should render a dedicated video preview branch',
);
assert.match(
  studioPanel,
  /<TeachingVideoEntryModal[\s\S]*onSubmit=\{handleTeachingVideoSubmit\}/,
  'StudioPanel should render the teaching video entry modal and bind its submit handler',
);
assert.match(
  studioPanel,
  /title:\s*'教学视频'|title="教学视频"/,
  'StudioPanel should expose a teaching video card in the workbench',
);
assert.match(
  studioPanel,
  /<video[\s\S]*src=\{videoUrl\}/,
  'StudioPanel should render an HTML video player for completed teaching videos',
);
assert.match(
  studioPanel,
  /videoErrorMessage/,
  'StudioPanel should surface backend teaching video failure details',
);
assert.match(
  studioPanel,
  /useEffect\(\(\)\s*=>\s*\{[\s\S]*generatedFiles\.find\([\s\S]*item\.type !== 'video'[\s\S]*generationState[\s\S]*status === 'processing'[\s\S]*setTeachingVideoTaskId\(/,
  'StudioPanel should resume polling persisted processing teaching video tasks after reload',
);

console.log('studioPanel.teaching-video-entry tests passed');
