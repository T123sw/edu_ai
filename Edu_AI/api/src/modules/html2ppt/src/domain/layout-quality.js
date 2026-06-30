const cheerio = require('cheerio');
const { parseContentProtocol } = require('./content-protocol');
const { extractSlides, inferLayout, inferTitle } = require('./fragment');

const REQUIRED_SLOT_SELECTORS = {
  'comparison-vs-panels': ['.vs-problem', '.vs-panel', '.vs-teaching-summary'],
  'execution-pipeline': ['.pipeline-card', '.pipeline-teaching-note'],
  'capability-map-grid': ['.capability-hero', '.capability-relation', '.capability-takeaway'],
  'pillar-cards-banner': ['.pillar-card', '.pillar-example', '.pillar-summary-bar'],
  'media-focus': ['.media-focus-image-panel', '.media-observation-list', '.media-conclusion'],
  'architecture-pipeline-spotlight': ['.architecture-summary', '.architecture-stage', '.architecture-spotlight'],
  'dual-core-support': ['.dual-core-summary', '.dual-core-card-primary', '.dual-core-card-secondary'],
  'thesis-evidence-grid': ['.thesis-band', '.evidence-card'],
};

const VISUAL_SLOT_SELECTORS = new Set(['.media-focus-image-panel']);
const BASE_DENSITY_SELECTORS = [
  '.list-item',
  '.surface-card',
  '.card-title',
  '.card-desc',
  '.comparison-row',
  '.pipeline-card',
  '.pipeline-teaching-note',
  '.metric-item',
  '.matrix-cell',
  '.timeline-step',
  '.relationship-node',
  '.quote-text',
  '.pillar-card',
  '.pillar-example',
  '.pillar-summary-bar',
  '.capability-hero',
  '.capability-relation',
  '.capability-takeaway',
  '.media-observation-list',
  '.media-conclusion',
];
const DENSITY_SELECTORS_BY_LAYOUT = {
  'standard-text-structured': [
    '.structured-lead-text',
    '.structured-section-title',
    '.structured-section-text',
    '.structured-flow-step',
  ],
  'comparison-vs-panels': [
    '.vs-problem-text',
    '.vs-panel-heading',
    '.vs-point',
    '.vs-summary',
    '.vs-teaching-summary',
  ],
  'execution-pipeline': ['.pipeline-card', '.pipeline-step-title', '.pipeline-step-copy', '.pipeline-teaching-note'],
  'capability-map-grid': ['.capability-hero', '.capability-node', '.capability-relation', '.capability-takeaway'],
  'pillar-cards-banner': ['.pillar-card', '.pillar-title', '.pillar-copy', '.pillar-example', '.pillar-summary-bar'],
  'architecture-pipeline-spotlight': [
    '.architecture-summary-text',
    '.architecture-stage-title',
    '.architecture-stage-text',
    '.architecture-spotlight-title',
    '.architecture-spotlight-text',
  ],
  'dual-core-support': ['.dual-core-summary-text', '.dual-core-card-title', '.dual-core-card-text'],
  'thesis-evidence-grid': ['.thesis-band-text', '.evidence-card-title', '.evidence-card-text', '.evidence-card-note'],
};

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
  $(
    '.slide-brand, .footer-decoration, .thanks-safe-decor, .slide-safe-decor, img, video, picture, iframe, canvas, svg, object, embed'
  ).remove();
  return normalizeText($.root().text());
}

function hasVisibleText($, node) {
  return normalizeText($(node).text()).length > 0;
}

function hasMediaContent($, slideRoot) {
  return (
    $(slideRoot)
      .find('img, video, picture, iframe, canvas, svg, object, embed, [data-media-kind]')
      .toArray()
      .filter((node) => !$(node).closest('.slide-brand, .footer-decoration').length).length > 0
  );
}

