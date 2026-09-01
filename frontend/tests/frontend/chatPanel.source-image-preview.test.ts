import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanelFile = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanelFile,
  /const \[sourceImageUrls,\s*setSourceImageUrls\] = useState<Record<string, string>>\(\{\}\);/,
  'ChatPanel should keep authenticated preview URLs for AI image evidence cards',
);

assert.match(
  chatPanelFile,
  /const isImage = String\(\(source as any\)\?\.modality \|\| \(source as any\)\?\.metadata\?\.modality \|\| ''\)\.toLowerCase\(\) === 'image';/,
  'ChatPanel should detect image evidence from either top-level or metadata modality',
);

assert.match(
  chatPanelFile,
  /const imageUrl = \(\(source as any\)\?\.image_url \|\| \(source as any\)\?\.metadata\?\.image_url\) as string \| undefined;/,
  'ChatPanel should read AI image evidence URLs from normalized source payloads',
);

assert.match(
  chatPanelFile,
  /const resolvedImageUrl = imageUrl \? sourceImageUrls\[imageUrl\] : '';/,
  'ChatPanel should map AI image evidence URLs through authenticated blob previews',
);

assert.match(
  chatPanelFile,
  /persistedSourceImageUrls/,
  'ChatPanel should preload image evidence media for the current conversation',
);

console.log('chatPanel.source-image-preview tests passed');
