const path = require('path');
const fs = require('fs');

const repoRoot = path.resolve(__dirname, '..');
const envFilePath = path.join(repoRoot, '.env');

function stripWrappingQuotes(value) {
  const input = String(value || '').trim();
  if (
    (input.startsWith('"') && input.endsWith('"')) ||
    (input.startsWith("'") && input.endsWith("'"))
  ) {
    return input.slice(1, -1);
  }
  return input;
}

function loadEnvFile() {
  if (!fs.existsSync(envFilePath)) {
    return;
  }

  const source = fs.readFileSync(envFilePath, 'utf8');
  const lines = source.split(/\r?\n/);

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }

    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) {
      continue;
    }

    const [, key, rawValue] = match;
    if (Object.prototype.hasOwnProperty.call(process.env, key)) {
      continue;
    }

    process.env[key] = stripWrappingQuotes(rawValue);
  }
}

loadEnvFile();

function parseInteger(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function parseArgsString(value) {
  const input = String(value || '').trim();
  if (!input) {
    return [];
  }

  try {
    const parsed = JSON.parse(input);
    if (Array.isArray(parsed)) {
      return parsed.map((entry) => String(entry));
    }
  } catch {
    // Fall through to shell-like parsing.
  }

  const tokens = [];
  const pattern = /"([^"]*)"|'([^']*)'|(\S+)/g;
  let match;
  while ((match = pattern.exec(input))) {
    tokens.push(match[1] ?? match[2] ?? match[3]);
  }
  return tokens;
}

function resolveDefaultChromePath() {
  const candidatesByPlatform = {
    win32: [
      path.join(process.env.PROGRAMFILES || 'C:\\Program Files', 'Google\\Chrome\\Application\\chrome.exe'),
      path.join(process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)', 'Google\\Chrome\\Application\\chrome.exe'),
      path.join(process.env.LOCALAPPDATA || '', 'Google\\Chrome\\Application\\chrome.exe'),
      path.join(process.env.PROGRAMFILES || 'C:\\Program Files', 'Microsoft\\Edge\\Application\\msedge.exe'),
    ],
    darwin: [
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      '/Applications/Chromium.app/Contents/MacOS/Chromium',
    ],
    linux: [
      '/usr/bin/google-chrome',
      '/usr/bin/google-chrome-stable',
      '/usr/bin/chromium',
      '/usr/bin/chromium-browser',
      '/snap/bin/chromium',
    ],
  };

  const candidates = candidatesByPlatform[process.platform] || candidatesByPlatform.linux;
  return candidates.find((candidate) => candidate && fs.existsSync(candidate)) || candidates[0];
}

module.exports = {
  repoRoot,
  envFilePath,
  servicePort: parseInteger(process.env.PPT_SERVICE_PORT, 4300),
  dataDir: path.resolve(process.env.PPT_DATA_DIR || path.join(repoRoot, 'data')),
  workerConcurrency: parseInteger(process.env.PPT_WORKER_CONCURRENCY, 1),
  chromePath: process.env.PPT_CHROME_PATH || resolveDefaultChromePath(),
  chromeArgs: parseArgsString(process.env.PPT_CHROME_ARGS || ''),
  ffmpegPath: process.env.PPT_FFMPEG_PATH || 'ffmpeg',
  claudeCmd: process.env.PPT_CLAUDE_CMD || 'claude',
  claudeArgs: parseArgsString(process.env.PPT_CLAUDE_ARGS || ''),
  defaultThemeId: process.env.PPT_DEFAULT_THEME_ID || 'heu_academic_elegant',
};
