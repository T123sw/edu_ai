const cheerio = require('cheerio');
const { parseContentProtocol } = require('./content-protocol');
const { extractSlides, inferLayout, inferTitle } = require('./fragment');

function normalizeText(value) {
  return String(value || '')
    .replace(/<[^>]*>/g, '')
    .replace(/\*\*/g, '')
    .replace(/[`"'“”‘’]/g, '')
    .replace(/^[\s\d.、-]+/, '')
    .replace(/[：:，,。；;（）()[\]\s]/g, '')
    .toLowerCase();
}

function visibleText(slideHtml) {
  const $ = cheerio.load(String(slideHtml || ''), { decodeEntities: false });
  return normalizeText($.root().text());
}

function cleanMarker(value) {
  return String(value || '')
    .replace(/\*\*/g, '')
    .replace(/^[\s\d.、-]+/, '')
    .trim();
}

function extractBlockMarkers(slide) {
  const markers = [];
  let inBlocks = false;

  for (const line of slide.rawLines || []) {
    if (/^###\s+Blocks\b/i.test(line)) {
      inBlocks = true;
      continue;
    }
    if (/^###\s+Notes\b/i.test(line)) {
      inBlocks = false;
    }
    if (!inBlocks) {
      continue;
    }

    const boldMarker = line.match(/\*\*([^*]{2,24})\*\*\s*[：:]/);
    if (boldMarker) {
      markers.push(cleanMarker(boldMarker[1]));
    }

    const fieldMarker = line.match(/^\s*-\s*(?:Left-Title|Right-Title|Step-Title|Title)\s*:\s*(.+)$/i);
    if (fieldMarker) {
      markers.push(cleanMarker(fieldMarker[1]));
    }
  }

  const seen = new Set();
  return markers.filter((marker) => {
    const normalized = normalizeText(marker);
    if (!normalized || normalized.length > 36 || seen.has(normalized)) {
      return false;
    }
    seen.add(normalized);
    return true;
  });
}

function addMissingMarkerWarnings({ warnings, parsedSlides, htmlSlides }) {
  parsedSlides.forEach((slide, index) => {
    if (!['content', 'section'].includes(slide.role || '')) {
      return;
    }

    const slideHtml = htmlSlides[index] || '';
    const text = visibleText(slideHtml);
    for (const marker of extractBlockMarkers(slide)) {
      if (!text.includes(normalizeText(marker))) {
        warnings.push({
          code: 'CONTENT_MARKER_MISSING',
          slide_index: index + 1,
          title: inferTitle(slideHtml) || slide.title || '',
          message: `关键内容标记未在页面显示：${marker}`,
        });
      }
    }
  });
}

function addRepeatedLayoutWarnings({ warnings, htmlSlides }) {
  let currentLayout = null;
  let runStart = 0;
  let runLength = 0;

  htmlSlides.forEach((slideHtml, index) => {
    const layout = inferLayout(slideHtml);
    const isTextLayout = /^standard-text/.test(layout);
    if (isTextLayout && layout === currentLayout) {
      runLength += 1;
    } else {
      currentLayout = isTextLayout ? layout : null;
      runStart = index;
      runLength = isTextLayout ? 1 : 0;
    }

    if (runLength === 3) {
      warnings.push({
        code: 'REPEATED_TEXT_LAYOUT',
        slide_index: runStart + 1,
        title: inferTitle(htmlSlides[runStart]) || '',
        message: `连续 3 页使用 ${layout}，整套 PPT 容易产生模板重复感。`,
      });
    }
  });
}

function addStructuredDensityWarnings({ warnings, htmlSlides }) {
  htmlSlides.forEach((slideHtml, index) => {
    const $ = cheerio.load(slideHtml, { decodeEntities: false });
    const hasFlow = $('.structured-flow').length > 0;
    const sectionCount = $('.structured-section').length;
    const listItemCount = $('.structured-section .list-item').length;
    if (hasFlow && sectionCount >= 3 && listItemCount >= 6) {
      warnings.push({
        code: 'STRUCTURED_FLOW_DENSITY_RISK',
        slide_index: index + 1,
        title: inferTitle(slideHtml) || '',
        message: '结构化页同时包含多段解释和流程，底部流程存在被挤压风险。',
      });
    }
  });
}

function buildLayoutQualityReport({ contentMarkdown, fragmentHtml }) {
  const htmlSlides = extractSlides(fragmentHtml);
  const warnings = [];
  const parsed = parseContentProtocol(contentMarkdown, { allowLoose: true });

  addMissingMarkerWarnings({ warnings, parsedSlides: parsed.slides, htmlSlides });
  addRepeatedLayoutWarnings({ warnings, htmlSlides });
  addStructuredDensityWarnings({ warnings, htmlSlides });

  return {
    slide_count: htmlSlides.length,
    warning_count: warnings.length,
    warnings,
  };
}

module.exports = {
  buildLayoutQualityReport,
};
