const fs = require('fs/promises');
const path = require('path');
const { repoRoot } = require('../config');
const { getComponent, getLayout, listLayoutKeys, loadCatalogBundle } = require('./catalogs');
const { resolveThemeCss } = require('./themes');

const brandConfigPath = path.join(repoRoot, 'style', 'theme-brand-config.json');
const themeStyleSummary = {
  heu_academic_elegant: 'academic blue-white, compact content rhythm, strong title hierarchy',
  heu_academic_basic: 'academic blue-white, conservative spacing, clean chrome',
};

function summarizeList(items, count = 3) {
  return (Array.isArray(items) ? items : []).slice(0, count).join(' / ') || 'none';
}

function formatUnits(entry) {
  if (!entry || entry.min_content_units == null || entry.max_content_units == null) {
    return 'n/a';
  }
  return `${entry.min_content_units}-${entry.max_content_units}`;
}

async function readBrandSummary(themeId) {
  const source = await fs.readFile(brandConfigPath, 'utf8');
  const config = JSON.parse(source);
  const themeFileName = path.basename(resolveThemeCss(themeId));
  const themeBrand = config?.themes?.[themeFileName]?.brand || config?.default?.brand || {};

  if (!themeBrand.enabled) {
    return 'disabled';
  }

  const position = themeBrand.position || 'default';
  return `${position} ${themeBrand.alt || 'brand'}${position === 'top-right' ? '; omit on thanks' : ''}`;
}

async function buildPlannerDigest({
  themeId,
  layoutCatalogPath,
  componentCatalogPath,
} = {}) {
  const bundle = await loadCatalogBundle({
    layoutCatalogPath,
    componentCatalogPath,
  });
  const layoutLines = listLayoutKeys(bundle)
    .filter((layoutKey) => !getLayout(bundle, layoutKey)?.planner_hidden)
    .map((layoutKey) => {
      const entry = getLayout(bundle, layoutKey);
      return [
        `- ${layoutKey}`,
        `best=${summarizeList(entry?.best_for, 2)}`,
        `units=${formatUnits(entry)}`,
        `fallback=${entry?.fallback_layout || 'none'}`,
        `components=${summarizeList(entry?.allowed_components, 4)}`,
      ].join(' | ');
    });
  const componentLines = Object.keys(bundle?.components?.components || {}).map((componentKey) => {
    const entry = getComponent(bundle, componentKey);
    return [
      `- ${componentKey}`,
      `best=${summarizeList(entry?.best_for, 2)}`,
      `units=${formatUnits(entry)}`,
      `fallback=${entry?.fallback_layout || 'none'}`,
    ].join(' | ');
  });

  return [
    '# Planner Digest',
    `Theme: ${themeId}`,
    `Style: ${themeStyleSummary[themeId] || 'academic presentation style'}`,
    `Brand: ${await readBrandSummary(themeId)}`,
    '',
    'Global Routing',
    '- standard_text only for 2-3 short bullets; 4+ long bullets should use denser fallback.',
    '- content_blank should combine registered components; avoid a lone bullet_list shell.',
    '- prefer fallback over sparse variety when a page would look empty or generic.',
    '',
    'Layouts',
    ...layoutLines,
    '',
    'Components',
    ...componentLines,
    '',
  ].join('\n');
}

module.exports = {
  buildPlannerDigest,
};
