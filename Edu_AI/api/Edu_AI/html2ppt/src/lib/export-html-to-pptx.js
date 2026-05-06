const fs = require('fs');
const http = require('http');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const { repoRoot, chromePath, chromeArgs } = require('../config');

const HOST = '127.0.0.1';
const DEFAULT_CHROME_EXPORT_TIMEOUT_MS = 120000;

function shouldUseShellForCommand(command, platform = process.platform) {
  return platform === 'win32' && /\.(cmd|bat)$/i.test(String(command || '').trim());
}

function buildProcessSpawnOptions({ command, cwd, platform = process.platform }) {
  return {
    cwd,
    encoding: 'utf8',
    stdio: 'pipe',
    shell: shouldUseShellForCommand(command, platform),
  };
}

function parsePositiveInt(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function ensureFileExists(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`${label} not found: ${filePath}`);
  }
}

function walkLatestMtime(targetPath) {
  if (!fs.existsSync(targetPath)) {
    return 0;
  }
  const stats = fs.statSync(targetPath);
  if (!stats.isDirectory()) {
    return stats.mtimeMs;
  }

  let latest = stats.mtimeMs;
  for (const entry of fs.readdirSync(targetPath, { withFileTypes: true })) {
    latest = Math.max(latest, walkLatestMtime(path.join(targetPath, entry.name)));
  }
  return latest;
}

function syncDomToPptxBundle() {
  const domToPptxDir = path.join(repoRoot, 'dom-to-pptx');
  const sourceDir = path.join(domToPptxDir, 'src');
  const rollupConfigPath = path.join(domToPptxDir, 'rollup.config.js');
  const packageJsonPath = path.join(domToPptxDir, 'package.json');
  const distBundlePath = path.join(domToPptxDir, 'dist', 'dom-to-pptx.bundle.js');
  const harnessBundlePath = path.join(repoRoot, 'test-harness', 'dom-to-pptx.bundle.js');

  const sourceMtime = Math.max(
    walkLatestMtime(sourceDir),
    walkLatestMtime(rollupConfigPath),
    walkLatestMtime(packageJsonPath)
  );
  const harnessMtime = walkLatestMtime(harnessBundlePath);
  const distMtime = walkLatestMtime(distBundlePath);

  if (harnessMtime >= sourceMtime) {
    return harnessBundlePath;
  }

  if (distMtime < sourceMtime) {
    const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
    const buildResult = spawnSync(
      npmCommand,
      ['run', 'build'],
      buildProcessSpawnOptions({
        command: npmCommand,
        cwd: domToPptxDir,
      })
    );
    if (buildResult.error) {
      throw new Error(`Failed to build dom-to-pptx bundle: ${buildResult.error.message}`);
    }
    if (buildResult.status !== 0) {
      const stderr = String(buildResult.stderr || buildResult.stdout || '').trim();
      throw new Error(`Failed to build dom-to-pptx bundle: ${stderr}`);
    }
  }

  ensureFileExists(distBundlePath, 'dom-to-pptx dist bundle');
  fs.copyFileSync(distBundlePath, harnessBundlePath);
  return harnessBundlePath;
}

