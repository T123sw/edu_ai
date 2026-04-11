const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs/promises');
const os = require('os');
const path = require('path');

process.env.PPT_DATA_DIR = path.join(os.tmpdir(), `ppt-service-initial-generation-tests-${Date.now()}`);

const exportModulePath = require.resolve('../src/lib/export-html-to-pptx');
const serviceModulePath = require.resolve('../src/services/ppt-service');
const originalExportModule = require.cache[exportModulePath];
const originalServiceModule = require.cache[serviceModulePath];

delete require.cache[serviceModulePath];
require.cache[exportModulePath] = {
  id: exportModulePath,
  filename: exportModulePath,
  loaded: true,
  exports: {
    exportHtmlToPptx: async ({ outputPath }) => {
      await fs.mkdir(path.dirname(outputPath), { recursive: true });
      await fs.writeFile(outputPath, 'fake-pptx', 'utf8');
    },
  },
};

const { PptService } = require('../src/services/ppt-service');
const { getRevisionPaths } = require('../src/store/job-store');

function createDeckMarkdown() {
  return [
    '# Deck',
    '- Title: One Shot Generation Test',
    '- Theme: heu_academic_elegant',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: cover',
    '- Title: Cover',
    '',
    '### Blocks',
    '- Lead: intro',
    '',
    '---',
    '',
    '## Slide 2',
    '- Role: toc',
    '- Title: Agenda',
    '',
    '### Blocks',
    '- Toc:',
    '  - Part 1',
    '  - Part 2',
    '',
    '---',
    '',
    '## Slide 3',
    '- Role: section',
    '- Title: Section One',
    '',
    '### Blocks',
    '- Lead: first section',
    '',
    '---',
    '',
    '## Slide 4',
    '- Role: content',
    '- Title: A1',
    '',
    '### Blocks',
    '- Bullets:',
    '  - x',
    '',
    '---',
    '',
    '## Slide 5',
    '- Role: section',
    '- Title: Section Two',
    '',
    '### Blocks',
    '- Lead: second section',
    '',
    '---',
    '',
    '## Slide 6',
    '- Role: content',
    '- Title: B1',
    '',
    '### Blocks',
    '- Bullets:',
    '  - y',
    '',
  ].join('\n');
}

test('initial generation runs the full deck in one shot even when sections exist', async () => {
  const runnerCalls = [];
  let queuedTask = null;
  const service = new PptService({
    queue: {
      enqueue(task) {
        queuedTask = task;
        return Promise.resolve();
      },
    },
    runner: {
      async run({ promptPath, outputPath, workspaceDir, prompt }) {
        runnerCalls.push({ promptPath, outputPath, workspaceDir, prompt });
        await fs.mkdir(path.dirname(outputPath), { recursive: true });
        await fs.writeFile(
          outputPath,
          '<div class="slide layout-cover"><div class="title-main">Cover</div></div>\n',
          'utf8'
        );
      },
    },
  });

  await service.init();
  const job = await service.createJob({
    content_markdown: createDeckMarkdown(),
    theme_id: 'heu_academic_elegant',
    metadata: {
      request_id: 'req-one-shot',
      timestamp: '2026-04-11T16:00:00+08:00',
      idempotency_key: 'idem-one-shot',
      user_id: 'tester',
    },
  });

  assert.ok(queuedTask, 'expected initial generation task to be queued');
  await queuedTask();

  const revisionPaths = getRevisionPaths(job.job_id, 'rev_0000');
  const persistedContent = await fs.readFile(revisionPaths.contentPath, 'utf8');

  assert.equal(runnerCalls.length, 1);
  assert.equal(runnerCalls[0].workspaceDir, revisionPaths.revisionDir);
  assert.equal(runnerCalls[0].promptPath, revisionPaths.promptPath);
  assert.equal(runnerCalls[0].outputPath, revisionPaths.fragmentPath);
  assert.match(persistedContent, /## Slide 1/);
  assert.match(persistedContent, /## Slide 6/);
  await assert.rejects(fs.access(path.join(revisionPaths.revisionDir, 'batches')));
});

test.after(async () => {
  if (originalExportModule) {
    require.cache[exportModulePath] = originalExportModule;
  } else {
    delete require.cache[exportModulePath];
  }

  if (originalServiceModule) {
    require.cache[serviceModulePath] = originalServiceModule;
  } else {
    delete require.cache[serviceModulePath];
  }

  await fs.rm(process.env.PPT_DATA_DIR, { recursive: true, force: true });
});
