const { extractSlides, inferLayout, inferTitle } = require('./fragment');

function buildManifest({ jobId, revisionId, themeId, fragmentHtml }) {
  const slides = extractSlides(fragmentHtml);

  return {
    job_id: jobId,
    revision_id: revisionId,
    theme_id: themeId,
    slide_count: slides.length,
    slides: slides.map((slideHtml, index) => ({
      slide_index: index + 1,
      title: inferTitle(slideHtml),
      layout: inferLayout(slideHtml),
    })),
  };
}

module.exports = {
  buildManifest,
};
