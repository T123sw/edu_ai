const fs = require('fs');
const path = require('path');
const { repoRoot } = require('../config');
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
  const fragment = extractBodyFragment(rawInput);
  if (!fragment) {
    throw new Error('Input fragment is empty after normalization.');
  }
  if (!hasSlideClass(fragment)) {
    throw new Error('Input fragment does not contain any .slide elements.');
  }

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
  extractBodyFragment,
  hasSlideClass,
  inferTitle,
  resolveThemeCss,
  stripCodeFences,
};
