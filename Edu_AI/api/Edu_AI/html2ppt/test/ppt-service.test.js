const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs/promises');
const os = require('os');
const path = require('path');

process.env.PPT_DATA_DIR = path.join(os.tmpdir(), `ppt-service-tests-${Date.now()}`);

const { resolveThemeCss } = require('../src/domain/themes');
const { progressForPhase } = require('../src/domain/status');
const { extractSlides, replaceSlide, inferLayout, inferTitle } = require('../src/domain/fragment');
const { parseContentProtocol } = require('../src/domain/content-protocol');
const { buildManifest } = require('../src/domain/manifest');
const { localizeMediaAssets } = require('../src/lib/media-assets');
const { PptService } = require('../src/services/ppt-service');

function createService() {
  return new PptService({
    queue: {
      enqueue() {
        return Promise.resolve();
      },
    },
    runner: {},
  });
}

function createPayload(overrides = {}) {
  const overrideMetadata = overrides.metadata || {};
  const mergedMetadata = {
    request_id: 'req-1',
    timestamp: '2026-04-05T10:30:00+08:00',
    idempotency_key: 'idem-1',
    user_id: 'user-1',
    ...overrideMetadata,
  };

  return {
    content_markdown: [
      '# Deck',
      '- Title: 测试',
      '- Theme: heu_academic_elegant',
      '',
      '---',
      '',
      '## Slide 1',
      '- Role: cover',
      '- Title: 测试',
      '',
      '### Blocks',
      '- Lead: 内容',
      '',
    ].join('\n'),
    theme_id: 'heu_academic_elegant',
    metadata: mergedMetadata,
    ...overrides,
    metadata: mergedMetadata,
  };
}

test('theme registry resolves known theme ids', () => {
  const resolved = resolveThemeCss('heu_academic_elegant');
  assert.match(resolved, /theme-heu-academic-elegant\.css$/);
});

test('phase progress mapping stays stable', () => {
  assert.equal(progressForPhase('accepted'), 0);
  assert.equal(progressForPhase('generating_slides'), 40);
  assert.equal(progressForPhase('completed'), 100);
});

test('fragment helpers extract, replace, infer title and layout', () => {
  const source =
    '<div class="slide layout-standard-text"><div class="title-main">第一页</div></div>\n' +
    '<div class="slide"><div class="cards-grid"></div><div class="title-main">第二页</div></div>';

  const slides = extractSlides(source);
  assert.equal(slides.length, 2);
  assert.equal(inferTitle(slides[0]), '第一页');
  assert.equal(inferLayout(slides[1]), 'card-layout');

  const replaced = replaceSlide(
    source,
    2,
    '<div class="slide layout-thanks"><div class="title-main">致谢</div></div>'
  );
  const nextSlides = extractSlides(replaced);
  assert.equal(nextSlides.length, 2);
  assert.equal(inferTitle(nextSlides[1]), '致谢');
  assert.equal(inferLayout(nextSlides[1]), 'thanks');
});

test('fragment helpers infer new media layouts', () => {
  assert.equal(
    inferLayout('<div class="slide layout-image-text"><div class="title-main">图文页</div></div>'),
    'media-left-text-right'
  );
  assert.equal(
    inferLayout('<div class="slide layout-text-media"><div class="title-main">文图页</div></div>'),
    'text-left-media-right'
  );
  assert.equal(
    inferLayout('<div class="slide layout-media-focus"><div class="title-main">焦点页</div></div>'),
    'media-focus'
  );
});

test('manifest generation summarizes slides', () => {
  const fragment =
    '<div class="slide layout-cover"><div class="title-main">封面</div></div>\n' +
    '<div class="slide layout-toc"><div class="toc-title-zh">目录</div></div>';

  const manifest = buildManifest({
    jobId: 'job-1',
    revisionId: 'rev_0000',
    themeId: 'heu_academic_elegant',
    fragmentHtml: fragment,
  });

  assert.equal(manifest.slide_count, 2);
  assert.deepEqual(manifest.slides[0], {
    slide_index: 1,
    title: '封面',
    layout: 'cover',
  });
});

test('content protocol parses pure markdown slide blocks', () => {
  const parsed = parseContentProtocol([
    '# Deck',
    '- Title: 测试文档',
    '- Theme: heu_academic_elegant',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 图片页',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 要点一',
    '- Media:',
    '  - Kind: image',
    '  - URL: https://example.com/demo.png',
    '  - Caption: 图注',
    '',
  ].join('\n'));

  assert.equal(parsed.deck.title, '测试文档');
  assert.equal(parsed.slides.length, 1);
  assert.equal(parsed.slides[0].role, 'content');
  assert.deepEqual(parsed.slides[0].blockTypes, ['Bullets', 'Media']);
  assert.equal(parsed.slides[0].mediaBlocks[0].fields.URL, 'https://example.com/demo.png');
});

test('media assets localize to revision-relative paths', async () => {
  const mediaDir = path.join(process.env.PPT_DATA_DIR, 'media-assets-test');
  const markdown = [
    '# Deck',
    '- Title: 媒体测试',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 图片页',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 要点一',
    '- Media:',
    '  - Kind: image',
    '  - URL: data:image/png;base64,iVBORw0KGgo=',
    '  - Caption: 图注',
    '',
  ].join('\n');

  const localized = await localizeMediaAssets(markdown, { mediaDir });

  assert.match(localized.runtimeMarkdown, /Local-Path: \.\/media\/slide-01-main\.png/);
  const files = await fs.readdir(mediaDir);
  assert.ok(files.includes('slide-01-main.png'));
});

test('media assets support repository-relative local files', async () => {
  const mediaDir = path.join(process.env.PPT_DATA_DIR, 'media-assets-local-test');
  const markdown = [
    '# Deck',
    '- Title: 本地媒体测试',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 本地图像页',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 要点一',
    '- Media:',
    '  - Kind: image',
    '  - URL: assets/test/1.jpg',
    '  - Caption: 本地图像',
    '',
  ].join('\n');

  const localized = await localizeMediaAssets(markdown, { mediaDir });

  assert.match(localized.runtimeMarkdown, /Local-Path: \.\/media\/slide-01-main\.jpg/);
  const files = await fs.readdir(mediaDir);
  assert.ok(files.includes('slide-01-main.jpg'));
});

test('service createJob is idempotent for same payload and rejects conflicting reuse', async () => {
  const service = createService();
  await service.init();

  const payload = createPayload();
  const first = await service.createJob(payload);
  const second = await service.createJob(payload);

  assert.equal(first.job_id, second.job_id);

  await assert.rejects(
    () =>
      service.createJob(
        createPayload({
          theme_id: 'heu_academic_basic',
          metadata: { idempotency_key: 'idem-1' },
        })
      ),
    (error) => error.statusCode === 409
  );
});

test('service validates revision payload before queueing', async () => {
  const service = createService();
  await service.init();

  await assert.rejects(
    () => service.createRevision('missing-job', { mode: 'multi_slide', target_slides: [1] }),
    (error) => error.code === 'INVALID_REVISION_MODE'
  );

  await assert.rejects(
    () =>
      service.createJob(
        createPayload({
          content_markdown: 'not a valid content protocol document',
          metadata: { idempotency_key: 'idem-invalid' },
        })
      ),
    (error) => error.code === 'INVALID_CONTENT_FORMAT'
  );
});

test.after(async () => {
  await fs.rm(process.env.PPT_DATA_DIR, { recursive: true, force: true });
});