function extractStatusMessage(domDump) {
  const match = String(domDump || '').match(/<div[^>]*id=["']status["'][^>]*>([\s\S]*?)<\/div>/i);
  if (!match) {
    return null;
  }
  return match[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() || null;
}

function isUnfinishedExportStatus(statusMessage) {
  return /^(Preparing export|Running export)/i.test(String(statusMessage || '').trim());
}

function outputIsFresh(outputFile, previousMtimeMs) {
  if (!fs.existsSync(outputFile)) {
    return false;
  }
  const stats = fs.statSync(outputFile);
  return stats.mtimeMs > previousMtimeMs && stats.size > 0;
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
          signal: chromeResult.signal,
          timedOut: Boolean(chromeResult.timedOut),
          timeoutMs: chromeResult.timeoutMs,
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

  const absoluteAssetNormalized = html.replace(
    /\b(src|href)=("|\')(?:file:\/\/)?[^"']*\/assets\/([^"']+)\2/gi,
    (match, attr, quote, assetPath) => {
      changed = true;
      return `${attr}=${quote}/assets/${assetPath}${quote}`;
    }
  );

  const relativeAssetNormalized = absoluteAssetNormalized.replace(
    /\b(src|href)=("|\')\.?\/?assets\/([^"']+)\2/gi,
    (match, attr, quote, assetPath) => {
      changed = true;
      return `${attr}=${quote}/assets/${assetPath}${quote}`;
    }
  );

  const urlNormalized = relativeAssetNormalized.replace(
    /url\((["']?)(?:file:\/\/)?[^)"']*\/assets\/([^)"']+)\1\)/gi,
    (match, quote, assetPath) => {
      changed = true;
      return `url(${quote}/assets/${assetPath}${quote})`;
    }
  );

  return { html: urlNormalized, changed };
}

function getHtmlAttribute(attrs, name) {
  const pattern = new RegExp(`\\b${name}\\s*=\\s*(["'])(.*?)\\1`, 'i');
  const match = String(attrs || '').match(pattern);
  return match ? { quote: match[1], value: match[2] } : null;
}

function normalizeVideoSourceTags(html) {
  let changed = false;

  const normalized = html.replace(/<video\b([^>]*)>([\s\S]*?)<\/video>/gi, (match, attrs, body) => {
    const sourceMatch = String(body || '').match(/<source\b([^>]*)>/i);
    if (!sourceMatch) return match;

    const sourceSrc = getHtmlAttribute(sourceMatch[1], 'src');
    if (!sourceSrc) return match;

    const nextAttrs = /\bsrc\s*=/i.test(attrs)
      ? attrs
      : `${attrs} src=${sourceSrc.quote}${sourceSrc.value}${sourceSrc.quote}`;
    const nextBody = String(body || '').replace(/\s*<source\b[^>]*>\s*/gi, '');
    changed = true;
    return `<video${nextAttrs}>${nextBody}</video>`;
  });

  return { html: normalized, changed };
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

  const videoResult = normalizeVideoSourceTags(html);
  html = videoResult.html;
  if (videoResult.changed) {
    changes.push('normalized video source tags');
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
  const bundlePath = syncDomToPptxBundle();
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

function runChromeExport(pageUrl, options = {}) {
  return new Promise((resolve, reject) => {
    const chromeExecutable = options.chromePathOverride || chromePath;
    const spawnChrome = options.spawnChrome || spawn;
    const timeoutMs =
      options.timeoutMs ||
      parsePositiveInt(process.env.PPT_CHROME_TIMEOUT_MS, DEFAULT_CHROME_EXPORT_TIMEOUT_MS);
    const virtualTimeBudgetMs = parsePositiveInt(
      options.virtualTimeBudgetMs || process.env.PPT_CHROME_VIRTUAL_TIME_BUDGET_MS,
      timeoutMs
    );

    ensureFileExists(chromeExecutable, 'Chrome executable');

    const args = [
      '--headless=new',
      '--disable-gpu',
      `--virtual-time-budget=${virtualTimeBudgetMs}`,
      ...chromeArgs,
      '--dump-dom',
      pageUrl,
    ];

    const chrome = spawnChrome(chromeExecutable, args, {
      cwd: repoRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    let settled = false;
    let timedOut = false;
    let forceKillTimer = null;

    const cleanup = () => {
      if (timeoutTimer) clearTimeout(timeoutTimer);
      if (forceKillTimer) clearTimeout(forceKillTimer);
      chrome.removeListener('error', onError);
      chrome.removeListener('close', onClose);
    };

    const finish = (result) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve({
        stdout,
        stderr,
        timedOut,
        timeoutMs,
        ...result,
      });
    };

    const fail = (error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    };

    const terminateForTimeout = () => {
      if (settled) return;
      timedOut = true;
      stderr += `\n[html2ppt] Chrome export timed out after ${timeoutMs}ms; terminating browser.`;
      try {
        chrome.kill('SIGTERM');
      } catch {
        // Fall through to the force-kill timer below.
      }

      forceKillTimer = setTimeout(() => {
        if (settled) return;
        try {
          chrome.kill('SIGKILL');
        } catch {
          // If the process cannot be killed, still resolve so the job can fail instead of hanging.
        }
        finish({ code: null, signal: 'SIGKILL' });
      }, 3000);
      if (typeof forceKillTimer.unref === 'function') forceKillTimer.unref();
    };

    const timeoutTimer = setTimeout(terminateForTimeout, timeoutMs);
    if (typeof timeoutTimer.unref === 'function') timeoutTimer.unref();

    if (chrome.stdout) chrome.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });

    if (chrome.stderr) chrome.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    function onError(error) {
      if (timedOut) {
        finish({ code: null, signal: null, error: error.message });
        return;
      }
      fail(error);
    }

    function onClose(code, signal) {
      finish({ code, signal });
    }

    chrome.on('error', onError);
    chrome.on('close', onClose);
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
    const statusMessage = extractStatusMessage(chromeResult.stdout);
    if (chromeResult.timedOut) {
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
      const suffix = suffixParts.length > 0 ? ` (${suffixParts.join('; ')})` : '';
      throw new Error(`Chrome export timed out after ${chromeResult.timeoutMs}ms${suffix}`);
    }
    if (isUnfinishedExportStatus(statusMessage) && !outputIsFresh(resolvedOutputPath, previousMtimeMs)) {
      const suffixParts = [`browser status: ${statusMessage}`];
      if (debugPaths.dom) {
        suffixParts.push(`debug DOM: ${debugPaths.dom}`);
      }
      if (debugPaths.log) {
        suffixParts.push(`debug log: ${debugPaths.log}`);
      }
      throw new Error(
        `Browser exited before PPTX export completed: ${resolvedOutputPath} (${suffixParts.join('; ')})`
      );
    }
    let stats;
    try {
      stats = await waitForOutput(resolvedOutputPath, previousMtimeMs);
    } catch (error) {
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
  buildProcessSpawnOptions,
  exportHtmlToPptx,
  normalizeRepoAssetPaths,
  normalizeVideoSourceTags,
  runChromeExport,
  syncDomToPptxBundle,
};
