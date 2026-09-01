import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanelFile = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanelFile,
  /inputVideos\?: ChatInputVideoV2\[\];/,
  'ChatPanel message model should keep uploaded chat videos on each message',
);

assert.match(
  chatPanelFile,
  /inputVideos:\s*\(msg\.input_videos \|\| \[\]\) as ChatInputVideoV2\[\],/,
  'ChatPanel should restore persisted input videos from conversation history',
);

assert.match(
  chatPanelFile,
  /userMessage\.inputVideos = inputVideos;/,
  'ChatPanel should attach uploaded videos to the outgoing user message bubble before rendering it',
);

assert.match(
  chatPanelFile,
  /const \[messageVideoUrls,\s*setMessageVideoUrls\] = useState<Record<string, string>>\(\{\}\);/,
  'ChatPanel should keep authenticated preview URLs for sent message videos',
);

assert.match(
  chatPanelFile,
  /item\.inputVideos && item\.inputVideos\.length > 0/,
  'ChatPanel should render sent message videos when a message carries inputVideos',
);

assert.match(
  chatPanelFile,
  /loadPreviewMediaUrl\(/,
  'ChatPanel should load persisted chat videos through the authenticated media preview helper',
);

const apiServiceFile = readFileSync(
  new URL('../../src/services/teacher/api.ts', import.meta.url),
  'utf8',
);

assert.match(
  apiServiceFile,
  /input_videos\?: ChatInputVideoV2\[\];/,
  'conversation detail typing should include persisted input_videos',
);

console.log('chatPanel.message-video-history tests passed');