function countVisibleUnits($, slideRoot, layout) {
  const selectors = [...BASE_DENSITY_SELECTORS, ...(DENSITY_SELECTORS_BY_LAYOUT[layout] || [])];
  const countedNodes = new Set();

  selectors.forEach((selector) => {
    $(slideRoot)
      .find(selector)
      .toArray()
      .forEach((node) => {
        if (!hasVisibleText($, node)) {
          return;
        }
        countedNodes.add(node);
      });
  });

  return countedNodes.size;
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

function addContentDensityWarnings({ warnings, parsedSlides, htmlSlides }) {
  parsedSlides.forEach((slide, index) => {
    if ((slide.role || '') !== 'content') {
      return;
    }

    const slideHtml = htmlSlides[index] || '';
    const layout = inferLayout(slideHtml);
    const $ = cheerio.load(slideHtml, { decodeEntities: false });
    const slideRoot = $('.slide').first();
    if (!slideRoot.length || hasMediaContent($, slideRoot)) {
      return;
    }

    if (countVisibleUnits($, slideRoot, layout) < 3) {
      warnings.push({
        code: 'CONTENT_DENSITY_LOW',
        slide_index: index + 1,
        title: inferTitle(slideHtml) || '',
        message: '页面可见信息单元过少，可能导致教学内容偏空。',
      });
    }
  });
}

function pushSparseRiskWarning(warnings, slideIndex, slideHtml, message) {
  warnings.push({
    code: 'LAYOUT_SPARSE_RISK',
    slide_index: slideIndex,
    title: inferTitle(slideHtml) || '',
    message,
  });
}

function addSparseRiskWarnings({ warnings, parsedSlides, htmlSlides }) {
  parsedSlides.forEach((slide, index) => {
    if ((slide.role || '') !== 'content') {
      return;
    }

    const slideHtml = htmlSlides[index] || '';
    const layout = inferLayout(slideHtml);
    const $ = cheerio.load(slideHtml, { decodeEntities: false });
    const slideRoot = $('.slide').first();
    if (!slideRoot.length || hasMediaContent($, slideRoot)) {
      return;
    }

    if (layout === 'standard-text') {
      const detailCount = slideRoot.find('.text-details .list-item').length;
      const supportCount = slideRoot.find('.bullet-example, .bullet-takeaway, .card-example, .card-question').length;
      if (slideRoot.find('.quote-box').length > 0 && detailCount <= 3 && supportCount === 0) {
        pushSparseRiskWarning(
          warnings,
          index + 1,
          slideHtml,
          'standard_text 仅承载 quote 与少量解释，存在大面积留白风险。'
        );
      }
      return;
    }

    if (layout === 'standard-text-comparison') {
      const comparisonCards = slideRoot.find('.comparison-card').length;
      const comparisonRows = slideRoot.find('.comparison-row').length;
      const detailCount = slideRoot.find('.comparison-details .list-item').length;
      if (comparisonCards === 2 && comparisonRows <= 1 && detailCount <= 4) {
        pushSparseRiskWarning(
          warnings,
          index + 1,
          slideHtml,
          'standard_text_comparison 只有两块短对照，存在大面板留白风险。'
        );
      }
      return;
    }

    if (layout === 'standard-text-process') {
      const shortTrackSteps = slideRoot.find('.process-track .process-step').length;
      const supportBlocks = slideRoot.find(
        '.quote-box, .text-details, .process-list, .process-summary-bar, .process-detail-grid'
      ).length;
      if (shortTrackSteps > 0 && shortTrackSteps <= 3 && supportBlocks <= 1) {
        pushSparseRiskWarning(
          warnings,
          index + 1,
          slideHtml,
          'standard_text_process_track 只呈现短流程节点，存在横向流程过空风险。'
        );
      }
      return;
    }

    if (layout === 'card-layout') {
      const cardCount = slideRoot.find('.cards-grid > .surface-card').length;
      const exampleCount = slideRoot.find('.card-example, .card-question').length;
      if (cardCount === 3 && exampleCount === 0) {
        pushSparseRiskWarning(
          warnings,
          index + 1,
          slideHtml,
          'card_layout 缺少 example 或 question 的第二层信息，存在海报式留白风险。'
        );
      }
      return;
    }

    if (layout === 'thesis-evidence-grid') {
      const cardCount = slideRoot.find('.evidence-card').length;
      const noteCount = slideRoot.find('.evidence-card-note').length;
      if (cardCount < 3 || noteCount === 0) {
        pushSparseRiskWarning(
          warnings,
          index + 1,
          slideHtml,
          'thesis_evidence_grid 缺少完整证据卡支撑，存在论证结构过空风险。'
        );
      }
    }
  });
}

function hasRequiredSlotContent($, nodes, selector) {
  if (VISUAL_SLOT_SELECTORS.has(selector)) {
    return nodes
      .toArray()
      .every((node) => hasMediaContent($, node) || hasVisibleText($, node));
  }

  return nodes.toArray().every((node) => hasVisibleText($, node));
}

function addRequiredSlotWarnings({ warnings, htmlSlides }) {
  htmlSlides.forEach((slideHtml, index) => {
    const layout = inferLayout(slideHtml);
    const requiredSelectors = REQUIRED_SLOT_SELECTORS[layout];
    if (!requiredSelectors) {
      return;
    }

    const $ = cheerio.load(slideHtml, { decodeEntities: false });
    const slideRoot = $('.slide').first();
    for (const selector of requiredSelectors) {
      const nodes = slideRoot.find(selector);
      if (nodes.length > 0 && hasRequiredSlotContent($, nodes, selector)) {
        continue;
      }

      warnings.push({
        code: 'REQUIRED_SLOT_EMPTY',
        slide_index: index + 1,
        title: inferTitle(slideHtml) || '',
        message: `优先级版式缺少必要教学槽位或槽位为空：${selector}`,
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
  addContentDensityWarnings({ warnings, parsedSlides: parsed.slides, htmlSlides });
  addSparseRiskWarnings({ warnings, parsedSlides: parsed.slides, htmlSlides });
  addRequiredSlotWarnings({ warnings, htmlSlides });

  return {
    slide_count: htmlSlides.length,
    warning_count: warnings.length,
    warnings,
  };
}

function mergeQualityReports(primary, secondary) {
  const warnings = [...(primary?.warnings || []), ...(secondary?.warnings || [])];
  return {
    slide_count: primary?.slide_count || secondary?.slide_count || 0,
    warning_count: warnings.length,
    warnings,
  };
}

module.exports = {
  buildLayoutQualityReport,
  mergeQualityReports,
};
