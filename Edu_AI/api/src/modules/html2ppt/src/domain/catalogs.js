const fs = require('fs/promises');
const path = require('path');
const { repoRoot } = require('../config');

const defaultLayoutCatalogPath = path.join(repoRoot, 'references', 'layout-catalog.json');
const defaultComponentCatalogPath = path.join(repoRoot, 'references', 'component-catalog.json');

async function loadJsonCatalog(catalogPath, collectionName) {
  const source = await fs.readFile(catalogPath, 'utf8');
  const catalog = JSON.parse(source);

  if (!catalog || typeof catalog !== 'object' || Array.isArray(catalog)) {
    throw new Error(`Catalog ${collectionName} must be a JSON object.`);
  }

  if (!catalog.version) {
    throw new Error(`Catalog ${collectionName} must declare a version.`);
  }

  if (!catalog[collectionName] || typeof catalog[collectionName] !== 'object' || Array.isArray(catalog[collectionName])) {
    throw new Error(`Catalog ${collectionName} must contain an object property named ${collectionName}.`);
  }

  return catalog;
}

async function loadCatalogBundle({
  layoutCatalogPath = defaultLayoutCatalogPath,
  componentCatalogPath = defaultComponentCatalogPath,
} = {}) {
  const [layouts, components] = await Promise.all([
    loadJsonCatalog(layoutCatalogPath, 'layouts'),
    loadJsonCatalog(componentCatalogPath, 'components'),
  ]);

  return {
    paths: {
      layoutCatalogPath,
      componentCatalogPath,
    },
    layouts,
    components,
  };
}

function getLayout(bundle, layoutKey) {
  return bundle?.layouts?.layouts?.[layoutKey] || null;
}

function getComponent(bundle, componentKey) {
  return bundle?.components?.components?.[componentKey] || null;
}

function listLayoutKeys(bundle) {
  return Object.keys(bundle?.layouts?.layouts || {});
}

function pickSummaryFields(entry) {
  if (!entry) return null;
  return {
    source: entry.source,
    teaching_recipe: entry.teaching_recipe || '',
    content_slots: entry.content_slots || [],
    min_content_units: entry.min_content_units || null,
    max_content_units: entry.max_content_units || null,
    chart_affordances: entry.chart_affordances || [],
    fallback_layout: entry.fallback_layout || '',
    hard_constraints: entry.hard_constraints || [],
  };
}

function summarizeCatalogEntries(bundle, { layouts = [], components = [] } = {}) {
  const payload = {
    layouts: Object.fromEntries(
      layouts
        .map((key) => [key, pickSummaryFields(getLayout(bundle, key))])
        .filter(([, value]) => value)
    ),
    components: Object.fromEntries(
      components
        .map((key) => [key, pickSummaryFields(getComponent(bundle, key))])
        .filter(([, value]) => value)
    ),
  };

  return JSON.stringify(payload, null, 2);
}

module.exports = {
  defaultComponentCatalogPath,
  defaultLayoutCatalogPath,
  getComponent,
  getLayout,
  listLayoutKeys,
  loadCatalogBundle,
  loadJsonCatalog,
  summarizeCatalogEntries,
};
