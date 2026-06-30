const http = require('http');
const fs = require('fs');
const path = require('path');

const host = '127.0.0.1';
const port = 4173;
const harnessDir = __dirname;
const repoRoot = path.resolve(harnessDir, '..');
const outputDir = path.join(harnessDir, 'output');
const defaultOutputFile = path.join(outputDir, 'dom-to-pptx-test.pptx');

fs.mkdirSync(outputDir, { recursive: true });

const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};

function sendJson(res, statusCode, body) {
  const payload = JSON.stringify(body);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(payload),
  });
  res.end(payload);
}

function resolveFilePath(reqPath) {
  const safePath = reqPath === '/' ? '/index.html' : decodeURIComponent(reqPath);
  const relativePath = safePath.replace(/^\/+/, '');
  const baseDir = relativePath.startsWith('assets/') ? repoRoot : harnessDir;
  const filePath = path.normalize(path.join(baseDir, relativePath));
  return { safePath, baseDir, filePath };
}

function sanitizeOutputName(name) {
  const candidate = String(name || '').trim();
  if (!candidate) {
    return path.basename(defaultOutputFile);
  }

  const basename = path.basename(candidate).replace(/[^a-zA-Z0-9._-]/g, '_');
  return basename.endsWith('.pptx') ? basename : `${basename}.pptx`;
}

function serveFile(reqPath, res) {
  const { safePath, baseDir, filePath } = resolveFilePath(reqPath);

  if (!filePath.startsWith(baseDir)) {
    sendJson(res, 403, { error: 'Forbidden' });
    return;
  }

  fs.readFile(filePath, (error, data) => {
    if (error) {
      sendJson(res, 404, { error: `Not found: ${safePath}` });
      return;
    }

    const ext = path.extname(filePath);
    res.writeHead(200, {
      'Content-Type': contentTypes[ext] || 'application/octet-stream',
      'Content-Length': data.length,
    });
    res.end(data);
  });
}

const server = http.createServer((req, res) => {
  if (!req.url) {
    sendJson(res, 400, { error: 'Missing URL' });
    return;
  }

  const requestUrl = new URL(req.url, `http://${host}:${port}`);

  if (req.method === 'POST' && requestUrl.pathname === '/save-pptx') {
    const chunks = [];
    const outputName = sanitizeOutputName(requestUrl.searchParams.get('name'));
    const outputFile = path.join(outputDir, outputName);

    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const body = Buffer.concat(chunks);
      fs.writeFileSync(outputFile, body);
      sendJson(res, 200, {
        ok: true,
        bytes: body.length,
        outputFile,
      });
    });
    req.on('error', (error) => {
      sendJson(res, 500, { error: error.message });
    });
    return;
  }

  if (req.method === 'GET') {
    serveFile(requestUrl.pathname, res);
    return;
  }

  sendJson(res, 405, { error: 'Method not allowed' });
});

server.listen(port, host, () => {
  console.log(`Test harness listening at http://${host}:${port}`);
  console.log(`Default PPTX output path: ${defaultOutputFile}`);
});
