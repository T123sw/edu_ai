const fs = require('fs');
const http = require('http');
const path = require('path');
const { spawn } = require('child_process');
const { repoRoot, chromePath, chromeArgs } = require('../config');

const HOST = '127.0.0.1';

function ensureFileExists(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`${label} not found: ${filePath}`);
  }
}

function extractStatusMessage(domDump) {
  const match = String(domDump || '').match(/<div[^>]*id=["']status["'][^>]*>([\s\S]*?)<\/div>/i);
  if (!match) {
    return null;
  }
  return match[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() || null;
}

function writeDebugArtifacts(jobWorkspace, chromeResult) {
  if (!jobWorkspace) {
    return {};
  }

  const debugPaths = {
    dom: path.join(jobWorkspace, 'export-debug-dom.html'),
    log: path.join(jobWorkspace, 'export-debug-log.json'),
  };

  try {
    fs.writeFileSync(debugPaths.dom, chromeResult.stdout || '', 'utf8');
    fs.writeFileSync(
      debugPaths.log,
      JSON.stringify(
        {
          code: chromeResult.code,
          statusMessage: extractStatusMessage(chromeResult.stdout),
          stderr: chromeResult.stderr || '',
        },
        null,
        2
      ),
      'utf8'
    );
  } catch {
    return {};
  }

  return debugPaths;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function hasSlideClass(html) {
  return /class\s*=\s*["'][^"']*\bslide\b[^"']*["']/i.test(html);
}

function ensureSlideClass(html) {
  if (hasSlideClass(html)) {
    return { html, changed: false };
  }

  let changed = false;

  const addToSections = html.replace(/<section\b([^>]*)>/gi, (match, attrs) => {
    if (/\bclass\s*=/i.test(attrs)) {
      changed = true;
      return match.replace(/\bclass\s*=\s*(["'])([^"']*)(\1)/i, (m, quote, classes) => {
        return `class=${quote}${classes} slide${quote}`;
      });
    }

    changed = true;
    return `<section class="slide"${attrs}>`;
  });

  if (changed) {
    return { html: addToSections, changed: true };
  }

  const addToDeckChild = html.replace(
    /(<div\b[^>]*class\s*=\s*["'][^"']*\bdeck\b[^"']*["'][^>]*>\s*)(<([a-z0-9-]+)\b([^>]*)>)/i,
    (match, prefix, tagOpen, tagName, attrs) => {
      changed = true;
      if (/\bclass\s*=/i.test(attrs)) {
        return `${prefix}${tagOpen.replace(/\bclass\s*=\s*(["'])([^"']*)(\1)/i, (m, quote, classes) => {
          return `class=${quote}${classes} slide${quote}`;
        })}`;
      }
      return `${prefix}<${tagName} class="slide"${attrs}>`;
    }
  );

  if (changed) {
    return { html: addToDeckChild, changed: true };
  }

  throw new Error('No .slide element found, and no <section> or .deck child could be upgraded automatically.');
}

function ensureBodyDataFileName(html, pptxFileName) {
  let foundBody = false;
  let changed = false;

  const updated = html.replace(/<body\b([^>]*)>/i, (match, attrs) => {
    foundBody = true;
    if (/\bdata-pptx-file-name\s*=/i.test(attrs)) {
      return match;
    }

    changed = true;
    return `<body data-pptx-file-name="${pptxFileName}"${attrs}>`;
  });

  if (!foundBody) {
    throw new Error('Missing <body> tag.');
  }

  return { html: updated, changed };
}

function ensureStatusBanner(html) {
  if (/id\s*=\s*["']status["']/i.test(html)) {
    return { html, changed: false };
  }

  const banner =
    '<div id="status" style="position:fixed; left:16px; bottom:16px; z-index:9999; background:rgba(15,23,42,0.88); color:#fff; padding:8px 12px; border-radius:10px; font:14px/1.4 -apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;">Preparing export...</div>\n';

  const updated = html.replace(/<body\b[^>]*>/i, (match) => `${match}\n  ${banner}`);
  if (updated === html) {
    throw new Error('Unable to inject export status banner because <body> was not found.');
  }

  return { html: updated, changed: true };
}

function ensureScriptTag(html, src) {
  const quotedSrc = escapeRegExp(src);
  const pattern = new RegExp(`<script\\b[^>]*src\\s*=\\s*["']${quotedSrc}["'][^>]*><\\/script>`, 'i');
  if (pattern.test(html)) {
    return { html, changed: false };
  }

  const scriptTag = `  <script src="${src}"></script>\n`;
  const updated = html.replace(/<\/body>/i, `${scriptTag}</body>`);
  if (updated === html) {
    throw new Error(`Unable to inject script tag for ${src}; missing </body>.`);
  }

  return { html: updated, changed: true };
}

function normalizeRepoAssetPaths(html) {
  let changed = false;

  const attrNormalized = html.replace(
    /\b(src|href)=("|\')(?:file:\/\/)?[^"']*\/assets\/([^"']+)\2/gi,
    (match, attr, quote, assetPath) => {
      changed = true;
      return `${attr}=${quote}/assets/${assetPath}${quote}`;
    }
  );

  const urlNormalized = attrNormalized.replace(
    /url\((["']?)(?:file:\/\/)?[^)"']*\/assets\/([^)"']+)\1\)/gi,
    (match, quote, assetPath) => {
      changed = true;
      return `url(${quote}/assets/${assetPath}${quote})`;
    }
  );

  return { html: urlNormalized, changed };
}

function prepareHtml(htmlFilePath, pptxFileName) {
  const original = fs.readFileSync(htmlFilePath, 'utf8');
  let html = original;
  const changes = [];

  const slideResult = ensureSlideClass(html);
  html = slideResult.html;
  if (slideResult.changed) {
    changes.push('added .slide to export containers');
  }

  const bodyResult = ensureBodyDataFileName(html, pptxFileName);
  html = bodyResult.html;
  if (bodyResult.changed) {
    changes.push('added body data-pptx-file-name');
  }

  const statusResult = ensureStatusBanner(html);
  html = statusResult.html;
  if (statusResult.changed) {
    changes.push('added export status banner');
  }

  const bundleResult = ensureScriptTag(html, '/dom-to-pptx.bundle.js');
  html = bundleResult.html;
  if (bundleResult.changed) {
    changes.push('injected /dom-to-pptx.bundle.js');
  }

  const runnerResult = ensureScriptTag(html, '/runner.js');
  html = runnerResult.html;
  if (runnerResult.changed) {
    changes.push('injected /runner.js');
  }

  const assetResult = normalizeRepoAssetPaths(html);
  html = assetResult.html;
  if (assetResult.changed) {
    changes.push('normalized asset URLs');
  }

  if (html !== original) {
    fs.writeFileSync(htmlFilePath, html, 'utf8');
  }

  return { htmlFilePath, pptxFileName, changed: html !== original, changes };
}

function serveFile(filePath, res) {
  fs.readFile(filePath, (error, data) => {
    if (error) {
      res.writeHead(404, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ error: `Not found: ${filePath}` }));
      return;
    }

    const ext = path.extname(filePath);
    const types = {
      '.html': 'text/html; charset=utf-8',
      '.js': 'text/javascript; charset=utf-8',
      '.css': 'text/css; charset=utf-8',
      '.json': 'application/json; charset=utf-8',
      '.png': 'image/png',
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.svg': 'image/svg+xml',
      '.webp': 'image/webp',
      '.mp4': 'video/mp4',
      '.webm': 'video/webm',
      '.mov': 'video/quicktime',
    };

    res.writeHead(200, {
      'Content-Type': types[ext] || 'application/octet-stream',
      'Content-Length': data.length,
    });
    res.end(data);
  });
}

function createExportServer({ htmlRootDir, outputDir, port }) {
  const runnerPath = path.join(repoRoot, 'test-harness', 'runner.js');
  const bundlePath = path.join(repoRoot, 'test-harness', 'dom-to-pptx.bundle.js');
  const assetsDir = path.join(repoRoot, 'assets');

  ensureFileExists(runnerPath, 'runner.js');
  ensureFileExists(bundlePath, 'dom-to-pptx.bundle.js');
  ensureFileExists(assetsDir, 'assets directory');
  fs.mkdirSync(outputDir, { recursive: true });

  const server = http.createServer((req, res) => {
    if (!req.url) {
      res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ error: 'Missing URL' }));
      return;
    }

    const requestUrl = new URL(req.url, `http://${HOST}:${port}`);
    const pathname = decodeURIComponent(requestUrl.pathname);

    if (req.method === 'POST' && pathname === '/save-pptx') {
      const outputName = path.basename(requestUrl.searchParams.get('name') || 'deck.pptx');
      const outputFile = path.join(outputDir, outputName);
      const chunks = [];
      req.on('data', (chunk) => chunks.push(chunk));
      req.on('end', () => {
        const body = Buffer.concat(chunks);
        fs.writeFileSync(outputFile, body);
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: true, bytes: body.length, outputFile }));
      });
      req.on('error', (error) => {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ error: error.message }));
      });
      return;
    }

    if (req.method !== 'GET') {
      res.writeHead(405, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ error: 'Method not allowed' }));
      return;
    }

    if (pathname === '/runner.js') {
      serveFile(runnerPath, res);
      return;
    }

    if (pathname === '/dom-to-pptx.bundle.js') {
      serveFile(bundlePath, res);
      return;
    }

    if (pathname.startsWith('/assets/')) {
      const candidate = path.normalize(path.join(assetsDir, pathname.slice('/assets/'.length)));
      if (!candidate.startsWith(assetsDir)) {
        res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ error: 'Forbidden' }));
        return;
      }
      serveFile(candidate, res);
      return;
    }

    const normalizedPath = pathname === '/' ? '/index.html' : pathname;
    const candidate = path.normalize(path.join(htmlRootDir, normalizedPath.replace(/^\/+/, '')));
    if (!candidate.startsWith(htmlRootDir)) {
      res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ error: 'Forbidden' }));
      return;
    }
    serveFile(candidate, res);
  });

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, HOST, () => {
      server.removeListener('error', reject);
      resolve(server);
    });
  });
}

