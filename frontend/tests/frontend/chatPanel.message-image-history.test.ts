import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanelFile = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanelFile,
  /inputImages\?: ChatInputImageV2\[\];/,
  'ChatPanel message model should keep uploaded chat images on each message',
);

assert.match(
  chatPanelFile,
  /inputImages:\s*\(msg\.input_images \|\| \[\]\) as ChatInputImageV2\[\],/,
  'ChatPanel should restore persisted input images from conversation history',
);

assert.match(
  chatPanelFile,
  /userMessage\.inputImages = inputImages;/,
  'ChatPanel should attach uploaded images to the outgoing user message bubble before rendering it',
);

assert.match(
  chatPanelFile,
  /const \[messageImageUrls,\s*setMessageImageUrls\] = useState<Record<string, string>>\(\{\}\);/,
  'ChatPanel should keep authenticated preview URLs for sent message images',
);

assert.match(
  chatPanelFile,
  /loadPreviewMediaUrl\(/,
  'ChatPanel should load persisted chat images through the authenticated media preview helper',
);

assert.match(
  chatPanelFile,
  /item\.inputImages && item\.inputImages\.length > 0/,
  'ChatPanel should render sent message images when a message carries inputImages',
);

console.log('chatPanel.message-image-history tests passed');
