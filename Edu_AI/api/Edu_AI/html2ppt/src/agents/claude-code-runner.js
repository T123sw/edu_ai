const fs = require('fs/promises');
const { spawn } = require('child_process');
const path = require('path');
const { repoRoot, claudeCmd, claudeArgs } = require('../config');
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

function normalizeAgentOutputByKind(stdout, outputKind = 'slide') {
  const trimmed = String(stdout || '').trim();
  if (!trimmed) {
    return '';
  }

  if (outputKind === 'json') {
    JSON.parse(trimmed);
    return trimmed;
  }

  if (outputKind === 'html_document') {
    if (!/<html\b/i.test(trimmed)) {
      throw new Error('Expected a full HTML document.');
    }
    return trimmed;
  }

  return normalizeAgentOutput(trimmed);
}

function shouldUseShellForCommand(command, platform = process.platform) {
  if (platform !== 'win32') {
    return false;
  }
  return /\.(cmd|bat)$/i.test(String(command || '').trim());
}

function buildSpawnOptions({ command, cwd, platform = process.platform }) {
  return {
    cwd,
    stdio: ['pipe', 'pipe', 'pipe'],
    shell: shouldUseShellForCommand(command, platform),
  };
}

class ClaudeCodeRunner {
  async run({ promptPath, outputPath, workspaceDir, prompt, outputKind = 'slide' }) {
    const context = {
      prompt_file: promptPath,
      output_file: outputPath,
      job_dir: workspaceDir,
      repo_root: repoRoot,
    };

    const args = claudeArgs.map((arg) => interpolateArg(arg, context));
    const result = await new Promise((resolve, reject) => {
      const child = spawn(
        claudeCmd,
        args,
        buildSpawnOptions({
          command: claudeCmd,
          cwd: repoRoot,
        })
      );

      let stdout = '';
      let stderr = '';

      child.stdout.on('data', (chunk) => {
        stdout += chunk.toString();
      });

      child.stderr.on('data', (chunk) => {
        stderr += chunk.toString();
      });

      child.on('error', (error) => {
        reject(
          new AppError(
            'AGENT_GENERATION_FAILED',
            `Failed to start Claude Code command: ${claudeCmd}`,
            500,
            { cause: error.message }
          )
        );
      });
      child.on('close', (code) => {
        resolve({ code, stdout, stderr });
      });

      child.stdin.write(prompt);
      child.stdin.end();
    });

    if (!(await fileExists(outputPath))) {
      const normalized = normalizeAgentOutputByKind(result.stdout, outputKind);
      if (
        normalized &&
        (outputKind === 'json' || outputKind === 'html_document' || hasSlideClass(normalized))
      ) {
        await fs.writeFile(outputPath, `${normalized}\n`, 'utf8');
      }
    }

    if (result.code !== 0) {
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
  buildSpawnOptions,
  normalizeAgentOutputByKind,
};
