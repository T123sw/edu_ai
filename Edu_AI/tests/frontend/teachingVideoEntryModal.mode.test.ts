import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const modal = readFileSync(new URL('../../src/components/teacher/TeachingVideoEntryModal.tsx', import.meta.url), 'utf8');

assert.match(
  modal,
  /generationMode:\s*'realtime'\s*\|\s*'offline'/,
  'TeachingVideoEntryModal should receive the selected teaching-video chain mode from the workbench flow',
);
assert.match(
  modal,
  /onGenerationModeChange:\s*\(mode:\s*'realtime'\s*\|\s*'offline'\)\s*=>\s*void/,
  'TeachingVideoEntryModal should let the single-step modal push mode changes back to the workbench',
);
assert.match(
  modal,
  /<Radio\.Button value="realtime">[\s\S]*<\/Radio\.Button>/,
  'TeachingVideoEntryModal should render the realtime teaching-video chain option inside the same modal',
);
assert.match(
  modal,
  /<Radio\.Button value="offline">[\s\S]*<\/Radio\.Button>/,
  'TeachingVideoEntryModal should render the offline teaching-video chain option inside the same modal',
);
assert.match(
  modal,
  /onChange=\{\(event\)\s*=>\s*onGenerationModeChange\(event\.target\.value\)\}/,
  'TeachingVideoEntryModal should update the selected mode in-place without a second step',
);
assert.match(
  modal,
  /onSubmit:\s*\(payload:\s*\{\s*pptMaterialId:\s*string;\s*pptTitle:\s*string;\s*generationMode:\s*'realtime'\s*\|\s*'offline'/s,
  'TeachingVideoEntryModal should forward the chosen teaching-video mode when submitting the selected PPT',
);
assert.match(
  modal,
  /generationMode,\s*\n\s*\}\);/,
  'TeachingVideoEntryModal should include the chosen generation mode in its submit payload',
);

console.log('teachingVideoEntryModal.mode tests passed');