function runChromeExport(pageUrl) {
  return new Promise((resolve, reject) => {
    ensureFileExists(chromePath, 'Chrome executable');

    const args = [
      '--headless=new',
      '--disable-gpu',
      '--virtual-time-budget=60000',
      ...chromeArgs,
      '--dump-dom',
      pageUrl,
    ];

    const chrome = spawn(
      chromePath,
      args,
      {
        cwd: repoRoot,
        stdio: ['ignore', 'pipe', 'pipe'],
      }
    );

    let stdout = '';
    let stderr = '';

    chrome.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });

    chrome.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    chrome.on('error', reject);
    chrome.on('close', (code) => {
      resolve({ code, stdout, stderr });
    });
  });
}

async function waitForOutput(outputFile, previousMtimeMs, timeoutMs = 70000) {
  const start = Date.now();
  while (Date.now() - start <= timeoutMs) {
    if (fs.existsSync(outputFile)) {
      const stats = fs.statSync(outputFile);
      if (stats.mtimeMs > previousMtimeMs && stats.size > 0) {
        return stats;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for PPTX output: ${outputFile}`);
}

function getAvailablePort() {
  return new Promise((resolve, reject) => {
    const probe = http.createServer();
    probe.once('error', reject);
    probe.listen(0, HOST, () => {
      const address = probe.address();
      const port = address && typeof address === 'object' ? address.port : null;
      probe.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve(port);
      });
    });
  });
}

async function exportHtmlToPptx({ htmlPath, outputPath, jobWorkspace, serverPort }) {
  const resolvedHtmlPath = path.resolve(htmlPath);
  const resolvedOutputPath = path.resolve(outputPath);
  const htmlRootDir = path.dirname(resolvedHtmlPath);
  const outputDir = path.dirname(resolvedOutputPath);
  const outputFileName = path.basename(resolvedOutputPath);
  const resolvedServerPort = serverPort || (await getAvailablePort());
  const exportHtmlPath = path.join(
    htmlRootDir,
    `.__export__-${Date.now()}-${path.basename(resolvedHtmlPath)}`
  );

  ensureFileExists(resolvedHtmlPath, 'HTML file');
  fs.copyFileSync(resolvedHtmlPath, exportHtmlPath);

  const preparation = prepareHtml(exportHtmlPath, outputFileName);
  const previousMtimeMs = fs.existsSync(resolvedOutputPath) ? fs.statSync(resolvedOutputPath).mtimeMs : 0;
  const pageUrl = `http://${HOST}:${resolvedServerPort}/${path.basename(exportHtmlPath)}`;
  const server = await createExportServer({
    htmlRootDir,
    outputDir,
    port: resolvedServerPort,
  });

  try {
    const chromeResult = await runChromeExport(pageUrl);
    const debugPaths = writeDebugArtifacts(jobWorkspace, chromeResult);
    let stats;
    try {
      stats = await waitForOutput(resolvedOutputPath, previousMtimeMs);
    } catch (error) {
      const statusMessage = extractStatusMessage(chromeResult.stdout);
      const suffixParts = [];
      if (statusMessage) {
        suffixParts.push(`browser status: ${statusMessage}`);
      }
      if (debugPaths.dom) {
        suffixParts.push(`debug DOM: ${debugPaths.dom}`);
      }
      if (debugPaths.log) {
        suffixParts.push(`debug log: ${debugPaths.log}`);
      }
      error.message = suffixParts.length > 0 ? `${error.message} (${suffixParts.join('; ')})` : error.message;
      throw error;
    }
    return {
      preparation,
      outputFile: resolvedOutputPath,
      outputSize: stats.size,
      pageUrl,
      chromeResult,
      jobWorkspace,
    };
  } finally {
    if (fs.existsSync(exportHtmlPath)) {
      fs.unlinkSync(exportHtmlPath);
    }
    await new Promise((resolve, reject) => {
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve();
      });
    });
  }
}

module.exports = {
  exportHtmlToPptx,
};
