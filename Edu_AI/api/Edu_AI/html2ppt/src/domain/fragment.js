const cheerio = require('cheerio');
const { extractBodyFragment, stripCodeFences, collapseWhitespace } = require('../lib/build-standalone-html');
const { AppError } = require('./errors');

function loadRoot(html) {
  const normalized = extractBodyFragment(stripCodeFences(String(html || '')));
  const $ = cheerio.load(`<div id="__root__">${normalized}</div>`, {
    decodeEntities: false,
    xmlMode: false,
  });
  return { $, root: $('#__root__'), normalized };
}

function serializeChildren(root, $) {
  return root
    .children()
    .toArray()
    .map((element) => $.html(element))
    .join('\n\n')
    .trim();
}

function extractSlides(html) {
  const { $, root } = loadRoot(html);
  return root
    .children('.slide')
    .toArray()
    .map((element) => $.html(element));
}

function expectSingleSlide(html) {
  const slides = extractSlides(html);
  if (slides.length !== 1) {
    throw new AppError(
      'INVALID_REQUEST',
      `Expected exactly one slide fragment, but found ${slides.length}.`,
      400
    );
  }
  return slides[0];
}

function replaceSlide(html, slideIndex, replacementHtml) {
  const { $, root } = loadRoot(html);
  const slides = root.children('.slide');
  const zeroBasedIndex = Number(slideIndex) - 1;
  if (!Number.isInteger(zeroBasedIndex) || zeroBasedIndex < 0 || zeroBasedIndex >= slides.length) {
    throw new AppError('INVALID_TARGET_SLIDES', `Invalid slide index: ${slideIndex}`, 400);
  }

  const replacement = expectSingleSlide(replacementHtml);
  slides.eq(zeroBasedIndex).replaceWith(replacement);
  return serializeChildren(root, $);
}

function inferLayout(slideHtml) {
  const { $, root } = loadRoot(slideHtml);
  const slide = root.children('.slide').first();
  const classAttr = slide.attr('class') || '';
  const classes = new Set(classAttr.split(/\s+/).filter(Boolean));

  if (classes.has('layout-cover')) return 'cover';
  if (classes.has('layout-toc')) return 'toc';
  if (classes.has('layout-section-break')) return 'section';
  if (classes.has('layout-standard-text')) return 'standard-text';
  if (classes.has('layout-standard-text-dual-panel')) return 'standard-text-dual-panel';
  if (classes.has('layout-standard-text-sidebar')) return 'standard-text-sidebar';
  if (classes.has('layout-standard-text-structured')) return 'standard-text-structured';
  if (classes.has('layout-standard-text-comparison')) return 'standard-text-comparison';
  if (classes.has('layout-standard-text-process')) return 'standard-text-process';
  if (classes.has('layout-comparison-vs-panels')) return 'comparison-vs-panels';
  if (classes.has('layout-execution-pipeline')) return 'execution-pipeline';
  if (classes.has('layout-pillar-cards-banner')) return 'pillar-cards-banner';
  if (classes.has('layout-capability-map-grid')) return 'capability-map-grid';
  if (classes.has('layout-image-text')) return 'media-left-text-right';
  if (classes.has('layout-text-media')) return 'text-left-media-right';
  if (classes.has('layout-media-focus')) return 'media-focus';
  if (classes.has('layout-thanks')) return 'thanks';
  if (slide.find('.cards-grid').length > 0) return 'card-layout';

  return 'unknown';
}

function inferTitle(slideHtml) {
  const { $, root } = loadRoot(slideHtml);
  const slide = root.children('.slide').first();
  const candidates = [
    '.title-main',
    '.toc-title-zh',
    '.card-title',
    '.section-number',
  ];

  for (const selector of candidates) {
    const text = collapseWhitespace(slide.find(selector).first().text());
    if (text) {
      return text;
    }
  }

  return 'Untitled';
}

module.exports = {
  expectSingleSlide,
  extractSlides,
  inferLayout,
  inferTitle,
  loadRoot,
  replaceSlide,
};
