import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanelFile = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanelFile,
  /const \[pendingImages,\s*setPendingImages\] = useState<[\s\S]*>\(\[\]\);/,
  'ChatPanel should track pending chat images before send',
);

assert.match(
  chatPanelFile,
  /uploadChatImagesV2\(/,
  'ChatPanel should upload pasted or selected images before sending the reply request',
);

assert.match(
  chatPanelFile,
  /onPaste=\{\(event\) => \{\s*void handleImagePaste\(event\);\s*\}\}/,
  'ChatPanel composer should support paste-from-clipboard image input',
);

assert.match(
  chatPanelFile,
  /type="file"[\s\S]*accept="image\/png,image\/jpeg,image\/webp,image\/bmp,image\/gif"/,
  'ChatPanel should expose an image picker for common raster image types',
);

assert.match(
  chatPanelFile,
  /pendingImages\.map\(\(image\) => \{[\s\S]*image\.previewUrl[\s\S]*handleRemovePendingImage\(image\.image_id\)/,
  'ChatPanel should render pending image thumbnails before send',
);

assert.match(
  chatPanelFile,
  /setPendingImages\(\(current\) => current\.filter\(\(image\) => image\.image_id !== imageId\)\)/,
  'ChatPanel should allow removing a pending image before send',
);

const chatServiceFile = readFileSync(
  new URL('../../src/services/teacher/chatV2.ts', import.meta.url),
  'utf8',
);

assert.match(
  chatServiceFile,
  /export interface ChatInputImageV2 \{/,
  'chatV2 service should expose the chat image metadata contract',
);

assert.match(
  chatServiceFile,
  /input_images\?: ChatInputImageV2\[\];/,
  'chatV2 reply payload should carry uploaded image references',
);

assert.match(
  chatServiceFile,
  /export async function uploadChatImagesV2\(/,
  'chatV2 service should expose a chat image upload helper',
);

assert.match(
  chatServiceFile,
  /formData\.append\('files', file, file\.name\)/,
  'chatV2 upload helper should send each selected file as multipart form data',
);

assert.match(
  chatServiceFile,
  /payload\.input_images = options\.inputImages;/,
  'buildChatReplyPayload should include uploaded chat images in the reply payload',
);

console.log('chatPanel.image-input tests passed');
