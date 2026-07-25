import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  createPptxDownloader,
  sanitizePptxFilename,
} from './pptxDownload.ts';

test('sanitizes PPTX filenames for browsers and Windows', () => {
  assert.equal(
    sanitizePptxFilename('  算法：A/B? <导论>.  '),
    '算法_A_B_ _导论_',
  );
  assert.equal(sanitizePptxFilename('...'), '课件');
  assert.equal(sanitizePptxFilename('CON'), 'CON_');
});

test('guards duplicate downloads and releases state after success', async () => {
  let resolveBuild!: (blob: Blob) => void;
  let buildCount = 0;
  const saved: Array<{ blob: Blob; filename: string }> = [];
  const downloader = createPptxDownloader({
    build: async () => {
      buildCount += 1;
      return new Promise<Blob>((resolve) => {
        resolveBuild = resolve;
      });
    },
    save: (blob, filename) => saved.push({ blob, filename }),
  });

  const first = downloader.run({ title: '课程/一', scenes: [] });
  const duplicate = await downloader.run({ title: '课程/一', scenes: [] });

  assert.equal(duplicate, false);
  assert.equal(buildCount, 1);
  assert.equal(downloader.running, true);

  resolveBuild(new Blob(['pptx']));
  assert.equal(await first, true);
  assert.equal(downloader.running, false);
  assert.equal(saved.length, 1);
  assert.equal(saved[0].filename, '课程_一.pptx');
});

test('releases state and skips saving when export fails', async () => {
  let saveCount = 0;
  const downloader = createPptxDownloader({
    build: async () => {
      throw new Error('export failed');
    },
    save: () => {
      saveCount += 1;
    },
  });

  await assert.rejects(
    downloader.run({ title: '失败课件', scenes: [] }),
    /export failed/,
  );
  assert.equal(downloader.running, false);
  assert.equal(saveCount, 0);
});
