const fs = require('fs');
const path = require('path');

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

function loadEnvFileIntoProcess(envPath) {
  if (!envPath || !fs.existsSync(envPath)) {
    return;
  }

  const source = fs.readFileSync(envPath, 'utf8');
  const lines = source.split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('//')) {
      continue;
    }

    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) {
      continue;
    }

    const [, key, rawValue] = match;
    if (Object.prototype.hasOwnProperty.call(process.env, key) && String(process.env[key] || '').trim()) {
      continue;
    }

    process.env[key] = stripWrappingQuotes(rawValue);
  }
}

function normalizeBaseUrl(baseUrl) {
  const normalized = String(baseUrl || '').trim().replace(/\/+$/, '');
  if (!normalized) {
    return '';
  }
  return normalized.endsWith('/v1') ? normalized : `${normalized}/v1`;
}

function resolveDeepSeekConfig() {
  const apiKey = String(process.env.DEEPSEEK_API_KEY || '').trim();
  const apiBase = normalizeBaseUrl(process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com/v1');
  const model =
    String(process.env.DEEPSEEK_MODEL || '').trim() ||
    String(process.env.LLM_MODEL_DEEP || '').trim() ||
    'deepseek-chat';

  if (!apiKey) {
    throw new Error('Missing DEEPSEEK_API_KEY in environment.');
  }

  return {
    apiKey,
    apiBase,
    model,
  };
}

function buildProbeMessages({ promptText, workspaceDir, promptPath, outputPath }) {
  return [
    {
      role: 'system',
      content:
        '你现在不是 Claude Code，也不需要调用任何本地工具。你是一个纯文本大模型测试探针。请基于我提供的原始 agent prompt 和工作目录信息，直接输出你会返回给调用方的最终文本结果。不要解释你的行为，不要补充额外说明。',
    },
    {
      role: 'user',
      content: [
        '下面是一次 html2ppt 对 Claude 的真实调用上下文，请你直接模拟模型侧输出。',
        `工作目录: ${workspaceDir}`,
        `原始 prompt 文件: ${promptPath}`,
        `建议输出保存路径: ${outputPath}`,
        '',
        '要求：',
        '1. 把下面的原始 prompt 当作唯一主要输入。',
        '2. 你无法真正读取本地文件，所以如果 prompt 中要求“读取 content.md”之类文件，请仅基于 prompt 文本本身给出你此刻会输出的内容。',
        '3. 只输出最终结果文本，不要加解释，不要加代码围栏，除非原始 prompt 本身迫使你这么做。',
        '',
        '===== BEGIN AGENT PROMPT =====',
        promptText,
        '===== END AGENT PROMPT =====',
      ].join('\n'),
    },
  ];
}

async function callDeepSeek({ apiBase, apiKey, model, messages, temperature = 0.2, maxTokens = 4000 }) {
  const response = await fetch(`${apiBase}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      messages,
      temperature,
      max_tokens: maxTokens,
    }),
  });

  if (!response.ok) {
    throw new Error(`DeepSeek API error ${response.status}: ${await response.text()}`);
  }

  const data = await response.json();
  return String(data?.choices?.[0]?.message?.content || '').trim();
}

async function main() {
  const promptPath = process.argv[2];
  const workspaceDir = process.argv[3];
  const outputPath = process.argv[4];

  if (!promptPath) {
    throw new Error(
      'Usage: node scripts/test-deepseek-agent-prompt.js <promptPath> [workspaceDir] [outputPath]'
    );
  }

  const resolvedPromptPath = path.resolve(promptPath);
  const resolvedWorkspaceDir = workspaceDir
    ? path.resolve(workspaceDir)
    : path.dirname(resolvedPromptPath);
  const resolvedOutputPath = outputPath
    ? path.resolve(outputPath)
    : path.join(resolvedWorkspaceDir, 'deepseek-direct-output.txt');

  const repoRoot = path.resolve(__dirname, '..');
  const backendEnvPath = path.resolve(repoRoot, '..', '.env');
  loadEnvFileIntoProcess(backendEnvPath);

  const config = resolveDeepSeekConfig();
  const promptText = fs.readFileSync(resolvedPromptPath, 'utf8');
  const messages = buildProbeMessages({
    promptText,
    workspaceDir: resolvedWorkspaceDir,
    promptPath: resolvedPromptPath,
    outputPath: resolvedOutputPath,
  });

  const output = await callDeepSeek({
    apiBase: config.apiBase,
    apiKey: config.apiKey,
    model: config.model,
    messages,
  });

  fs.writeFileSync(resolvedOutputPath, `${output}\n`, 'utf8');

  process.stdout.write(
    `${JSON.stringify(
      {
        api_base: config.apiBase,
        model: config.model,
        prompt_path: resolvedPromptPath,
        workspace_dir: resolvedWorkspaceDir,
        output_path: resolvedOutputPath,
        output_chars: output.length,
      },
      null,
      2
    )}\n`
  );
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.message || String(error));
    process.exit(1);
  });
}

module.exports = {
  buildProbeMessages,
  loadEnvFileIntoProcess,
  resolveDeepSeekConfig,
};
