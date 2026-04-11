const path = require('path');
const { AppError } = require('./errors');

const ALLOWED_ROLES = new Set(['cover', 'toc', 'section', 'content', 'thanks']);
const ALLOWED_IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'webp', 'svg']);
const ALLOWED_VIDEO_EXTENSIONS = new Set(['mp4', 'webm', 'mov']);

function normalizeLineEndings(markdown) {
  return String(markdown || '').replace(/\r\n/g, '\n');
}

function trimValue(value) {
  return String(value || '').trim();
}

function parseContentProtocol(markdown, { allowLoose = false } = {}) {
  const source = normalizeLineEndings(markdown);
  const lines = source.split('\n');
  const deck = {};
  const slides = [];
  let currentSlide = null;
  let currentSection = null;

  function ensureSlide() {
    if (!currentSlide) {
      throw new AppError('INVALID_CONTENT_FORMAT', 'Slide field found before any `## Slide N` header.', 400);
    }
  }

  function finishSlide() {
    if (!currentSlide) {
      return;
    }

    if (!allowLoose) {
      if (!trimValue(currentSlide.role)) {
        throw new AppError(
          'INVALID_CONTENT_FORMAT',
          `Slide ${currentSlide.slide_number} is missing \`- Role:\`.`,
          400
        );
      }

      if (!ALLOWED_ROLES.has(currentSlide.role)) {
        throw new AppError(
          'INVALID_CONTENT_FORMAT',
          `Slide ${currentSlide.slide_number} has unsupported Role: ${currentSlide.role}.`,
          400
        );
      }

      if (!trimValue(currentSlide.title)) {
        throw new AppError(
          'INVALID_CONTENT_FORMAT',
          `Slide ${currentSlide.slide_number} is missing \`- Title:\`.`,
          400
        );
      }

      if (!currentSlide.hasBlocks) {
        throw new AppError(
          'INVALID_CONTENT_FORMAT',
          `Slide ${currentSlide.slide_number} is missing \`### Blocks\`.`,
          400
        );
      }
    }

    slides.push(currentSlide);
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();

    const slideHeaderMatch = trimmed.match(/^##\s+Slide\s+(\d+)\s*$/i);
    if (slideHeaderMatch) {
      finishSlide();
      currentSlide = {
        slide_number: Number.parseInt(slideHeaderMatch[1], 10),
        title: '',
        role: '',
        hasBlocks: false,
        blockTypes: [],
        mediaBlocks: [],
        rawLines: [line],
      };
      currentSection = null;
      continue;
    }

    if (currentSlide) {
      currentSlide.rawLines.push(line);
    }

    if (trimmed === '### Blocks') {
      ensureSlide();
      currentSlide.hasBlocks = true;
      currentSection = 'blocks';
      continue;
    }

    if (trimmed === '### Notes') {
      ensureSlide();
      currentSection = 'notes';
      continue;
    }

    if (!currentSlide) {
      const deckFieldMatch = trimmed.match(/^- (Title|Subtitle|Theme):\s*(.+)\s*$/);
      if (deckFieldMatch) {
        deck[deckFieldMatch[1].toLowerCase()] = deckFieldMatch[2];
      }
      continue;
    }

    const roleMatch = trimmed.match(/^- Role:\s*(.+)\s*$/);
    if (roleMatch) {
      currentSlide.role = roleMatch[1].trim();
      continue;
    }

    const titleMatch = trimmed.match(/^- Title:\s*(.+)\s*$/);
    if (titleMatch) {
      currentSlide.title = titleMatch[1].trim();
      continue;
    }

    if (currentSection === 'blocks') {
      const blockMatch = line.match(/^- ([A-Za-z-]+):(.*)$/);
      if (blockMatch) {
        const blockType = blockMatch[1];
        currentSlide.blockTypes.push(blockType);

        if (blockType === 'Media') {
          const block = {
            lineIndex: index,
            fields: {},
          };
          let cursor = index + 1;
          while (cursor < lines.length) {
            const nestedLine = lines[cursor];
            const nestedTrimmed = nestedLine.trim();

            if (!nestedTrimmed) {
              cursor += 1;
              continue;
            }

            if (/^##\s+Slide\s+\d+/i.test(nestedTrimmed) || nestedTrimmed === '### Notes') {
              break;
            }

            if (/^- [A-Za-z-]+:/.test(nestedLine)) {
              break;
            }

            const fieldMatch = nestedLine.match(/^\s+- ([A-Za-z-]+):\s*(.*)$/);
            if (fieldMatch) {
              block.fields[fieldMatch[1]] = fieldMatch[2];
              block.lastFieldLineIndex = cursor;
            }
            cursor += 1;
          }
          currentSlide.mediaBlocks.push(block);
        }
      }
    }
  }

  finishSlide();

  if (!allowLoose && slides.length === 0) {
    throw new AppError('INVALID_CONTENT_FORMAT', 'The document must contain at least one `## Slide N` block.', 400);
  }

  return { deck, slides, lines, source };
}

function parseSingleSlideContent(markdown) {
  const parsed = parseContentProtocol(markdown, { allowLoose: false });
  if (parsed.slides.length !== 1) {
    throw new AppError('INVALID_CONTENT_FORMAT', 'Single-slide content must contain exactly one `## Slide N` block.', 400);
  }
  return parsed;
}

function previewLine(value, maxLength = 160) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...(+${text.length - maxLength} chars)`;
}

function summarizeContentProtocol(input, { previewChars = 160 } = {}) {
  const parsed = typeof input === 'string' ? parseContentProtocol(input) : input;
  const slides = Array.isArray(parsed?.slides) ? parsed.slides : [];
  return {
    deck: {
      title: trimValue(parsed?.deck?.title),
      subtitle: trimValue(parsed?.deck?.subtitle),
      theme: trimValue(parsed?.deck?.theme),
    },
    slideCount: slides.length,
    slides: slides.map((slide) => ({
      slide_number: slide.slide_number,
      role: trimValue(slide.role),
      title: trimValue(slide.title),
      blockTypes: Array.isArray(slide.blockTypes) ? [...slide.blockTypes] : [],
      hasNotes: slide.rawLines.some((line) => String(line || '').trim() === '### Notes'),
      preview: previewLine(slide.rawLines.join('\n'), previewChars),
    })),
  };
}

function getExtensionFromUrl(url) {
  const input = trimValue(url);
  if (!input) return '';

  if (input.startsWith('data:')) {
    const mimeMatch = input.match(/^data:([^;]+);/i);
    if (!mimeMatch) return '';
    const mime = mimeMatch[1].toLowerCase();
    const parts = mime.split('/');
    return parts[1] || '';
  }

  try {
    const parsed = new URL(input);
    const ext = path.extname(parsed.pathname).replace(/^\./, '').toLowerCase();
    return ext;
  } catch {
    const ext = path.extname(input).replace(/^\./, '').toLowerCase();
    return ext;
  }
}

function validateMediaFieldSet(mediaFields, slideNumber) {
  const kind = trimValue(mediaFields.Kind).toLowerCase();
  const url = trimValue(mediaFields.URL);
  const posterUrl = trimValue(mediaFields['Poster-URL']);

  if (!kind || !['image', 'video'].includes(kind)) {
    throw new AppError(
      'INVALID_CONTENT_FORMAT',
      `Slide ${slideNumber} has a Media block with invalid Kind.`,
      400
    );
  }

  if (!url) {
    throw new AppError(
      'INVALID_CONTENT_FORMAT',
      `Slide ${slideNumber} has a Media block without URL.`,
      400
    );
  }

  if (kind === 'image') {
    const ext = getExtensionFromUrl(url);
    if (ext && !ALLOWED_IMAGE_EXTENSIONS.has(ext)) {
      throw new AppError(
        'UNSUPPORTED_MEDIA_TYPE',
        `Slide ${slideNumber} image media type is not supported: ${ext}.`,
        400
      );
    }
  }

  if (kind === 'video') {
    const ext = getExtensionFromUrl(url);
    if (ext && !ALLOWED_VIDEO_EXTENSIONS.has(ext)) {
      throw new AppError(
        'UNSUPPORTED_MEDIA_TYPE',
        `Slide ${slideNumber} video media type is not supported: ${ext}.`,
        400
      );
    }

    if (posterUrl) {
      const posterExt = getExtensionFromUrl(posterUrl);
      if (posterExt && !ALLOWED_IMAGE_EXTENSIONS.has(posterExt)) {
        throw new AppError(
          'UNSUPPORTED_MEDIA_TYPE',
          `Slide ${slideNumber} poster media type is not supported: ${posterExt}.`,
          400
        );
      }
    }
  }
}

function validateMediaBlocks(slides) {
  for (const slide of slides) {
    if (slide.mediaBlocks.length > 1) {
      throw new AppError(
        'INVALID_CONTENT_FORMAT',
        `Slide ${slide.slide_number} contains more than one Media block.`,
        400
      );
    }

    for (const mediaBlock of slide.mediaBlocks) {
      validateMediaFieldSet(mediaBlock.fields, slide.slide_number);
    }
  }
}

function injectLocalizedMediaPaths(markdown, insertions) {
  const lines = normalizeLineEndings(markdown).split('\n');
  const sorted = [...insertions].sort((a, b) => b.afterLineIndex - a.afterLineIndex);

  for (const insertion of sorted) {
    lines.splice(insertion.afterLineIndex + 1, 0, ...insertion.lines);
  }

  return `${lines.join('\n').trim()}\n`;
}

module.exports = {
  ALLOWED_IMAGE_EXTENSIONS,
  ALLOWED_ROLES,
  ALLOWED_VIDEO_EXTENSIONS,
  getExtensionFromUrl,
  injectLocalizedMediaPaths,
  parseContentProtocol,
  parseSingleSlideContent,
  summarizeContentProtocol,
  validateMediaBlocks,
};
