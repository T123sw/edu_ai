const { AppError } = require('./errors');
const { extractSlides } = require('./fragment');
const { buildLayoutQualityReport } = require('./layout-quality');
const { buildManifest } = require('./manifest');
const { normalizeSlideDecorations } = require('./slide-decor');

function buildEmptyQualityReport(slideCount) {
  return {
    slide_count: slideCount,
    warning_count: 0,
    warnings: [],
  };
}

function runPostProcessingChain({
  jobId,
  revisionId,
  themeId,
  fragmentHtml,
  contentMarkdown = '',
}) {
  const normalizedFragmentHtml = normalizeSlideDecorations(fragmentHtml, themeId);
  const slides = extractSlides(normalizedFragmentHtml);

  if (slides.length === 0) {
    throw new AppError('AGENT_GENERATION_FAILED', 'Agent did not produce any .slide elements.', 500);
  }

  const manifest = buildManifest({
    jobId,
    revisionId,
    themeId,
    fragmentHtml: normalizedFragmentHtml,
  });
  const qualityReport = String(contentMarkdown || '').trim()
    ? buildLayoutQualityReport({ contentMarkdown, fragmentHtml: normalizedFragmentHtml })
    : buildEmptyQualityReport(manifest.slide_count);

  return {
    fragmentHtml: `${normalizedFragmentHtml}\n`,
    manifest,
    qualityReport,
    slideCount: slides.length,
  };
}

module.exports = {
  runPostProcessingChain,
};
