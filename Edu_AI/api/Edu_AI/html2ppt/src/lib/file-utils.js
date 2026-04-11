const fs = require('fs/promises');
const path = require('path');
const crypto = require('crypto');

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

async function writeJson(filePath, value) {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function readJson(filePath) {
  const content = await fs.readFile(filePath, 'utf8');
  return JSON.parse(content);
}

async function fileExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map((entry) => stableStringify(entry)).join(',')}]`;
  }

  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(',')}}`;
  }

  return JSON.stringify(value);
}

function sha256(value) {
  return crypto.createHash('sha256').update(String(value)).digest('hex');
}

function hashRequestForIdempotency(request) {
  const normalized = {
    content_markdown: request.content_markdown,
    theme_id: request.theme_id,
    metadata: {
      request_id: request.metadata?.request_id || null,
      user_id: request.metadata?.user_id || null,
      tenant_id: request.metadata?.tenant_id || 'default',
    },
  };

  return sha256(stableStringify(normalized));
}

module.exports = {
  ensureDir,
  fileExists,
  hashRequestForIdempotency,
  readJson,
  sha256,
  stableStringify,
  writeJson,
};
