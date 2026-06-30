const fs = require('fs');
const path = require('path');
const { repoRoot } = require('../config');
const { normalizeSlideDecorations } = require('../domain/slide-decor');
const { resolveThemeCss } = require('../domain/themes');

const defaultLayoutCssPath = path.join(repoRoot, 'format', 'layout.css');

function ensureFileExists(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`${label} not found: ${filePath}`);
  }
}

function stripCodeFences(source) {
  const trimmed = String(source || '').trim();
  const fenced = trimmed.match(/^```(?:html)?\s*([\s\S]*?)\s*```$/i);
  return fenced ? fenced[1].trim() : source;
}

function extractBodyFragment(inputHtml) {
  const source = stripCodeFences(inputHtml).trim();
  const bodyMatch = source.match(/<body\b[^>]*>([\s\S]*?)<\/body>/i);
  if (bodyMatch) {
    return bodyMatch[1].trim();
  }
  if (/<html\b/i.test(source)) {
    throw new Error('Input looks like a full HTML document but no <body>...</body> block was found.');
  }
  return source;
}

function hasSlideClass(html) {
  return /class\s*=\s*["'][^"']*\bslide\b[^"']*["']/i.test(html);
}

function stripTags(value) {
  return String(value || '').replace(/<[^>]+>/g, ' ');
}

function collapseWhitespace(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function inferTitle(fragment, fallbackTitle) {
  if (fallbackTitle) {
    return fallbackTitle;
  }

  const titleMainMatch = fragment.match(/<div\s+class=["'][^"']*\btitle-main\b[^"']*["']>([\s\S]*?)<\/div>/i);
  if (titleMainMatch) {
    return collapseWhitespace(stripTags(titleMainMatch[1])) || 'Slides';
  }

  return 'Slides';
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function buildPreviewRuntimeBridgeScript() {
  return [
    '<script>',
    '(function () {',
    '  let previewSingleSlideMode = false;',
    '',
    '  function getSlides() {',
    "    return Array.from(document.querySelectorAll('.slide'));",
    '  }',
    '',
    '  function clampSlideIndex(slideIndex, slides) {',
    '    if (!slides.length) return 1;',
    '    if (!Number.isFinite(slideIndex)) return 1;',
    '    return Math.min(slides.length, Math.max(1, Math.round(slideIndex)));',
    '  }',
    '',
    '  function syncAddressBar(safeSlideIndex) {',
    '    try {',
    '      const nextUrl = new URL(window.location.href);',
    "      nextUrl.searchParams.set('slide', String(safeSlideIndex));",
    "      nextUrl.searchParams.set('page', String(safeSlideIndex));",
    "      nextUrl.hash = 'slide-' + safeSlideIndex;",
    '      window.history.replaceState(null, "", nextUrl);',
    '    } catch {}',
    '  }',
    '',
    '  function renderSingleSlide(slides, safeSlideIndex) {',
    "    document.documentElement.style.overflow = 'hidden';",
    "    document.body.style.overflow = 'hidden';",
    '    slides.forEach((slide, index) => {',
    "      slide.style.display = index === safeSlideIndex - 1 ? 'flex' : 'none';",
    "      slide.dataset.previewActive = index === safeSlideIndex - 1 ? 'true' : 'false';",
    '    });',
    '  }',
    '',
    '  function scrollToSlide(slideIndex) {',
    '    const slides = getSlides();',
    '    const safeSlideIndex = clampSlideIndex(slideIndex, slides);',
    '    const targetSlide = slides[safeSlideIndex - 1];',
    '    const singleSlidePreviewMode = previewSingleSlideMode;',
    '    if (!targetSlide) return;',
    '    if (!singleSlidePreviewMode) {',
    "      targetSlide.scrollIntoView({ block: 'start', inline: 'nearest' });",
    '      window.scrollTo({ top: targetSlide.offsetTop, left: targetSlide.offsetLeft });',
    '    } else {',
    '      renderSingleSlide(slides, safeSlideIndex);',
    '      window.scrollTo({ top: 0, left: 0 });',
    '    }',
    '    syncAddressBar(safeSlideIndex);',
    '  }',
    '',
    '  function readInitialSlideIndex() {',
    '    try {',
    '      const searchParams = new URLSearchParams(window.location.search);',
    "      const singleSlidePreviewMode = searchParams.get('preview_mode') === 'single-slide';",
    '      previewSingleSlideMode = singleSlidePreviewMode;',
    "      const rawSlideIndex = searchParams.get('slide') || searchParams.get('page') || window.location.hash.replace(/^#slide-/, '');",
    '      return Number.parseInt(String(rawSlideIndex || 1), 10) || 1;',
    '    } catch {',
    '      return 1;',
    '    }',
    '  }',
    '',
    '  function handlePreviewMessage(event) {',
    '    const data = event.data || {};',
    "    if (data.type !== 'ppt-preview-go-to-slide') return;",
    '    const requestedSlideIndex = Number.parseInt(String(data.slideIndex || 1), 10);',
    '    scrollToSlide(requestedSlideIndex);',
    '  }',
    '',
    "  window.addEventListener('message', handlePreviewMessage);",
    '',
    '  function announceReady() {',
    '    if (window.parent === window) return;',
    '    try {',
    "      window.parent.postMessage({ type: 'ppt-preview-ready' }, '*');",
    '    } catch {}',
    '  }',
    '',
    '  function initializePreviewBridge() {',
    '    scrollToSlide(readInitialSlideIndex());',
    '    announceReady();',
    '  }',
    '',
    "  if (document.readyState === 'complete') {",
    '    initializePreviewBridge();',
    '  } else {',
    "    window.addEventListener('load', initializePreviewBridge, { once: true });",
    '  }',
    '})();',
    '</script>',
  ].join('\n');
}

function ensurePreviewRuntimeBridge(html) {
  const source = String(html || '');
  if (!source.trim()) {
    return source;
  }
  const upgradedSource = source.replace(
    /<script\b[^>]*>[\s\S]*?(?:ppt-preview-go-to-slide|ppt-preview-ready)[\s\S]*?<\/script>/gi,
    ''
  );
  if (/<\/body>/i.test(upgradedSource)) {
    return upgradedSource.replace(/<\/body>/i, `${buildPreviewRuntimeBridgeScript()}\n</body>`);
  }
  return `${upgradedSource}\n${buildPreviewRuntimeBridgeScript()}`;
}

function buildStandaloneHtml({ title, layoutCss, themeCss, fragment }) {
  return [
    '<!DOCTYPE html>',
    '<html lang="zh-CN">',
    '<head>',
    '  <meta charset="UTF-8">',
    '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
    `  <title>${escapeHtml(title)}</title>`,
    '  <style>',
    '/* format/layout.css */',
    layoutCss.trim(),
    '',
    '/* style/theme.css */',
    themeCss.trim(),
    '  </style>',
    '</head>',
    '<body>',
    fragment.trim(),
    buildPreviewRuntimeBridgeScript(),
    '</body>',
    '</html>',
    '',
  ].join('\n');
}

function buildOutputPath(inputPath, explicitOutput) {
  if (explicitOutput) {
    return path.resolve(explicitOutput);
  }

  const inputDir = path.dirname(inputPath);
  const ext = path.extname(inputPath);
  const base = path.basename(inputPath, ext);
  const normalizedBase = base
    .replace(/[-_.]fragment$/i, '')
    .replace(/[-_.]slides$/i, '')
    .replace(/[-_.]body$/i, '');

  return path.join(inputDir, `${normalizedBase}.html`);
}

function buildStandaloneHtmlFromFragment({ fragmentPath, outputPath, title, themeId }) {
  const resolvedFragmentPath = path.resolve(fragmentPath);
  const resolvedOutputPath = buildOutputPath(resolvedFragmentPath, outputPath);
  const themeCssPath = resolveThemeCss(themeId);

  ensureFileExists(resolvedFragmentPath, 'Input fragment');
  ensureFileExists(defaultLayoutCssPath, 'Layout CSS');
  ensureFileExists(themeCssPath, 'Theme CSS');

  const rawInput = fs.readFileSync(resolvedFragmentPath, 'utf8');
  const fragment = normalizeSlideDecorations(extractBodyFragment(rawInput), themeId);
  if (!fragment) {
    throw new Error('Input fragment is empty after normalization.');
  }
  if (!hasSlideClass(fragment)) {
    throw new Error('Input fragment does not contain any .slide elements.');
  }

  fs.writeFileSync(resolvedFragmentPath, `${fragment}\n`, 'utf8');

  const layoutCss = fs.readFileSync(defaultLayoutCssPath, 'utf8');
  const themeCss = fs.readFileSync(themeCssPath, 'utf8');
  const documentTitle = inferTitle(fragment, title);
  const standaloneHtml = buildStandaloneHtml({
    title: documentTitle,
    layoutCss,
    themeCss,
    fragment,
  });

  fs.mkdirSync(path.dirname(resolvedOutputPath), { recursive: true });
  fs.writeFileSync(resolvedOutputPath, standaloneHtml, 'utf8');

  return {
    fragmentPath: resolvedFragmentPath,
    outputPath: resolvedOutputPath,
    themeCssPath,
    title: documentTitle,
    fragment,
  };
}

module.exports = {
  buildOutputPath,
  buildStandaloneHtml,
  buildStandaloneHtmlFromFragment,
  collapseWhitespace,
  ensurePreviewRuntimeBridge,
  extractBodyFragment,
  hasSlideClass,
  inferTitle,
  resolveThemeCss,
  stripCodeFences,
};
