const fs = require('fs/promises');
const path = require('path');
const { repoRoot } = require('../config');
const { AppError } = require('../domain/errors');
const {
  ALLOWED_IMAGE_EXTENSIONS,
  ALLOWED_VIDEO_EXTENSIONS,
  getExtensionFromUrl,
  injectLocalizedMediaPaths,
  parseContentProtocol,
  validateMediaBlocks,
} = require('../domain/content-protocol');

function inferExtensionFromContentType(contentType, fallback) {
  const normalized = String(contentType || '').toLowerCase().split(';')[0].trim();
  if (!normalized) {
    return fallback || '';
  }

  const mapping = {
    'image/png': 'png',
    'image/jpeg': 'jpg',
    'image/webp': 'webp',
    'image/svg+xml': 'svg',
    'video/mp4': 'mp4',
    'video/webm': 'webm',
    'video/quicktime': 'mov',
  };

  return mapping[normalized] || fallback || '';
}

function ensureExtensionSupported(kind, extension, slideNumber, label) {
  if (!extension) {
    return;
  }

  if (kind === 'image' && !ALLOWED_IMAGE_EXTENSIONS.has(extension)) {
    throw new AppError(
      'UNSUPPORTED_MEDIA_TYPE',
      `Slide ${slideNumber} ${label} type is not supported: ${extension}.`,
      400
    );
  }

  if (kind === 'video' && !ALLOWED_VIDEO_EXTENSIONS.has(extension)) {
    throw new AppError(
      'UNSUPPORTED_MEDIA_TYPE',
      `Slide ${slideNumber} ${label} type is not supported: ${extension}.`,
      400
    );
  }
}

function isRemoteUrl(input) {
  return /^https?:\/\//i.test(String(input || '').trim());
}

function isDataUrl(input) {
  return /^data:/i.test(String(input || '').trim());
}

async function copyLocalFileToTarget(inputPath, filePath, { kind, slideNumber, label }) {
  const resolvedPath = path.isAbsolute(inputPath) ? inputPath : path.join(repoRoot, inputPath);

  try {
    await fs.access(resolvedPath);
  } catch {
    throw new AppError(
      'MEDIA_DOWNLOAD_FAILED',
      `Slide ${slideNumber} failed to load local ${label}.`,
      500,
      { path: inputPath }
    );
  }

  const ext = getExtensionFromUrl(resolvedPath);
  ensureExtensionSupported(kind, ext, slideNumber, label);
  await fs.copyFile(resolvedPath, filePath);
}

async function downloadUrlToFile(url, filePath, { kind, slideNumber, label }) {
  if (!isRemoteUrl(url) && !isDataUrl(url)) {
    await copyLocalFileToTarget(url, filePath, { kind, slideNumber, label });
    return;
  }

  let response;
  try {
    response = await fetch(url);
  } catch (error) {
    throw new AppError(
      'MEDIA_DOWNLOAD_FAILED',
      `Slide ${slideNumber} failed to download ${label}.`,
      500,
      { url, cause: error.message }
    );
  }

  if (!response.ok) {
    throw new AppError(
      'MEDIA_DOWNLOAD_FAILED',
      `Slide ${slideNumber} failed to download ${label}.`,
      500,
      { url, status: response.status }
    );
  }

  const fallbackExt = getExtensionFromUrl(url);
  const ext = inferExtensionFromContentType(response.headers.get('content-type'), fallbackExt);
  ensureExtensionSupported(kind, ext, slideNumber, label);

  const arrayBuffer = await response.arrayBuffer();
  await fs.writeFile(filePath, Buffer.from(arrayBuffer));
}

async function localizeMediaAssets(markdown, { mediaDir, contentKind = 'deck' }) {
  const parsed = parseContentProtocol(markdown);
  validateMediaBlocks(parsed.slides);
  await fs.mkdir(mediaDir, { recursive: true });

  const insertions = [];
  const assets = [];

  for (const slide of parsed.slides) {
    const mediaBlock = slide.mediaBlocks[0];
    if (!mediaBlock) {
      continue;
    }

    const fields = mediaBlock.fields;
    const kind = String(fields.Kind || '').toLowerCase();
    const mainUrl = String(fields.URL || '').trim();
    const posterUrl = String(fields['Poster-URL'] || '').trim();

    const mainExt = getExtensionFromUrl(mainUrl) || (kind === 'image' ? 'png' : 'mp4');
    ensureExtensionSupported(kind, mainExt, slide.slide_number, 'media');

    const mainFileName = `slide-${String(slide.slide_number).padStart(2, '0')}-main.${mainExt}`;
    const mainFilePath = path.join(mediaDir, mainFileName);
    await downloadUrlToFile(mainUrl, mainFilePath, {
      kind,
      slideNumber: slide.slide_number,
      label: 'media',
    });

    const addedLines = [`  - Local-Path: ./media/${mainFileName}`];
    assets.push({
      slide_number: slide.slide_number,
      kind,
      file_name: mainFileName,
      local_path: `./media/${mainFileName}`,
    });

    if (kind === 'video' && posterUrl) {
      const posterExt = getExtensionFromUrl(posterUrl) || 'jpg';
      ensureExtensionSupported('image', posterExt, slide.slide_number, 'poster');
      const posterFileName = `slide-${String(slide.slide_number).padStart(2, '0')}-poster.${posterExt}`;
      const posterFilePath = path.join(mediaDir, posterFileName);
      await downloadUrlToFile(posterUrl, posterFilePath, {
        kind: 'image',
        slideNumber: slide.slide_number,
        label: 'poster',
      });
      addedLines.push(`  - Local-Poster-Path: ./media/${posterFileName}`);
      assets.push({
        slide_number: slide.slide_number,
        kind: 'image',
        file_name: posterFileName,
        local_path: `./media/${posterFileName}`,
        role: 'poster',
      });
    }

    insertions.push({
      afterLineIndex: mediaBlock.lastFieldLineIndex || mediaBlock.lineIndex,
      lines: addedLines,
    });
  }

  return {
    runtimeMarkdown: injectLocalizedMediaPaths(markdown, insertions),
    parsed,
    assets,
    contentKind,
  };
}

module.exports = {
  localizeMediaAssets,
};
