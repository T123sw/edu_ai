import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url), 'utf8');

assert.match(
  source,
  /const isVideo = .*modality.*=== 'video';/,
  'ChatPanel should detect video sources from source metadata',
);

assert.match(
  source,
  /<video[\s\S]*controls[\s\S]*src=\{/,
  'ChatPanel should render a playable video element for video evidence sources',
);

console.log('chatPanel.video-sources tests passed');
