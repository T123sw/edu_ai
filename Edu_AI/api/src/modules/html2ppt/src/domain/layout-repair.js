const cheerio = require('cheerio');

const REPAIRABLE_CODES = new Set(['KEY_CONTAINER_OVERFLOW', 'ELEMENT_OUTSIDE_SLIDE', 'ELEMENT_OVERLAP']);

function collapseWhitespace(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function collectRepairTargets(geometryReport) {
  const targets = new Set();

  for (const warning of geometryReport?.warnings || []) {
    if (REPAIRABLE_CODES.has(warning?.code)) {
      targets.add(Number(warning.slide_index));
    }
  }

  return targets;
}

function replaceSummaryText($, summaryBar, nextText) {
  let copy = summaryBar.children('.summary-copy').first();
  if (!copy.length) {
    copy = $('<div class="summary-copy"></div>');
    summaryBar.append(copy);
  }

  copy.empty().text(nextText);
}

function shortenComparisonSummary($, slide) {
  const summaryBar = slide.find('.comparison-summary-bar').first();
  if (!summaryBar.length) {
    return false;
  }

  const currentText = collapseWhitespace(summaryBar.text());
  if (currentText.length <= 60) {
    return false;
  }

  const titles = slide
    .find('.comparison-card .card-title')
    .slice(0, 2)
    .toArray()
    .map((node) => collapseWhitespace($(node).text()))
    .filter(Boolean);
  const subtitles = slide
    .find('.comparison-card .card-subtitle')
    .slice(0, 2)
    .toArray()
    .map((node) => collapseWhitespace($(node).text()));

  if (titles.length !== 2) {
    return false;
  }

  const normalizeSubtitle = (value, fallback) => {
    const subtitle = String(value || '').trim();
    if (!subtitle) {
      return fallback;
    }
    return /^(强调|聚焦|侧重)/.test(subtitle) ? subtitle : `强调${subtitle}`;
  };
  const nextText = `${titles[0]}${normalizeSubtitle(subtitles[0], '强调快速集成')}；${titles[1]}${normalizeSubtitle(
    subtitles[1],
    '强调底层统一'
  )}。`;
  replaceSummaryText($, summaryBar, nextText);
  return true;
}

function trimProcessMeta($, slide) {
  const meta = slide.find('.process-summary-meta').first();
  if (!meta.length) {
    return false;
  }

  const currentText = collapseWhitespace(meta.text());
  if (currentText.length <= 96) {
    return false;
  }

  meta.text(`${currentText.slice(0, 92)}...`);
  return true;
}

function collapseThesisCardHeaders($, slide) {
  let changed = false;

  slide.find('.evidence-card').each((_, element) => {
    const card = $(element);
    if (card.children('.evidence-card-head').length > 0) {
      return;
    }

    const indexNode = card.children('.process-index, .evidence-card-index').first();
    const titleNode = card.children('.card-title, .evidence-card-title').first();
    if (!indexNode.length || !titleNode.length) {
      return;
    }

    const header = $('<div class="evidence-card-head"></div>');
    indexNode.before(header);
    header.append(indexNode);
    header.append(titleNode);
    changed = true;
  });

  return changed;
}

function addCompactClasses(slide, classes) {
  const additions = String(classes || '')
    .split(/\s+/)
    .map((value) => value.trim())
    .filter(Boolean)
    .filter((value) => !slide.hasClass(value));

  if (additions.length === 0) {
    return false;
  }

  slide.addClass(additions.join(' '));
  return true;
}

function repairOverflowLayouts(fragmentHtml, geometryReport) {
  const targets = collectRepairTargets(geometryReport);
  if (targets.size === 0) {
    return {
      changed: false,
      fragmentHtml: String(fragmentHtml || '').trim(),
    };
  }

  const $ = cheerio.load(`<div id="__root__">${String(fragmentHtml || '').trim()}</div>`, {
    decodeEntities: false,
    xmlMode: false,
  });
  const root = $('#__root__');
  let changed = false;

  root.children('.slide').each((index, element) => {
    const slideIndex = index + 1;
    if (!targets.has(slideIndex)) {
      return;
    }

    const slide = $(element);
    const classAttr = slide.attr('class') || '';

    if (/\blayout-standard-text-comparison\b/.test(classAttr)) {
      changed = addCompactClasses(slide, 'layout-overflow-compact comparison-overflow-compact') || changed;
      if (shortenComparisonSummary($, slide)) {
        changed = true;
      }
      return;
    }

    if (/\blayout-standard-text-process\b/.test(classAttr)) {
      changed = addCompactClasses(slide, 'layout-overflow-compact process-overflow-compact') || changed;
      if (trimProcessMeta($, slide)) {
        changed = true;
      }
      return;
    }

    if (/\blayout-thesis-evidence-grid\b/.test(classAttr)) {
      changed = addCompactClasses(slide, 'layout-overflow-compact thesis-overflow-compact') || changed;
      if (collapseThesisCardHeaders($, slide)) {
        changed = true;
      }
      return;
    }

    if (/\blayout-architecture-pipeline-spotlight\b/.test(classAttr)) {
      changed = addCompactClasses(slide, 'layout-overflow-compact architecture-overflow-compact') || changed;
      return;
    }

    if (slide.find('.cards-grid').length > 0) {
      changed = addCompactClasses(slide, 'layout-overflow-compact card-layout-overflow-compact') || changed;
    }
  });

  return {
    changed,
    fragmentHtml: root
      .children()
      .toArray()
      .map((element) => $.html(element))
      .join('\n\n')
      .trim(),
  };
}

module.exports = {
  repairOverflowLayouts,
};
