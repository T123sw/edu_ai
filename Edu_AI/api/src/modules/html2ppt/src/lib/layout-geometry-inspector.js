const fs = require('fs/promises');
const path = require('path');
const { pathToFileURL } = require('url');
const { runChromeExport } = require('./export-html-to-pptx');

const GEOMETRY_SELECTORS = [
  '.content-area',
  '.text-details',
  '.text-density-grid',
  '.text-support-card',
  '.cards-lead',
  '.cards-grid',
  '.cards-summary-bar',
  '.comparison-summary-bar',
  '.comparison-grid',
  '.comparison-table',
  '.vs-comparison-grid',
  '.process-summary-bar',
  '.process-track',
  '.timeline',
  '.process-detail-grid',
  '.process-detail-card',
  '.pipeline-track',
  '.metric-strip',
  '.matrix-2x2',
  '.relationship-map',
  '.capability-map',
  '.capability-hero',
  '.capability-grid',
  '.media-focus-content-panel',
  '.thanks-content',
  '.footer-decoration',
];

function buildGeometryWarnings(rawReport) {
  const warnings = [];

  for (const slideResult of rawReport?.results || []) {
    for (const issue of slideResult?.issues || []) {
      warnings.push({
        code: issue.code,
        slide_index: slideResult.slide_index,
        title: slideResult.title || '',
        message: `${issue.selector || 'element'} geometry issue: ${issue.code}`,
        details: issue,
      });
    }
  }

  return {
    slide_count: rawReport?.slide_count || (rawReport?.results || []).length || 0,
    warning_count: warnings.length,
    warnings,
  };
}

function buildInspectorScript() {
  return `
  <script>
    (() => {
      const selectors = ${JSON.stringify(GEOMETRY_SELECTORS)};
      const tolerancePx = 2;
      const overflowSlackPx = 8;
      const overlapSlackPx = 4;

      function inferTitle(slide) {
        const titleNode = slide.querySelector('.title-main, .toc-title-zh, .toc-title-en, h1, h2, h3');
        return titleNode ? String(titleNode.textContent || '').trim() : '';
      }

      function rectsOverlap(a, b) {
        const horizontal = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const vertical = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        return horizontal > overlapSlackPx && vertical > overlapSlackPx;
      }

      function collectChildOverlapIssues(node, selector) {
        const children = Array.from(node.children || [])
          .map((child) => ({
            node: child,
            rect: child.getBoundingClientRect(),
          }))
          .filter(({ rect }) => rect.width > overlapSlackPx && rect.height > overlapSlackPx);
        const issues = [];

        for (let index = 0; index < children.length; index += 1) {
          for (let next = index + 1; next < children.length; next += 1) {
            const first = children[index];
            const second = children[next];
            if (!rectsOverlap(first.rect, second.rect)) {
              continue;
            }

            issues.push({
              code: 'ELEMENT_OVERLAP',
              selector,
              first: first.node.className || first.node.tagName || 'child',
              second: second.node.className || second.node.tagName || 'child',
              first_rect: {
                top: first.rect.top,
                left: first.rect.left,
                right: first.rect.right,
                bottom: first.rect.bottom,
              },
              second_rect: {
                top: second.rect.top,
                left: second.rect.left,
                right: second.rect.right,
                bottom: second.rect.bottom,
              },
            });
          }
        }

        return issues;
      }

      function collectIssues(slide) {
        const slideRect = slide.getBoundingClientRect();
        const issues = [];

        for (const selector of selectors) {
          for (const node of slide.querySelectorAll(selector)) {
            if (node.scrollHeight > node.clientHeight + overflowSlackPx) {
              issues.push({
                code: 'KEY_CONTAINER_OVERFLOW',
                selector,
                scrollHeight: node.scrollHeight,
                clientHeight: node.clientHeight,
              });
            }

            const rect = node.getBoundingClientRect();
            if (
              rect.top < slideRect.top - tolerancePx ||
              rect.left < slideRect.left - tolerancePx ||
              rect.right > slideRect.right + tolerancePx ||
              rect.bottom > slideRect.bottom + tolerancePx
            ) {
              issues.push({
                code: 'ELEMENT_OUTSIDE_SLIDE',
                selector,
                rect: {
                  top: rect.top,
                  left: rect.left,
                  right: rect.right,
                  bottom: rect.bottom,
                },
                slide_rect: {
                  top: slideRect.top,
                  left: slideRect.left,
                  right: slideRect.right,
                  bottom: slideRect.bottom,
                },
              });
            }

            issues.push(...collectChildOverlapIssues(node, selector));
          }
        }

        return issues;
      }

      const slides = Array.from(document.querySelectorAll('.slide'));
      const report = {
        slide_count: slides.length,
        results: slides.map((slide, index) => ({
          slide_index: index + 1,
          title: inferTitle(slide),
          issues: collectIssues(slide),
        })),
      };

      const existing = document.getElementById('layout-quality-json');
      if (existing) existing.remove();

      const script = document.createElement('script');
      script.type = 'application/json';
      script.id = 'layout-quality-json';
      script.textContent = JSON.stringify(report);
      document.body.appendChild(script);
    })();
  </script>`;
}

function injectInspector(html) {
  const inspectorScript = buildInspectorScript();
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${inspectorScript}\n</body>`);
  }
  return `${html}\n${inspectorScript}\n`;
}

function extractRawReport(domDump) {
  const match = String(domDump || '').match(
    /<script[^>]*type=["']application\/json["'][^>]*id=["']layout-quality-json["'][^>]*>([\s\S]*?)<\/script>/i
  );
  if (!match) {
    throw new Error('Chrome layout inspection did not emit layout-quality-json.');
  }
  return JSON.parse(match[1]);
}

async function inspectHtmlLayout(htmlPath, options = {}) {
  const inspectPath = path.join(path.dirname(htmlPath), `.__inspect__-${path.basename(htmlPath)}`);
  let sourceHtml = '<!DOCTYPE html><html><body></body></html>';

  try {
    sourceHtml = await fs.readFile(htmlPath, 'utf8');
  } catch (error) {
    if (error.code !== 'ENOENT') {
      throw error;
    }
  }

  await fs.writeFile(inspectPath, injectInspector(sourceHtml), 'utf8');

  try {
    const chromeResult = await runChromeExport(pathToFileURL(inspectPath).href, options);
    return buildGeometryWarnings(extractRawReport(chromeResult.stdout));
  } finally {
    await fs.unlink(inspectPath).catch(() => {});
  }
}

module.exports = {
  buildGeometryWarnings,
  inspectHtmlLayout,
};
