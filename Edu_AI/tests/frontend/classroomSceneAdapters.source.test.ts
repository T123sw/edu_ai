import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const classroomPlayer = readFileSync(
  new URL('../../src/stitch/pages/ClassroomPlayer.tsx', import.meta.url),
  'utf8',
);
const sceneRenderer = readFileSync(
  new URL('../../src/openmaic/ClassroomSceneRenderer.tsx', import.meta.url),
  'utf8',
);
const interactivePlayer = readFileSync(
  new URL('../../src/openmaic/InteractiveScenePlayer.tsx', import.meta.url),
  'utf8',
);

assert.match(
  classroomPlayer,
  /<ClassroomSceneRenderer/,
  'classroom page should delegate scene playback to the local adapter layer',
);
assert.doesNotMatch(
  classroomPlayer,
  /P3-1 只接了 slide/,
  'classroom page should not retain the old slide-only fallback',
);
assert.match(
  sceneRenderer,
  /case ['"]interactive['"]/,
  'scene renderer should dispatch interactive scenes',
);
assert.match(
  interactivePlayer,
  /<iframe/,
  'interactive scenes should render in an iframe',
);
assert.match(
  interactivePlayer,
  /sandbox=/,
  'interactive iframe should declare an explicit sandbox',
);
assert.doesNotMatch(
  interactivePlayer,
  /allow-same-origin/,
  'inline interactive content must not share the application origin',
);

console.log('classroom scene adapter source tests passed');
