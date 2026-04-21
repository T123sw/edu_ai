const cheerio = require('cheerio');
const { getBrandForTheme } = require('./themes');

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

function buildBrandSlot($, brand) {
  const slotClass = brand.slotClass || 'slide-brand';
  const imageClass = brand.imageClass || 'slide-brand-image';
  const asset = brand.asset || '';
  const alt = brand.alt || '';
  return $(
    `<div class="${slotClass}"><img class="${imageClass}" src="${asset}" alt="${alt}"></div>`
  );
}

function normalizeBrandSlot($, slide, themeId) {
  slide.children('.slide-brand').remove();

  const brandConfig = getBrandForTheme(themeId);
  const brand = brandConfig?.brand;
  if (!brand?.enabled) {
    return;
  }

  slide.prepend(buildBrandSlot($, brand));
}

function normalizeCoverSubtitleAccent($, slide) {
  slide.find('.cover-subtitle').each((_, element) => {
    const subtitle = $(element);
    subtitle.children('.cover-subtitle-accent').remove();
    subtitle.prepend('<div class="cover-subtitle-accent" aria-hidden="true"></div>');
  });
}

function collapseText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function deriveThanksNotePrefix(titleText) {
  const raw = collapseText(titleText);
  if (!raw) {
    return '';
  }

  if (/总结/.test(raw)) {
    return '总结与答疑。';
  }

  if (/致谢|感谢/.test(raw)) {
    return '感谢聆听，欢迎提问。';
  }

  return /[。！？.!?]$/.test(raw) ? raw : `${raw}。`;
}

function normalizeThanksTitle($, slide) {
  const titleMain = slide.find('.title-main').first();
  if (!titleMain.length) {
    return;
  }

  const titleText = collapseText(titleMain.text());
  if (!/q\s*&\s*a/i.test(titleText) || /^q\s*&\s*a$/i.test(titleText)) {
    return;
  }

  const note = slide.find('.thanks-note').first();
  const summaryText = collapseText(
    titleText
      .replace(/q\s*&\s*a/gi, '')
      .replace(/thanks/gi, '')
      .replace(/[\/｜|·,:：\-–—]+/g, ' ')
  );
  const notePrefix = deriveThanksNotePrefix(summaryText);

  titleMain.text('Q&A');

  if (!note.length || !notePrefix) {
    return;
  }

  const currentNoteText = collapseText(note.text());
  if (currentNoteText.startsWith(notePrefix)) {
    return;
  }

  const currentHtml = note.html() || '';
  note.html(`${notePrefix}${currentHtml}`);
}

function setOrInsertTextNode($, container, selector, text, anchorSelector) {
  const existing = container.children(selector).first();
  if (existing.length) {
    if (!collapseText(existing.text())) {
      existing.text(text);
    }
    return existing;
  }

  const node = $(`<div class="${selector.replace(/^\./, '')}"></div>`);
  node.text(text);

  const anchor = anchorSelector ? container.children(anchorSelector).last() : null;
  if (anchor && anchor.length) {
    anchor.after(node);
    return node;
  }

  container.append(node);
  return node;
}

function normalizeCardLayoutTeachingSlots($, slide) {
  slide.find('.cards-grid > .surface-card').each((_, element) => {
    const card = $(element);
    card.children('.card-ghost-number').remove();
    const title = collapseText(card.children('.card-title').first().text()) || '该能力';
    const exampleText = `例子：把“${title}”当作一类可复用能力单元来理解。`;
    const questionText = '课堂追问：它解决的是“做什么”，还是“怎么接”？';

    const example = setOrInsertTextNode($, card, '.card-example', exampleText, '.card-desc');
    setOrInsertTextNode($, card, '.card-question', questionText, `.${example.attr('class') || 'card-example'}`);
  });
}

function normalizeSummaryStrip($, strip) {
  if (!strip.length) {
    return;
  }

  if (!strip.children('.summary-accent').length) {
    strip.prepend('<div class="summary-accent" aria-hidden="true"></div>');
  }

  let copy = strip.children('.summary-copy').first();
  if (!copy.length) {
    copy = $('<div class="summary-copy"></div>');
    const movable = strip
      .contents()
      .toArray()
      .filter((node) => !(node.type === 'tag' && $(node).hasClass('summary-accent')));
    movable.forEach((node) => copy.append(node));
    strip.append(copy);
  }
}

