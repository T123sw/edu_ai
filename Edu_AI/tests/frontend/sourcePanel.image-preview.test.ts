import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const sourcePanel = readFileSync(new URL('../../src/components/teacher/SourcePanel.tsx', import.meta.url), 'utf8');

assert.match(
  sourcePanel,
  /const imageExts = \[[\s\S]*'\.png'[\s\S]*'\.jpg'[\s\S]*'\.jpeg'[\s\S]*'\.webp'[\s\S]*'\.bmp'[\s\S]*'\.gif'[\s\S]*\]/,
  'SourcePanel should recognize common image extensions',
);
assert.match(
  sourcePanel,
  /importImageDocument\(/,
  'SourcePanel should route image uploads through the RAG image import endpoint',
);
assert.match(
  sourcePanel,
  /accept="[^"]*\.png[^"]*\.jpg[^"]*\.jpeg[^"]*\.webp[^"]*\.bmp[^"]*\.gif/,
  'SourcePanel upload input should accept image files',
);
assert.match(
  sourcePanel,
  /<img[\s\S]*src=\{directPreviewImageUrl/,
  'SourcePanel preview should render image documents with an authenticated preview img element',
);
assert.match(
  sourcePanel,
  /previewContent\?\.chunks\.filter\(\(chunk\) => isRenderableImageChunk\(chunk\)\)/,
  'SourcePanel should extract renderable image chunks from document preview content',
);
assert.match(
  sourcePanel,
  /chunk\.metadata\?\.image_url/,
  'SourcePanel should use chunk metadata image_url when rendering embedded document images',
);
assert.match(
  sourcePanel,
  /loadPreviewMediaUrl\(/,
  'SourcePanel should resolve preview images through an authenticated media loader',
);

const ragService = readFileSync(new URL('../../src/services/rag.ts', import.meta.url), 'utf8');

assert.match(
  ragService,
  /export async function loadPreviewMediaUrl\(/,
  'rag service should expose an authenticated media preview loader',
);
assert.match(
  ragService,
  /Authorization.*Bearer/,
  'authenticated media preview loader should send the bearer token when fetching protected media',
);
assert.match(
  ragService,
  /URL\.createObjectURL/,
  'authenticated media preview loader should convert fetched media into a blob URL for img preview',
);

console.log('sourcePanel.image-preview tests passed');
