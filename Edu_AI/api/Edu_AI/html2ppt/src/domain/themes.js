const fs = require('fs');
const path = require('path');
const { repoRoot, defaultThemeId } = require('../config');
const { AppError } = require('./errors');

const themeRegistry = {
  heu_academic_elegant: {
    id: 'heu_academic_elegant',
    cssFile: 'theme-heu-academic-elegant.css',
  },
  heu_academic_basic: {
    id: 'heu_academic_basic',
    cssFile: 'theme-heu-academic-basic.css',
  },
};

const brandConfigPath = path.join(repoRoot, 'style', 'theme-brand-config.json');
let cachedBrandConfig = null;

function loadBrandConfig() {
  if (!cachedBrandConfig) {
    cachedBrandConfig = JSON.parse(fs.readFileSync(brandConfigPath, 'utf8'));
  }
  return cachedBrandConfig;
}

function getTheme(themeId = defaultThemeId) {
  const theme = themeRegistry[themeId];
  if (!theme) {
    throw new AppError('UNSUPPORTED_THEME_ID', `Unsupported theme_id: ${themeId}`, 400);
  }
  return theme;
}

function resolveThemeCss(themeId) {
  const theme = getTheme(themeId);
  return path.join(repoRoot, 'style', theme.cssFile);
}

function getBrandForTheme(themeId) {
  const theme = getTheme(themeId);
  const config = loadBrandConfig();
  return config.themes[theme.cssFile] || config.default || { brand: { enabled: false } };
}

function listThemeIds() {
  return Object.keys(themeRegistry);
}

module.exports = {
  brandConfigPath,
  getBrandForTheme,
  getTheme,
  listThemeIds,
  resolveThemeCss,
};
