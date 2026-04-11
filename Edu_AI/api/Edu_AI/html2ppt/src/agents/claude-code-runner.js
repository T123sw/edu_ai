const fs = require('fs/promises');
const { spawn } = require('child_process');
const path = require('path');
const { repoRoot, claudeCmd, claudeArgs, claudeTimeoutMs } = require('../config');
const { AppError } = require('../domain/errors');
const { fileExists } = require('../lib/file-utils');
const { extractBodyFragment, hasSlideClass } = require('../lib/build-standalone-html');

function interpolateArg(arg, context) {
  return String(arg).replace(/\{([a-z_]+)\}/gi, (_, key) => {
    return Object.prototype.hasOwnProperty.call(context, key) ? context[key] : '';
  });
}

function normalizeAgentOutput(stdout) {
  const normalized = extractBodyFragment(String(stdout || '').trim());
  return normalized.trim();
}

function ensureBareMode(args) {
  const normalizedArgs = Array.isArray(args) ? [...args] : [];
  if (normalizedArgs.some((arg) => String(arg).trim() === '--bare')) {
    return normalizedArgs;
  }
  return ['--bare', ...normalizedArgs];
}

async function persistAgentDiagnostics(workspaceDir, result) {
  if (!workspaceDir) {
    return;
  }

  await fs.writeFile(path.join(workspaceDir, 'agent-stdout.log'), String(result.stdout || ''), 'utf8');
  await fs.writeFile(path.join(workspaceDir, 'agent-stderr.log'), String(result.stderr || ''), 'utf8');
  await fs.writeFile(
    path.join(workspaceDir, 'agent-result.json'),
    `${JSON.stringify(
      {
        exit_code: result.code,
        stdout_bytes: Buffer.byteLength(String(result.stdout || ''), 'utf8'),
        stderr_bytes: Buffer.byteLength(String(result.stderr || ''), 'utf8'),
      },
      null,
      2
    )}\n`,
    'utf8'
  );
}

async function persistAgentInvocation(workspaceDir, invocation) {
  if (!workspaceDir) {
    return;
  }

  await fs.writeFile(
    path.join(workspaceDir, 'agent-invocation.json'),
    `${JSON.stringify(invocation, null, 2)}\n`,
    'utf8'
  );
}

function needsWindowsCmdShim(command) {
  if (process.platform !== 'win32') {
    return false;
  }

  const normalized = String(command || '').trim();
  return /\.(cmd|bat)$/i.test(normalized) || path.extname(normalized) === '';
}

function buildSpawnSpec(command, args) {
  if (needsWindowsCmdShim(command)) {
    return {
      command,
      args,
      options: {
        shell: true,
      },
    };
  }

  return {
    command,
    args,
    options: {},
  };
}

class ClaudeCodeRunner {
  async run({ promptPath, outputPath, workspaceDir, prompt }) {
    const context = {
      prompt_file: promptPath,
      output_file: outputPath,
      job_dir: workspaceDir,
      repo_root: repoRoot,
    };

    const args = ensureBareMode(claudeArgs.map((arg) => interpolateArg(arg, context)));
    const spawnSpec = buildSpawnSpec(claudeCmd, args);
    const startedAt = new Date().toISOString();

    await persistAgentInvocation(workspaceDir, {
      command: spawnSpec.command,
      args: spawnSpec.args,
      cwd: repoRoot,
      prompt_path: promptPath,
      output_path: outputPath,
      started_at: startedAt,
      timeout_ms: claudeTimeoutMs,
      shell: Boolean(spawnSpec.options.shell),
    });

    const result = await new Promise((resolve, reject) => {
      const child = spawn(spawnSpec.command, spawnSpec.args, {
        cwd: repoRoot,
        stdio: ['pipe', 'pipe', 'pipe'],
        windowsHide: true,
        ...spawnSpec.options,
      });

      let stdout = '';
      let stderr = '';
      let settled = false;
      let timeoutHandle = null;

      const finalizeReject = async (error) => {
        if (settled) {
          return;
        }
        settled = true;
        if (timeoutHandle) {
          clearTimeout(timeoutHandle);
        }
        reject(error);
      };

      const finalizeResolve = (value) => {
        if (settled) {
          return;
        }
        settled = true;
        if (timeoutHandle) {
          clearTimeout(timeoutHandle);
        }
        resolve(value);
      };

      child.stdout.on('data', (chunk) => {
        stdout += chunk.toString();
      });

      child.stderr.on('data', (chunk) => {
        stderr += chunk.toString();
      });

      child.on('error', async (error) => {
        await persistAgentDiagnostics(workspaceDir, {
          code: null,
          stdout,
          stderr,
          cause: error.message,
          failed_to_start: true,
        });
        await finalizeReject(
          new AppError(
            'AGENT_GENERATION_FAILED',
            `Failed to start Claude Code command: ${claudeCmd}`,
            500,
            { cause: error.message, command: spawnSpec.command, args: spawnSpec.args }
          )
        );
      });

      child.on('close', (code) => {
        finalizeResolve({ code, stdout, stderr });
      });

      timeoutHandle = setTimeout(async () => {
        stderr += stderr ? '\n[runner] Claude Code timed out.' : '[runner] Claude Code timed out.';
        child.kill();
        await persistAgentDiagnostics(workspaceDir, {
          code: null,
          stdout,
          stderr,
          timed_out: true,
          timeout_ms: claudeTimeoutMs,
        });
        await finalizeReject(
          new AppError(
            'AGENT_GENERATION_FAILED',
            `Claude Code execution timed out after ${claudeTimeoutMs}ms`,
            500,
            {
              timeout_ms: claudeTimeoutMs,
              stdout: stdout.trim() || undefined,
              stderr: stderr.trim() || undefined,
            }
          )
        );
      }, claudeTimeoutMs);

      child.stdin.write(prompt);
      child.stdin.end();
    });

    if (!(await fileExists(outputPath))) {
      const normalized = normalizeAgentOutput(result.stdout);
      if (normalized && hasSlideClass(normalized)) {
        await fs.writeFile(outputPath, `${normalized}\n`, 'utf8');
      }
    }

    if (result.code !== 0) {
      await persistAgentDiagnostics(workspaceDir, result);
      throw new AppError(
        'AGENT_GENERATION_FAILED',
        `Claude Code execution failed with code ${result.code}`,
        500,
        {
          stderr: result.stderr.trim() || undefined,
          stdout: result.stdout.trim() || undefined,
        }
      );
    }

    if (!(await fileExists(outputPath))) {
      await persistAgentDiagnostics(workspaceDir, result);
      throw new AppError(
        'AGENT_GENERATION_FAILED',
        `Claude Code finished but did not produce output file: ${path.relative(repoRoot, outputPath)}`,
        500,
        {
          stdout: result.stdout.trim() || undefined,
          stderr: result.stderr.trim() || undefined,
        }
      );
    }

    return result;
  }
}

module.exports = {
  ClaudeCodeRunner,
  buildSpawnSpec,
  ensureBareMode,
};
