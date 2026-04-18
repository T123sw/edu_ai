const cheerio = require('cheerio');

const GENERATED_DECOR_SELECTORS = [
  '.slide-safe-decor',
  '.thanks-safe-decor',
  '.thanks-orbit',
  '.thanks-accent-line',
].join(',');

function appendPptSafeChild($, parent, className) {
  parent.append(`<div class="${className}" aria-hidden="true"></div>`);
}

function buildStandardDecor($, slide) {
  const decor = $('<div class="slide-safe-decor" aria-hidden="true"></div>');
  appendPptSafeChild($, decor, 'slide-top-rule');
  appendPptSafeChild($, decor, 'slide-header-hairline');
  appendPptSafeChild($, decor, 'slide-header-mark slide-header-mark-left');
  appendPptSafeChild($, decor, 'slide-header-mark slide-header-mark-accent');

  if (slide.hasClass('layout-cover')) {
    appendPptSafeChild($, decor, 'slide-bottom-rule slide-bottom-rule-cover');
  } else {
    appendPptSafeChild($, decor, 'content-safe-accent');
  }

  return decor;
}

function buildThanksDecor($) {
  const decor = $('<div class="thanks-safe-decor" aria-hidden="true"></div>');
  appendPptSafeChild($, decor, 'thanks-safe-line thanks-safe-line-bottom');
  appendPptSafeChild($, decor, 'thanks-safe-line thanks-safe-line-accent');
  return decor;
}

function normalizeCoverSubtitleAccent($, slide) {
  slide.find('.cover-subtitle').each((_, element) => {
    const subtitle = $(element);
    subtitle.children('.cover-subtitle-accent').remove();
    subtitle.prepend('<div class="cover-subtitle-accent" aria-hidden="true"></div>');
  });
}

function normalizeSlideDecorations(fragmentHtml) {
  const $ = cheerio.load(`<div id="__root__">${String(fragmentHtml || '').trim()}</div>`, {
    decodeEntities: false,
    xmlMode: false,
  });
  const root = $('#__root__');

  root.children('.slide').each((_, element) => {
    const slide = $(element);
    slide.children(GENERATED_DECOR_SELECTORS).remove();
    normalizeCoverSubtitleAccent($, slide);

    if (slide.hasClass('layout-thanks')) {
      slide.children('.slide-brand,.footer-area').remove();
      slide.prepend(buildThanksDecor($));
      return;
    }

    slide.prepend(buildStandardDecor($, slide));
  });

  return root
    .children()
    .toArray()
    .map((element) => $.html(element))
    .join('\n\n')
    .trim();
}

module.exports = {
  normalizeSlideDecorations,
};
