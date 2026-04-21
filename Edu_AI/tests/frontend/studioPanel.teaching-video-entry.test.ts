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
  'StudioPanel should open the teaching-video entry modal directly for the video action',
);
assert.doesNotMatch(
  studioPanel,
  /configType === 'video'/,
  'StudioPanel should not keep a dedicated video branch inside the generic config modal',
);
assert.doesNotMatch(
  studioPanel,
  /name="videoGenerationMode"/,
  'StudioPanel should not render the video generation mode field inside the generic config modal',
);
assert.match(
  studioPanel,
  /if\s*\(generationMode\s*===\s*'realtime'\)\s*\{[\s\S]*createAiLectureSession\(/,
  'StudioPanel should create an AI lecture session only for the realtime teaching-video chain',
);
assert.match(
  studioPanel,
  /if\s*\(generationMode\s*===\s*'offline'\)\s*\{[\s\S]*createTeachingVideoTask\(courseId,\s*\{\s*ppt_material_id:\s*pptMaterialId\s*\}\)/,
  'StudioPanel should create the offline teaching video task only for the offline chain',
);
assert.doesNotMatch(
  studioPanel,
  /Promise\.allSettled\(\s*\[\s*createAiLectureSession[\s\S]*createTeachingVideoTask/s,
  'StudioPanel should no longer start realtime and offline teaching-video tasks together',
);
assert.match(
  studioPanel,
  /if\s*\(generationMode\s*===\s*'realtime'\)\s*\{[\s\S]*window\.localStorage\.setItem\(\s*AI_LECTURE_AUTOSTART_REQUEST_KEY/,
  'StudioPanel should only persist the autoplay handoff request for realtime teaching-video playback',
);
assert.match(
  studioPanel,
  /if\s*\(generationMode\s*===\s*'offline'\)\s*\{[\s\S]*setTeachingVideoTaskId\(/,
  'StudioPanel should persist the offline teaching-video task id only for the offline chain',
);
assert.doesNotMatch(
  studioPanel,
  /if\s*\(generationMode\s*===\s*'realtime'\)\s*\{[\s\S]*addGeneratedFile\(\s*\{[\s\S]*type:\s*'ai_lecture_session'/s,
  'StudioPanel should not add realtime AI lecture sessions into the workbench file list from the teaching-video flow',
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
  /<TeachingVideoEntryModal[\s\S]*generationMode=\{teachingVideoGenerationMode\}/,
  'StudioPanel should pass the current teaching-video generation mode into the single-step modal',
);
assert.match(
  studioPanel,
  /<TeachingVideoEntryModal[\s\S]*onGenerationModeChange=\{setTeachingVideoGenerationMode\}/,
  'StudioPanel should let the single-step modal update the selected teaching-video chain',
);
assert.match(
  studioPanel,
  /window\.location\.hash = '#video'/,
  'StudioPanel should redirect to the video player after creating an AI lecture session',
);

console.log('studioPanel.teaching-video-entry tests passed');
