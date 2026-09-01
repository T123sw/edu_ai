import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(
  new URL('../../src/stitch/pages/AIWorkspace.tsx', import.meta.url),
  'utf8',
);

assert.match(
  file,
  /readWorkspaceScopeFromSearch/,
  'stitch AI workspace should read workspace scope from the hash query params',
);

assert.match(
  file,
  /getHashSearchParams/,
  'stitch AI workspace should extract URLSearchParams from window.location.hash',
);

assert.match(
  file,
  /workspaceScope=\{workspaceScope\}/,
  'stitch AI workspace should pass the parsed workspace scope into child panels',
);

assert.match(
  file,
  /onWorkspaceScopeChange=\{/,
  'stitch AI workspace should keep the hash query in sync when a loaded conversation changes scope',
);

console.log('stitchAIWorkspace.scope tests passed');
