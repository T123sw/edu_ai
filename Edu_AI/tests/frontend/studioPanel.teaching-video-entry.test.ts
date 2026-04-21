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
  /createAiLectureSession\(/,
  'StudioPanel should create AI lecture sessions through the main backend',
);
assert.match(
  studioPanel,
  /createTeachingVideoTask\(courseId,\s*\{\s*ppt_material_id:\s*pptMaterialId\s*\}\)/,
  'StudioPanel should also submit the offline teaching video task from the same teaching video entry flow',
);
assert.match(
  studioPanel,
  /setTeachingVideoTaskId\(String\(offlineVideoResult\.value\.task_id \|\| ''\)\.trim\(\)\)/,
  'StudioPanel should persist the teaching video task id so the existing polling flow can resume it',
);
assert.match(
  studioPanel,
  /window\.localStorage\.setItem\(\s*AI_LECTURE_AUTOSTART_REQUEST_KEY/,
  'StudioPanel should persist an autoplay handoff request before redirecting',
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
  /window\.location\.hash = '#video'/,
  'StudioPanel should redirect to the video player after creating an AI lecture session',
);
assert.match(
  studioPanel,
  /type:\s*'ai_lecture_session'/,
  'StudioPanel should create AI lecture session artifacts in the workbench',
);

console.log('studioPanel.teaching-video-entry tests passed');
