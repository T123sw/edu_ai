const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs/promises');
const os = require('os');
const path = require('path');

const {
  buildProbeMessages,
  loadEnvFileIntoProcess,
  resolveDeepSeekConfig,
} = require('../scripts/test-deepseek-agent-prompt');

test('loadEnvFileIntoProcess loads DeepSeek config from env file', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'deepseek-probe-test-'));
  const envPath = path.join(tempRoot, '.env');

  await fs.writeFile(
    envPath,
    [
      'DEEPSEEK_API_KEY=test-key',
      'DEEPSEEK_BASE_URL=https://api.deepseek.com/v1',
      'LLM_MODEL_DEEP=deepseek-chat',
      '',
    ].join('\n'),
    'utf8'
  );

  const previousKey = process.env.DEEPSEEK_API_KEY;
  const previousBase = process.env.DEEPSEEK_BASE_URL;
  const previousModel = process.env.LLM_MODEL_DEEP;

  delete process.env.DEEPSEEK_API_KEY;
  delete process.env.DEEPSEEK_BASE_URL;
  delete process.env.LLM_MODEL_DEEP;

  try {
    loadEnvFileIntoProcess(envPath);
    const config = resolveDeepSeekConfig();

    assert.equal(config.apiKey, 'test-key');
    assert.equal(config.apiBase, 'https://api.deepseek.com/v1');
    assert.equal(config.model, 'deepseek-chat');
  } finally {
    if (previousKey === undefined) {
      delete process.env.DEEPSEEK_API_KEY;
    } else {
      process.env.DEEPSEEK_API_KEY = previousKey;
    }

    if (previousBase === undefined) {
      delete process.env.DEEPSEEK_BASE_URL;
    } else {
      process.env.DEEPSEEK_BASE_URL = previousBase;
    }

    if (previousModel === undefined) {
      delete process.env.LLM_MODEL_DEEP;
    } else {
      process.env.LLM_MODEL_DEEP = previousModel;
    }

    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('buildProbeMessages embeds workspace directory and prompt text', () => {
  const messages = buildProbeMessages({
    promptText: '请读取 content.md 并生成 deck.fragment.html',
    workspaceDir: 'D:\\demo\\workspace',
    promptPath: 'D:\\demo\\workspace\\agent-prompt.txt',
    outputPath: 'D:\\demo\\workspace\\deepseek-response.txt',
  });

  assert.equal(messages.length, 2);
  assert.equal(messages[0].role, 'system');
  assert.equal(messages[1].role, 'user');
  assert.match(messages[1].content, /D:\\demo\\workspace/);
  assert.match(messages[1].content, /agent-prompt\.txt/);
  assert.match(messages[1].content, /请读取 content\.md/);
  assert.match(messages[1].content, /deepseek-response\.txt/);
});
