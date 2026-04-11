const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs/promises');
const os = require('os');
const path = require('path');

function clearModule(modulePath) {
  delete require.cache[require.resolve(modulePath)];
}

test('html2ppt config uses a 30-minute Claude timeout', () => {
  const previousTimeout = process.env.PPT_CLAUDE_TIMEOUT_MS;

  delete process.env.PPT_CLAUDE_TIMEOUT_MS;
  clearModule('../src/config');

  try {
    const config = require('../src/config');
    assert.equal(config.claudeTimeoutMs, 1800000);
  } finally {
    if (previousTimeout === undefined) {
      delete process.env.PPT_CLAUDE_TIMEOUT_MS;
    } else {
      process.env.PPT_CLAUDE_TIMEOUT_MS = previousTimeout;
    }
    clearModule('../src/config');
  }
});

test('ClaudeCodeRunner can execute a Windows cmd shim and produce output', async () => {
  if (process.platform !== 'win32') {
    return;
  }

  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'claude-runner-test-'));
  const fakeClaudePath = path.join(tempRoot, 'fake-claude.cmd');
  const promptPath = path.join(tempRoot, 'prompt.txt');
  const outputPath = path.join(tempRoot, 'deck.fragment.html');

  await fs.writeFile(
    fakeClaudePath,
    [
      '@echo off',
      'setlocal',
      'set "target="',
      ':loop',
      'if "%~1"=="" goto done',
      'echo %~1 | findstr /b /c:"--" >nul || set "target=%~1"',
      'shift',
      'goto loop',
      ':done',
      'if not defined target exit /b 7',
      'echo ^<div class="slide"^>generated^</div^> > "%target%"',
      'exit /b 0',
      '',
    ].join('\r\n'),
    'utf8'
  );
  await fs.writeFile(promptPath, 'prompt placeholder\n', 'utf8');

  const previousCmd = process.env.PPT_CLAUDE_CMD;
  const previousArgs = process.env.PPT_CLAUDE_ARGS;

  process.env.PPT_CLAUDE_CMD = fakeClaudePath;
  process.env.PPT_CLAUDE_ARGS = '["{output_file}"]';

  clearModule('../src/config');
  clearModule('../src/agents/claude-code-runner');
  const { ClaudeCodeRunner } = require('../src/agents/claude-code-runner');

  try {
    const runner = new ClaudeCodeRunner();
    await runner.run({
      promptPath,
      outputPath,
      workspaceDir: tempRoot,
      prompt: 'ignored prompt',
    });

    const output = await fs.readFile(outputPath, 'utf8');
    assert.match(output, /generated/);
  } finally {
    if (previousCmd === undefined) {
      delete process.env.PPT_CLAUDE_CMD;
    } else {
      process.env.PPT_CLAUDE_CMD = previousCmd;
    }

    if (previousArgs === undefined) {
      delete process.env.PPT_CLAUDE_ARGS;
    } else {
      process.env.PPT_CLAUDE_ARGS = previousArgs;
    }

    clearModule('../src/config');
    clearModule('../src/agents/claude-code-runner');
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('ClaudeCodeRunner saves raw agent logs when no output file is produced', async () => {
  if (process.platform !== 'win32') {
    return;
  }

  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'claude-runner-test-'));
  const fakeClaudePath = path.join(tempRoot, 'fake-no-output.cmd');
  const promptPath = path.join(tempRoot, 'prompt.txt');
  const outputPath = path.join(tempRoot, 'deck.fragment.html');
  const stdoutLogPath = path.join(tempRoot, 'agent-stdout.log');
  const stderrLogPath = path.join(tempRoot, 'agent-stderr.log');

  await fs.writeFile(
    fakeClaudePath,
    [
      '@echo off',
      'echo not-a-slide-fragment',
      'echo stderr-marker 1>&2',
      'exit /b 0',
      '',
    ].join('\r\n'),
    'utf8'
  );
  await fs.writeFile(promptPath, 'prompt placeholder\n', 'utf8');

  const previousCmd = process.env.PPT_CLAUDE_CMD;
  const previousArgs = process.env.PPT_CLAUDE_ARGS;

  process.env.PPT_CLAUDE_CMD = fakeClaudePath;
  process.env.PPT_CLAUDE_ARGS = '[]';

  clearModule('../src/config');
  clearModule('../src/agents/claude-code-runner');
  const { ClaudeCodeRunner } = require('../src/agents/claude-code-runner');

  try {
    const runner = new ClaudeCodeRunner();

    await assert.rejects(
      () =>
        runner.run({
          promptPath,
          outputPath,
          workspaceDir: tempRoot,
          prompt: 'ignored prompt',
        }),
      /did not produce output file/
    );

    assert.match(await fs.readFile(stdoutLogPath, 'utf8'), /not-a-slide-fragment/);
    assert.match(await fs.readFile(stderrLogPath, 'utf8'), /stderr-marker/);
  } finally {
    if (previousCmd === undefined) {
      delete process.env.PPT_CLAUDE_CMD;
    } else {
      process.env.PPT_CLAUDE_CMD = previousCmd;
    }

    if (previousArgs === undefined) {
      delete process.env.PPT_CLAUDE_ARGS;
    } else {
      process.env.PPT_CLAUDE_ARGS = previousArgs;
    }

    clearModule('../src/config');
    clearModule('../src/agents/claude-code-runner');
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('ClaudeCodeRunner forces bare mode and persists stdout slide fragments', async () => {
  if (process.platform !== 'win32') {
    return;
  }

  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'claude-runner-test-'));
  const fakeClaudePath = path.join(tempRoot, 'fake-stdout-only.cmd');
  const promptPath = path.join(tempRoot, 'prompt.txt');
  const outputPath = path.join(tempRoot, 'deck.fragment.html');

  await fs.writeFile(
    fakeClaudePath,
    [
      '@echo off',
      'setlocal',
      'set found=',
      ':loop',
      'if "%~1"=="" goto done',
      'if /I "%~1"=="--bare" set found=1',
      'shift',
      'goto loop',
      ':done',
      'if not defined found exit /b 9',
      'echo ^<div class="slide"^>stdout-fragment^</div^>',
      'exit /b 0',
      '',
    ].join('\r\n'),
    'utf8'
  );
  await fs.writeFile(promptPath, 'prompt placeholder\n', 'utf8');

  const previousCmd = process.env.PPT_CLAUDE_CMD;
  const previousArgs = process.env.PPT_CLAUDE_ARGS;

  process.env.PPT_CLAUDE_CMD = fakeClaudePath;
  process.env.PPT_CLAUDE_ARGS = '["-p","--output-format","text"]';

  clearModule('../src/config');
  clearModule('../src/agents/claude-code-runner');
  const { ClaudeCodeRunner } = require('../src/agents/claude-code-runner');

  try {
    const runner = new ClaudeCodeRunner();
    await runner.run({
      promptPath,
      outputPath,
      workspaceDir: tempRoot,
      prompt: 'ignored prompt',
    });

    const output = await fs.readFile(outputPath, 'utf8');
    assert.match(output, /stdout-fragment/);
  } finally {
    if (previousCmd === undefined) {
      delete process.env.PPT_CLAUDE_CMD;
    } else {
      process.env.PPT_CLAUDE_CMD = previousCmd;
    }

    if (previousArgs === undefined) {
      delete process.env.PPT_CLAUDE_ARGS;
    } else {
      process.env.PPT_CLAUDE_ARGS = previousArgs;
    }

    clearModule('../src/config');
    clearModule('../src/agents/claude-code-runner');
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('ClaudeCodeRunner times out hung commands and persists diagnostics', async () => {
  if (process.platform !== 'win32') {
    return;
  }

  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'claude-runner-test-'));
  const fakeClaudePath = path.join(tempRoot, 'fake-hung.cmd');
  const promptPath = path.join(tempRoot, 'prompt.txt');
  const outputPath = path.join(tempRoot, 'deck.fragment.html');
  const resultPath = path.join(tempRoot, 'agent-result.json');
  const stderrLogPath = path.join(tempRoot, 'agent-stderr.log');
  const invocationPath = path.join(tempRoot, 'agent-invocation.json');

  await fs.writeFile(
    fakeClaudePath,
    [
      '@echo off',
      'echo started',
      'ping -n 30 127.0.0.1 >nul',
      'exit /b 0',
      '',
    ].join('\r\n'),
    'utf8'
  );
  await fs.writeFile(promptPath, 'prompt placeholder\n', 'utf8');

  const previousCmd = process.env.PPT_CLAUDE_CMD;
  const previousArgs = process.env.PPT_CLAUDE_ARGS;
  const previousTimeout = process.env.PPT_CLAUDE_TIMEOUT_MS;

  process.env.PPT_CLAUDE_CMD = fakeClaudePath;
  process.env.PPT_CLAUDE_ARGS = '[]';
  process.env.PPT_CLAUDE_TIMEOUT_MS = '200';

  clearModule('../src/config');
  clearModule('../src/agents/claude-code-runner');
  const { ClaudeCodeRunner } = require('../src/agents/claude-code-runner');

  try {
    const runner = new ClaudeCodeRunner();

    await assert.rejects(
      () =>
        runner.run({
          promptPath,
          outputPath,
          workspaceDir: tempRoot,
          prompt: 'ignored prompt',
        }),
      /timed out after 200ms/
    );

    const invocation = JSON.parse(await fs.readFile(invocationPath, 'utf8'));
    const result = JSON.parse(await fs.readFile(resultPath, 'utf8'));
    const stderrLog = await fs.readFile(stderrLogPath, 'utf8');

    assert.equal(invocation.timeout_ms, 200);
    assert.equal(result.exit_code, null);
    assert.match(stderrLog, /timed out/i);
  } finally {
    if (previousCmd === undefined) {
      delete process.env.PPT_CLAUDE_CMD;
    } else {
      process.env.PPT_CLAUDE_CMD = previousCmd;
    }

    if (previousArgs === undefined) {
      delete process.env.PPT_CLAUDE_ARGS;
    } else {
      process.env.PPT_CLAUDE_ARGS = previousArgs;
    }

    if (previousTimeout === undefined) {
      delete process.env.PPT_CLAUDE_TIMEOUT_MS;
    } else {
      process.env.PPT_CLAUDE_TIMEOUT_MS = previousTimeout;
    }

    clearModule('../src/config');
    clearModule('../src/agents/claude-code-runner');
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