function normalizeComparisonTeachingSlots($, slide) {
  if (!slide.hasClass('layout-standard-text-comparison')) {
    return;
  }

  const contentArea = slide.children('.content-area').first();
  if (!contentArea.length) {
    return;
  }

  const comparisonGrid = contentArea.children('.comparison-grid').first();
  if (!comparisonGrid.length) {
    return;
  }

  let summaryBar = contentArea.children('.comparison-summary-bar').first();

  const cardTitles = slide
    .find('.comparison-card .card-title')
    .slice(0, 2)
    .toArray()
    .map((node) => collapseText($(node).text()))
    .filter(Boolean);
  const cardSubtitles = slide
    .find('.comparison-card .card-subtitle')
    .slice(0, 2)
    .toArray()
    .map((node) => collapseText($(node).text()));

  let summaryText = '对比页要先对齐比较维度，再看两侧差异和底部映射。';
  if (cardTitles.length === 2) {
    const leftSubtitle = cardSubtitles[0] ? `：${cardSubtitles[0]}` : '';
    const rightSubtitle = cardSubtitles[1] ? `：${cardSubtitles[1]}` : '';
    summaryText = `${cardTitles[0]}${leftSubtitle}；${cardTitles[1]}${rightSubtitle}。`;
  }

  if (!summaryBar.length) {
    summaryBar = $('<div class="comparison-summary-bar"></div>');
    comparisonGrid.before(summaryBar);
  }
  if (!collapseText(summaryBar.text())) {
    summaryBar.text(summaryText);
  }
  normalizeSummaryStrip($, summaryBar);

  const comparisonTable = comparisonGrid.find('> .comparison-table').first();
  if (comparisonTable.length && !comparisonTable.parent().hasClass('comparison-matrix-card')) {
    const matrixCard = $('<div class="surface-card comparison-matrix-card"></div>');
    comparisonTable.replaceWith(matrixCard);
    matrixCard.append(comparisonTable);
  }
}

function normalizeProcessSummaryStrips($, slide) {
  slide.find('.process-summary-bar').each((_, element) => {
    normalizeSummaryStrip($, $(element));
  });
}

function normalizeCardsLeadStrips($, slide) {
  slide.find('.cards-lead').each((_, element) => {
    normalizeSummaryStrip($, $(element));
  });
}

function normalizeCapabilityMapTeachingSlots($, slide) {
  const hero = slide.find('.capability-hero').first();
  if (!hero.length) {
    return;
  }

  const relationText = '模块关系：网格保证稳定，语义路由负责选版式，导出链路负责把 DOM 变成 PPTX。';
  const takeawayText = '落地结论：先让内容进入完整结构，再追求视觉变化。';

  const relation = setOrInsertTextNode($, hero, '.capability-relation', relationText, '.capability-hero-text');
  setOrInsertTextNode($, hero, '.capability-takeaway', takeawayText, `.${relation.attr('class') || 'capability-relation'}`);
}

function normalizeMediaFocusTeachingSlots($, slide) {
  const panel = slide.find('.media-focus-content-panel').first();
  if (!panel.length) {
    return;
  }

  let observationList = panel.children('.media-observation-list').first();
  if (!observationList.length) {
    observationList = $('<div class="media-observation-list"></div>');
    observationList.append('<div class="list-item">观察点：主体是否落在视觉中心。</div>');
    observationList.append('<div class="list-item">观察点：裁切后是否仍保留讲解重点。</div>');

    const details = panel.children('.text-details').last();
    if (details.length) {
      details.after(observationList);
    } else {
      const quote = panel.children('.quote-box').last();
      if (quote.length) {
        quote.after(observationList);
      } else {
        panel.append(observationList);
      }
    }
  } else if (!observationList.find('.list-item').filter((_, node) => collapseText($(node).text())).length) {
    observationList.append('<div class="list-item">观察点：主体是否落在视觉中心。</div>');
    observationList.append('<div class="list-item">观察点：裁切后是否仍保留讲解重点。</div>');
  }

  setOrInsertTextNode(
    $,
    panel,
    '.media-conclusion',
    '结论：媒体焦点页右侧只保留观察与提示，不再堆长段文字。',
    '.media-observation-list'
  );
}

function normalizeSlideDecorations(fragmentHtml, themeId) {
  const $ = cheerio.load(`<div id="__root__">${String(fragmentHtml || '').trim()}</div>`, {
    decodeEntities: false,
    xmlMode: false,
  });
  const root = $('#__root__');

  root.children('.slide').each((_, element) => {
    const slide = $(element);
    slide.children(GENERATED_DECOR_SELECTORS).remove();
    normalizeCoverSubtitleAccent($, slide);
    normalizeCardLayoutTeachingSlots($, slide);
    normalizeComparisonTeachingSlots($, slide);
    normalizeProcessSummaryStrips($, slide);
    normalizeCardsLeadStrips($, slide);
    normalizeCapabilityMapTeachingSlots($, slide);
    normalizeMediaFocusTeachingSlots($, slide);

    if (slide.hasClass('layout-thanks')) {
      slide.children('.slide-brand,.footer-area').remove();
      normalizeThanksTitle($, slide);
      slide.prepend(buildThanksDecor($));
      return;
    }

    normalizeBrandSlot($, slide, themeId);
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
