const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('fs/promises');
const os = require('os');
const path = require('path');

process.env.PPT_DATA_DIR = path.join(os.tmpdir(), `ppt-service-tests-${Date.now()}`);

const { resolveThemeCss } = require('../src/domain/themes');
const { progressForPhase } = require('../src/domain/status');
const { extractSlides, replaceSlide, inferLayout, inferTitle } = require('../src/domain/fragment');
const { normalizeSlideDecorations } = require('../src/domain/slide-decor');
const { parseContentProtocol } = require('../src/domain/content-protocol');
const { buildManifest } = require('../src/domain/manifest');
const { localizeMediaAssets } = require('../src/lib/media-assets');
const { buildStandaloneHtmlFromFragment } = require('../src/lib/build-standalone-html');
const {
  normalizeRepoAssetPaths,
  normalizeVideoSourceTags,
  runChromeExport,
} = require('../src/lib/export-html-to-pptx');
const {
  PptService,
  applyRuntimePromptPaths,
  runInitialSlideGeneration,
} = require('../src/services/ppt-service');

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

test('chrome export is bounded by timeout and terminates the browser process', async () => {
  const signals = [];
  const chrome = new EventEmitter();
  chrome.stdout = new EventEmitter();
  chrome.stderr = new EventEmitter();
  chrome.kill = (signal) => {
    signals.push(signal);
    setImmediate(() => chrome.emit('close', null));
    return true;
  };

  const result = await runChromeExport('http://127.0.0.1:9/deck.html', {
    timeoutMs: 5,
    spawnChrome: () => chrome,
    chromePathOverride: process.execPath,
  });

  assert.equal(result.timedOut, true);
  assert.equal(result.code, null);
  assert.deepEqual(signals, ['SIGTERM']);
});

test('chrome export gives the page the full configured export window', async () => {
  let seenArgs = [];
  const chrome = new EventEmitter();
  chrome.stdout = new EventEmitter();
  chrome.stderr = new EventEmitter();
  chrome.kill = () => true;

  const result = await runChromeExport('http://127.0.0.1:9/deck.html', {
    timeoutMs: 12345,
    spawnChrome: (executable, args) => {
      seenArgs = args;
      setImmediate(() => chrome.emit('close', 0, null));
      return chrome;
    },
    chromePathOverride: process.execPath,
  });

  assert.equal(result.timedOut, false);
  assert.ok(seenArgs.includes('--virtual-time-budget=12345'));
  assert.ok(!seenArgs.includes('--virtual-time-budget=60000'));
});

test('export html preparation normalizes nested video source tags', () => {
  const input = [
    '<video class="media-element" controls="">',
    '  <source src="./media/demo.mp4" type="video/mp4">',
    '</video>',
  ].join('\n');

  const result = normalizeVideoSourceTags(input);

  assert.equal(result.changed, true);
  assert.match(result.html, /<video\b[^>]*src="\.\/media\/demo\.mp4"[^>]*>/);
  assert.doesNotMatch(result.html, /<source\b/);
});

test('export html preparation normalizes relative brand asset URLs', () => {
  const input =
    '<div class="slide-brand"><img class="slide-brand-image" src="assets/HEU/heu-logo.png" alt="哈尔滨工程大学logo"></div>';

  const result = normalizeRepoAssetPaths(input);

  assert.equal(result.changed, true);
  assert.match(result.html, /src="\/assets\/HEU\/heu-logo\.png"/);
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
  assert.equal(
    inferLayout('<div class="slide layout-standard-text-structured"><div class="title-main">结构化页</div></div>'),
    'standard-text-structured'
  );
});

test('fragment helpers infer advanced teaching layouts', () => {
  assert.equal(
    inferLayout('<div class="slide layout-comparison-vs-panels"><div class="title-main">架构对比</div></div>'),
    'comparison-vs-panels'
  );
  assert.equal(
    inferLayout('<div class="slide layout-execution-pipeline"><div class="title-main">执行链路</div></div>'),
    'execution-pipeline'
  );
  assert.equal(
    inferLayout('<div class="slide layout-pillar-cards-banner"><div class="title-main">三大基石</div></div>'),
    'pillar-cards-banner'
  );
  assert.equal(
    inferLayout('<div class="slide layout-capability-map-grid"><div class="title-main">能力图谱</div></div>'),
    'capability-map-grid'
  );
});

test('slide decoration normalizer injects deterministic ppt-safe decor', () => {
  const source = [
    [
      '<div class="slide layout-cover">',
      '<div class="title-main">封面</div>',
      '<div class="cover-subtitle">',
      '<div class="cover-subtitle-kicker">Topic Focus</div>',
      '<div class="cover-subtitle-text">研究范围</div>',
      '</div>',
      '</div>',
    ].join(''),
    '<div class="slide layout-standard-text"><div class="title-main">正文</div></div>',
  ].join('\n');

  const decorated = normalizeSlideDecorations(source);
  const redecorated = normalizeSlideDecorations(decorated);

  assert.equal(
    (decorated.match(/class="[^"]*\bslide-safe-decor\b/g) || []).length,
    2
  );
  assert.equal(
    (decorated.match(/class="[^"]*\bslide-top-rule\b/g) || []).length,
    2
  );
  assert.doesNotMatch(decorated, /slide-top-accent/);
  assert.equal(
    (decorated.match(/class="[^"]*\bslide-header-hairline\b/g) || []).length,
    2
  );
  assert.equal(
    (decorated.match(/class="[^"]*\bslide-header-mark\b/g) || []).length,
    4
  );
  assert.doesNotMatch(decorated, /slide-header-mark-right/);
  assert.equal(
    (decorated.match(/class="[^"]*\bslide-header-mark-accent\b/g) || []).length,
    2
  );
  assert.doesNotMatch(decorated, /slide-corner-mark/);
  assert.equal(
    (decorated.match(/class="[^"]*\bcover-subtitle-accent\b/g) || []).length,
    1
  );
  assert.equal(redecorated, decorated);
});

test('slide decoration normalizer replaces old thanks decor with ppt-safe decor', () => {
  const source = [
    '<div class="slide layout-thanks">',
    '<div class="thanks-orbit thanks-orbit-primary"></div>',
    '<div class="thanks-accent-line thanks-accent-line-top"></div>',
    '<div class="thanks-content"><div class="title-main">Q&A</div></div>',
    '</div>',
  ].join('');

  const decorated = normalizeSlideDecorations(source);

  assert.doesNotMatch(decorated, /thanks-orbit|thanks-accent-line/);
  assert.match(decorated, /class="[^"]*\bthanks-safe-decor\b/);
  assert.match(decorated, /class="[^"]*\bthanks-safe-line\b/);
  assert.doesNotMatch(decorated, /thanks-safe-panel|thanks-safe-corner|footer-area|slide-brand/);
  assert.doesNotMatch(decorated, /slide-top-rule|slide-top-accent/);
});

test('standalone html build normalizes ppt-safe decorations as a safety net', async () => {
  const workDir = path.join(process.env.PPT_DATA_DIR, 'standalone-decoration-test');
  await fs.mkdir(workDir, { recursive: true });
  const fragmentPath = path.join(workDir, 'deck.fragment.html');
  const outputPath = path.join(workDir, 'deck.html');

  await fs.writeFile(
    fragmentPath,
    [
      '<div class="slide layout-cover">',
      '<div class="title-main">封面</div>',
      '<div class="cover-subtitle">',
      '<div class="cover-subtitle-kicker">Topic Focus</div>',
      '<div class="cover-subtitle-text">研究范围</div>',
      '</div>',
      '</div>',
    ].join(''),
    'utf8'
  );

  buildStandaloneHtmlFromFragment({
    fragmentPath,
    outputPath,
    themeId: 'heu_academic_elegant',
  });

  const output = await fs.readFile(outputPath, 'utf8');
  const normalizedFragment = await fs.readFile(fragmentPath, 'utf8');
  assert.match(output, /class="slide-safe-decor"/);
  assert.doesNotMatch(output, /class="slide-top-accent"/);
  assert.match(output, /class="slide-header-hairline"/);
  assert.match(output, /class="[^"]*\bslide-header-mark-accent\b/);
  assert.match(output, /class="cover-subtitle-accent"/);
  assert.match(normalizedFragment, /class="slide-safe-decor"/);
  assert.match(normalizedFragment, /class="slide-header-hairline"/);
  assert.match(normalizedFragment, /class="cover-subtitle-accent"/);
});

test('thanks template uses real HEU logo instead of placeholder text', async () => {
  const template = await fs.readFile(path.join(__dirname, '../format/thanks-body.html'), 'utf8');
  const layoutCss = await fs.readFile(path.join(__dirname, '../format/layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');
  const basicThemeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-basic.css'), 'utf8');

  assert.match(template, /class="thanks-logo-image"/);
  assert.match(template, /src="\/assets\/HEU\/heu-logo\.png"/);
  assert.match(template, /class="thanks-note"/);
  assert.doesNotMatch(template, /thanks-orbit|thanks-accent-line/);
  assert.match(layoutCss, /\.slide-safe-decor\s*{/);
  assert.match(layoutCss, /\.thanks-safe-decor\s*{/);
  assert.doesNotMatch(
    layoutCss,
    /\.slide > \*:not\(\.slide-safe-decor\):not\(\.thanks-safe-decor\)\s*{[^}]*position:/s
  );
  assert.match(layoutCss, /\.slide-header-hairline\s*{[^}]*top:\s*44px[^}]*left:\s*230px/s);
  assert.match(layoutCss, /\.slide-header-mark-accent\s*{[^}]*left:\s*158px/s);
  assert.doesNotMatch(layoutCss, /\.slide-header-mark-right\s*{/);
  assert.doesNotMatch(layoutCss, /\.slide-corner-mark\s*{/);
  assert.match(themeCss, /\.slide-top-rule\s*{[^}]*background-color:\s*var\(--color-primary\)/s);
  assert.doesNotMatch(layoutCss, /\.slide-top-accent\s*{/);
  assert.doesNotMatch(themeCss, /\.slide-top-accent\s*{[^}]*background-color:\s*var\(--color-accent\)/s);
  assert.match(themeCss, /\.slide-header-mark-accent\s*{[^}]*background-color:\s*var\(--color-accent\)/s);
  assert.match(basicThemeCss, /\.slide-top-rule\s*{[^}]*background-color:\s*var\(--color-primary\)/s);
  assert.doesNotMatch(basicThemeCss, /\.slide::before|\.slide::after/);
  assert.match(layoutCss, /\.layout-thanks \.title-main\s*{[^}]*width:\s*420px/s);
  assert.match(layoutCss, /\.layout-thanks \.title-main\s*{[^}]*white-space:\s*nowrap/s);
  assert.match(layoutCss, /\.layout-thanks \.title-main\s*{[^}]*text-align:\s*center/s);
  assert.match(layoutCss, /\.layout-thanks \.thanks-content\s*{[^}]*padding-top:\s*72px/s);
  assert.match(layoutCss, /\.layout-thanks \.title-en\s*{[^}]*width:\s*360px/s);
  assert.match(layoutCss, /\.layout-thanks \.title-en\s*{[^}]*white-space:\s*nowrap/s);
  assert.match(layoutCss, /\.layout-thanks \.title-en\s*{[^}]*text-align:\s*center/s);
  assert.match(layoutCss, /\.layout-thanks \.title-en\s*{[^}]*margin-bottom:\s*22px/s);
  assert.doesNotMatch(layoutCss, /\.thanks-safe-panel-primary|\.thanks-safe-panel-secondary|\.thanks-safe-corner-right/);
  assert.doesNotMatch(template, /logo-placeholder|HEU LOGO/);
  assert.doesNotMatch(template, /contact-info|info-item/);
});

test('cover template uses dedicated cover subtitle structure', async () => {
  const template = await fs.readFile(path.join(__dirname, '../format/cover-body.html'), 'utf8');
  const layoutCss = await fs.readFile(path.join(__dirname, '../format/layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');

  assert.match(template, /class="slide layout-cover"/);
  assert.match(template, /class="cover-subtitle"/);
  assert.match(template, /class="cover-subtitle-accent"/);
  assert.match(template, /class="cover-subtitle-kicker"/);
  assert.match(template, /class="cover-subtitle-text"/);
  assert.match(layoutCss, /\.cover-subtitle-accent\s*{/);
  assert.match(themeCss, /\.cover-subtitle-accent\s*{/);
  assert.doesNotMatch(themeCss, /\.cover-subtitle\s*{[^}]*border-left:/s);
  assert.doesNotMatch(template, /quote-box|surface-card/);
});

test('classic standard-text template stays low-density and flat', async () => {
  const template = await fs.readFile(path.join(__dirname, '../format/standard-text-body.html'), 'utf8');

  assert.doesNotMatch(template, /<ol\b|<ul\b/);
  assert.doesNotMatch(template, /process-track|process-grid|comparison-grid|sidebar-rail|dual-panel-aside/);
});

test('process templates separate short track, four-step grid, and five-step list examples', async () => {
  const trackTemplate = await fs.readFile(path.join(__dirname, '../format/standard-text-process-body.html'), 'utf8');
  const gridTemplate = await fs.readFile(path.join(__dirname, '../format/standard-text-process-grid-body.html'), 'utf8');
  const listTemplate = await fs.readFile(path.join(__dirname, '../format/standard-text-process-list-body.html'), 'utf8');

  assert.match(trackTemplate, /class="process-track"/);
  assert.match(trackTemplate, /class="process-divider"/);
  assert.doesNotMatch(trackTemplate, /class="process-grid"/);

  assert.match(gridTemplate, /class="process-grid"/);
  assert.equal((gridTemplate.match(/class="[^"]*\bsurface-card\b[^"]*\bprocess-step\b[^"]*"/g) || []).length, 4);
  assert.doesNotMatch(gridTemplate, /class="process-divider"/);
  assert.doesNotMatch(gridTemplate, /process-step-wide/);

  assert.match(listTemplate, /class="[^"]*\bprocess-list\b/);
  assert.equal((listTemplate.match(/class="process-list-item"/g) || []).length, 5);
  assert.doesNotMatch(listTemplate, /class="process-grid"/);
});

test('advanced teaching layout templates are registered and ppt-safe', async () => {
  const prompt = await fs.readFile(path.join(__dirname, '../html-generation-entry-prompt.md'), 'utf8');
  const contracts = await fs.readFile(path.join(__dirname, '../layout-contracts.md'), 'utf8');
  const layoutCss = await fs.readFile(path.join(__dirname, '../format/layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');
  const layoutNames = [
    'comparison-vs-panels',
    'execution-pipeline',
    'pillar-cards-banner',
    'capability-map-grid',
  ];

  for (const layoutName of layoutNames) {
    const template = await fs.readFile(
      path.join(__dirname, `../format/${layoutName}-body.html`),
      'utf8'
    );
    const className = `layout-${layoutName}`;

    assert.match(template, new RegExp(`class="slide ${className}"`));
    assert.match(template, /class="header-area"/);
    assert.match(template, /class="title-divider"/);
    assert.doesNotMatch(template, /<ul\b|<ol\b|::before|::after|style="/);
    assert.match(prompt, new RegExp(`format/${layoutName}-body\\.html`));
    assert.match(prompt, new RegExp(layoutName));
    assert.match(contracts, new RegExp(layoutName));
  }

  assert.match(layoutCss, /\.layout-comparison-vs-panels \.vs-badge\s*{/);
  assert.match(layoutCss, /\.layout-execution-pipeline \.pipeline-card\s*{/);
  assert.match(layoutCss, /\.layout-pillar-cards-banner \.pillar-summary-bar\s*{/);
  assert.match(layoutCss, /\.layout-capability-map-grid \.capability-hero\s*{/);
  assert.match(themeCss, /\.vs-badge\s*{/);
  assert.match(themeCss, /\.pipeline-number\s*{/);
  assert.match(themeCss, /\.pillar-icon-box\s*{/);
  assert.match(themeCss, /\.capability-hero\s*{/);
  const vsTemplate = await fs.readFile(
    path.join(__dirname, '../format/comparison-vs-panels-body.html'),
    'utf8'
  );
  assert.doesNotMatch(vsTemplate, /vs-spine/);
  assert.doesNotMatch(layoutCss, /\.vs-spine\s*{/);
  assert.doesNotMatch(themeCss, /\.vs-spine\s*{/);
  assert.doesNotMatch(prompt, /vs-spine/);
  assert.doesNotMatch(contracts, /vs-spine/);
  const pipelineTemplate = await fs.readFile(
    path.join(__dirname, '../format/execution-pipeline-body.html'),
    'utf8'
  );
  assert.doesNotMatch(pipelineTemplate, /▶/);
  assert.match(pipelineTemplate, /class="pipeline-arrow-svg"/);
  assert.doesNotMatch(layoutCss, /\.pipeline-number\s*{[^}]*position:\s*absolute/s);
  assert.doesNotMatch(layoutCss, /\.pipeline-number\s*{[^}]*top:\s*-/s);
  assert.match(contracts, /不要连续使用 `comparison-vs-panels`|不要连续使用同一种增强版式/s);
});

test('card layout uses profile card styling and the prompt does not expose sidebar', async () => {
  const prompt = await fs.readFile(path.join(__dirname, '../html-generation-entry-prompt.md'), 'utf8');
  const contracts = await fs.readFile(path.join(__dirname, '../layout-contracts.md'), 'utf8');
  const template = await fs.readFile(path.join(__dirname, '../format/card-layout-body.html'), 'utf8');
  const layoutCss = await fs.readFile(path.join(__dirname, '../format/layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');

  assert.doesNotMatch(prompt, /standard-text-sidebar|format\/standard-text-sidebar-body\.html/);
  assert.doesNotMatch(contracts, /standard-text-sidebar|format\/standard-text-sidebar-body\.html/);
  assert.equal((template.match(/class="surface-card"/g) || []).length, 3);
  assert.equal((template.match(/class="card-top-accent"/g) || []).length, 3);
  assert.equal((template.match(/class="card-ghost-number"/g) || []).length, 3);
  assert.doesNotMatch(layoutCss, /\.cards-grid > \.surface-card::before\s*{/);
  assert.doesNotMatch(layoutCss, /\.cards-grid > \.surface-card::after\s*{/);
  assert.doesNotMatch(layoutCss, /content:\s*counter\(feature-card,\s*decimal-leading-zero\)/);
  assert.match(layoutCss, /\.cards-grid > \.surface-card \.card-top-accent\s*{/);
  assert.match(layoutCss, /\.cards-grid > \.surface-card \.card-ghost-number\s*{/);
  assert.match(layoutCss, /\.cards-grid > \.surface-card \.card-title\s*{[^}]*border-bottom:/s);
  assert.match(themeCss, /\.cards-grid > \.surface-card \.card-ghost-number\s*{[^}]*color:\s*#F4F7FA/s);
  assert.doesNotMatch(themeCss, /\.cards-grid > \.surface-card \.card-ghost-number\s*{[^}]*rgba\(/s);
  assert.match(contracts, /card-top-accent/);
  assert.match(contracts, /card-ghost-number/);
});

test('media focus uses export-safe split media panel and cover cropping', async () => {
  const prompt = await fs.readFile(path.join(__dirname, '../html-generation-entry-prompt.md'), 'utf8');
  const contracts = await fs.readFile(path.join(__dirname, '../layout-contracts.md'), 'utf8');
  const template = await fs.readFile(path.join(__dirname, '../format/media-focus-body.html'), 'utf8');
  const layoutCss = await fs.readFile(path.join(__dirname, '../format/layout.css'), 'utf8');

  assert.match(template, /class="media-focus-image-panel"/);
  assert.match(template, /class="media-focus-content-panel"/);
  assert.doesNotMatch(template, /media-focus-summary|media-card-focus/);
  assert.match(layoutCss, /\.slide\.layout-media-focus\s*{[^}]*display:\s*block/s);
  assert.doesNotMatch(layoutCss, /\.layout-media-focus\s*{[^}]*display:\s*grid/s);
  assert.doesNotMatch(layoutCss, /\.layout-media-focus\s*{[^}]*grid-template-columns/s);
  assert.match(layoutCss, /\.slide\.layout-media-focus\s*{[^}]*padding:\s*0/s);
  assert.match(layoutCss, /\.media-focus-image-panel\s*{[^}]*position:\s*absolute[^}]*left:\s*0[^}]*top:\s*0[^}]*width:\s*60%/s);
  assert.match(layoutCss, /\.media-focus-image-panel\s*{[^}]*overflow:\s*hidden/s);
  assert.match(layoutCss, /\.media-focus-content-panel\s*{[^}]*position:\s*absolute[^}]*left:\s*60%[^}]*top:\s*0[^}]*width:\s*40%/s);
  assert.match(layoutCss, /\.layout-media-focus \.media-element\s*{[^}]*object-fit:\s*cover/s);
  assert.match(prompt, /media-focus.*60%\s*\/\s*40%|60%\s*\/\s*40%.*media-focus/s);
  assert.match(prompt, /绝对定位|左右分栏/);
  assert.match(prompt, /object-fit:\s*cover|cover 裁切/);
  assert.doesNotMatch(prompt, /media-focus`：大媒体 \+ 下方一句结论/);
  assert.match(prompt, /不要.*横幅式|禁止.*横幅式|横幅式.*不要|banner/i);
  assert.match(contracts, /media-focus-image-panel/);
  assert.match(contracts, /media-focus-content-panel/);
  assert.doesNotMatch(contracts, /media-focus-summary/);
  assert.match(contracts, /不要.*横幅式|禁止.*横幅式|横幅式.*不要|banner/i);
});

test('capability map hero number is lighter in both HEU themes', async () => {
  const elegantThemeCss = await fs.readFile(
    path.join(__dirname, '../style/theme-heu-academic-elegant.css'),
    'utf8'
  );
  const basicThemeCss = await fs.readFile(
    path.join(__dirname, '../style/theme-heu-academic-basic.css'),
    'utf8'
  );

  assert.match(elegantThemeCss, /\.capability-hero-number\s*{[^}]*color:\s*#0A3D70/s);
  assert.match(basicThemeCss, /\.capability-hero-number\s*{[^}]*color:\s*#0A3D70/s);
  assert.doesNotMatch(elegantThemeCss, /\.capability-hero-number\s*{[^}]*rgba\(/s);
  assert.doesNotMatch(basicThemeCss, /\.capability-hero-number\s*{[^}]*rgba\(/s);
});

test('dual panel routing is reserved for substantial insight plus argument pages', async () => {
  const prompt = await fs.readFile(path.join(__dirname, '../html-generation-entry-prompt.md'), 'utf8');
  const contracts = await fs.readFile(path.join(__dirname, '../layout-contracts.md'), 'utf8');

  assert.match(prompt, /standard-text-dual-panel[\s\S]*1 到 2 个完整 insight card[\s\S]*quote \+ 3 条以上论证/);
  assert.match(prompt, /一个核心判断 \+ 3 到 4 条标签解释[\s\S]*standard-text-structured|standard-text-structured[\s\S]*一个核心判断 \+ 3 到 4 条标签解释/);
  assert.match(contracts, /standard-text-dual-panel[\s\S]*1 到 2 个完整 insight card[\s\S]*quote \+ 3 条以上论证/);
});

test('structured text template handles dense examples with one panel instead of odd card grids', async () => {
  const template = await fs.readFile(path.join(__dirname, '../format/standard-text-structured-body.html'), 'utf8');

  assert.match(template, /class="slide layout-standard-text-structured"/);
  assert.match(template, /class="structured-lead"/);
  assert.match(template, /class="[^"]*\bstructured-panel\b/);
  assert.match(template, /class="structured-section"/);
  assert.match(template, /class="structured-flow"/);
  assert.doesNotMatch(template, /structured-grid|structured-card|sidebar-card|sidebar-points|quote-box/);
});

test('generation prompt routes dense workflow content away from sidebar and avoids thanks double brand', async () => {
  const prompt = await fs.readFile(path.join(__dirname, '../html-generation-entry-prompt.md'), 'utf8');
  const layoutCss = await fs.readFile(path.join(__dirname, '../format/layout.css'), 'utf8');
  const textMediaTemplate = await fs.readFile(
    path.join(__dirname, '../format/text-left-media-right-body.html'),
    'utf8'
  );

  assert.match(prompt, /\{\{CONTENT_PATH\}\}/);
  assert.match(prompt, /\{\{THEME_CSS_PATH\}\}/);
  assert.doesNotMatch(prompt, /\/Users\/sun\/code\/aippt\/html2ppt/);
  assert.match(prompt, /standard-text-structured/);
  assert.match(prompt, /含示例流程|示例流程/);
  assert.doesNotMatch(prompt, /standard-text-sidebar/);
  assert.match(prompt, /不要把 3 个或 5 个信息块做成独立卡片网格/);
  assert.match(prompt, /5 步|五步/);
  assert.match(prompt, /thanks 页不要再插入右上角 `slide-brand`/);
  assert.match(prompt, /不要输出 `contact-info`|不输出 `contact-info`/);
  assert.match(prompt, /thanks-note/);
  assert.match(prompt, /Q&A.*单行|单行.*Q&A/);
  assert.match(prompt, /装饰.*系统后处理注入|系统后处理.*装饰/);
  assert.match(prompt, /不要手写.*slide-safe-decor|不要.*slide-safe-decor/);
  assert.match(prompt, /页脚.*只保留.*页码|只保留.*右下角页码/);
  assert.match(prompt, /structured-flow-step.*短动作|流程.*短动作/);
  assert.match(prompt, /没有.*Local-Poster-Path.*不要输出.*poster|不要输出.*poster.*没有.*Local-Poster-Path/s);
  assert.doesNotMatch(layoutCss, /\.slide::before|\.slide::after/);
  assert.doesNotMatch(textMediaTemplate, /\bposter=/);
  assert.doesNotMatch(textMediaTemplate, /1_poster\.jpg/);
});

test('layout css keeps shared base rules centralized', async () => {
  const layoutCss = await fs.readFile(path.join(__dirname, '../format/layout.css'), 'utf8');

  assert.equal((layoutCss.match(/^\.slide\s*{/gm) || []).length, 1);
  assert.equal((layoutCss.match(/^\.header-area\s*{/gm) || []).length, 1);
  assert.equal((layoutCss.match(/^\.title-divider\s*{/gm) || []).length, 1);
});

test('footer chrome is minimized to page number only', async () => {
  const layoutCss = await fs.readFile(path.join(__dirname, '../format/layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');
  const basicThemeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-basic.css'), 'utf8');

  assert.match(layoutCss, /\.footer-area\s*{[^}]*justify-content:\s*flex-end/s);
  assert.match(layoutCss, /\.footer-logo\s*{[^}]*display:\s*none/s);
  assert.doesNotMatch(themeCss, /\.footer-area\s*{[^}]*border-top/s);
  assert.doesNotMatch(themeCss, /\.footer-area\s*{[^}]*padding-top/s);
  assert.doesNotMatch(basicThemeCss, /\.footer-area\s*{[^}]*border-top/s);
});

test('body templates only include page number footers', async () => {
  const formatDir = path.join(__dirname, '../format');
  const files = (await fs.readdir(formatDir)).filter((fileName) => fileName.endsWith('-body.html'));

  for (const fileName of files) {
    const template = await fs.readFile(path.join(formatDir, fileName), 'utf8');
    assert.doesNotMatch(template, /footer-logo/, `${fileName} should not include footer-logo`);
  }
});

test('elegant theme uses lighter teaching deck rhythm', async () => {
  const layoutCss = await fs.readFile(path.join(__dirname, '../format/layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');

  assert.match(themeCss, /\.title-main\s*{[^}]*font-size:\s*50px[^}]*letter-spacing:\s*0/s);
  assert.match(themeCss, /\.layout-cover \.title-main\s*{[^}]*font-size:\s*64px/s);
  assert.match(themeCss, /\.surface-card\s*{[^}]*border-radius:\s*8px[^}]*box-shadow:\s*var\(--shadow-sm\)/s);
  assert.match(layoutCss, /\.layout-standard-text-comparison \.content-area\s*{[^}]*align-items:\s*flex-start/s);
  assert.match(layoutCss, /\.layout-standard-text-structured \.content-area\s*{[^}]*justify-content:\s*flex-start/s);
  assert.match(layoutCss, /\.layout-standard-text-process \.content-area\s*{[^}]*justify-content:\s*flex-start/s);
});

test('prompt and contracts require teaching display compression without dropping blocks', async () => {
  const prompt = await fs.readFile(path.join(__dirname, '../html-generation-entry-prompt.md'), 'utf8');
  const contracts = await fs.readFile(path.join(__dirname, '../layout-contracts.md'), 'utf8');

  assert.match(prompt, /显示层.*压缩|压缩.*显示层/);
  assert.match(prompt, /Notes|讲稿/);
  assert.match(prompt, /Definition|定义.*Compare|对比.*Process|流程.*Analogy|类比.*Takeaway|结论/s);
  assert.match(prompt, /每个.*Block.*可见承载|Block.*可见承载/);
  assert.doesNotMatch(prompt, /不为了适配版式而删减长要点、压缩示例流程/);

  assert.match(contracts, /教学表达|显示文案/);
  assert.match(contracts, /Definition|定义.*Compare|对比.*Process|流程.*Analogy|类比.*Takeaway|结论/s);
  assert.ok(contracts.split('\n').length < 700);
});

test('layout quality report flags missing visible block markers', () => {
  const { buildLayoutQualityReport } = require('../src/domain/layout-quality');
  const contentMarkdown = [
    '# Deck',
    '- Title: 测试',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 什么是 AI Skills？',
    '',
    '### Blocks',
    '- Bullets:',
    '  - **核心定义**：智能体完成特定任务的专项能力。',
    '- Comparison:',
    '  - Left-Title: 按功能领域划分',
    '  - Right-Title: 按集成复杂度划分',
    '',
  ].join('\n');
  const fragmentHtml = [
    '<div class="slide layout-standard-text-comparison">',
    '<div class="title-main">什么是 AI Skills？</div>',
    '<div class="comparison-card"><div class="card-title">按功能领域划分</div></div>',
    '<div class="comparison-card"><div class="card-title">按集成复杂度划分</div></div>',
    '</div>',
  ].join('');

  const report = buildLayoutQualityReport({ contentMarkdown, fragmentHtml });

  assert.equal(report.slide_count, 1);
  assert.equal(report.warning_count, 1);
  assert.equal(report.warnings[0].code, 'CONTENT_MARKER_MISSING');
  assert.match(report.warnings[0].message, /核心定义/);
});

test('initial deck generation runs one agent task per slide in parallel and merges in order', async () => {
  const workDir = path.join(process.env.PPT_DATA_DIR, 'parallel-generation-test');
  const revisionPaths = {
    revisionDir: workDir,
    fragmentPath: path.join(workDir, 'deck.fragment.html'),
    promptPath: path.join(workDir, 'agent-prompt.txt'),
  };
  const runtimeContent = [
    '# Deck',
    '- Title: 并行测试',
    '- Theme: heu_academic_elegant',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: cover',
    '- Title: 封面',
    '',
    '### Blocks',
    '- Lead: 开场',
    '',
    '---',
    '',
    '## Slide 2',
    '- Role: content',
    '- Title: 内容页',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 要点',
    '',
  ].join('\n');
  const calls = [];
  const releases = [];
  const runner = {
    async run({ promptPath, outputPath, prompt }) {
      const slideIndex = Number((outputPath.match(/slide-(\d+)\.fragment\.html$/) || [])[1]);
      calls.push({ promptPath, outputPath, prompt });
      await new Promise((resolve) => {
        releases[slideIndex] = resolve;
      });
      await fs.writeFile(
        outputPath,
        `<div class="slide layout-standard-text"><div class="title-main">第 ${slideIndex} 页</div></div>\n`,
        'utf8'
      );
    },
  };

  const generation = runInitialSlideGeneration({
    runner,
    runtimeContent,
    revisionPaths,
    themeId: 'heu_academic_elegant',
  });
  while (calls.length < 2) {
    await new Promise((resolve) => setImmediate(resolve));
  }

  assert.equal(calls.length, 2);
  assert.equal(releases.filter(Boolean).length, 2);
  const firstCall = calls.find((call) => /slides\/slide-01\.prompt\.txt$/.test(call.promptPath));
  const secondCall = calls.find((call) => /slides\/slide-02\.prompt\.txt$/.test(call.promptPath));
  assert.ok(firstCall);
  assert.ok(secondCall);
  assert.match(firstCall.prompt, /只生成第 1 \/ 2 页/);
  assert.match(secondCall.prompt, /只生成第 2 \/ 2 页/);
  assert.doesNotMatch(firstCall.prompt, /目标输出路径：`[^`]*deck\.fragment\.html`/);
  assert.match(firstCall.promptPath, /slides\/slide-01\.prompt\.txt$/);
  assert.match(secondCall.outputPath, /slides\/slide-02\.fragment\.html$/);

  releases[2]();
  await new Promise((resolve) => setImmediate(resolve));
  releases[1]();
  const merged = await generation;

  assert.match(merged, /第 1 页[\s\S]*第 2 页/);
  assert.equal((merged.match(/class="slide\b/g) || []).length, 2);
  assert.equal(await fs.readFile(revisionPaths.fragmentPath, 'utf8'), merged);
});

test('runtime prompt path normalization supports placeholders and legacy hard-coded paths', () => {
  const contentPath = '/tmp/html2ppt/jobs/job_1/revisions/rev_0000/content.md';
  const themeCssPath = '/tmp/html2ppt/style/theme-current.css';
  const template = [
    '- 内容大纲：`{{CONTENT_PATH}}`',
    '- 当前主题：`{{THEME_CSS_PATH}}`',
    '- 旧内容路径：`/Users/sun/code/aippt/html2ppt/content.md`',
    '- 旧主题路径：`/Users/sun/code/aippt/html2ppt/style/theme-heu-academic-elegant.css`',
  ].join('\n');

  const normalized = applyRuntimePromptPaths(template, {
    contentPath,
    themeCssPath,
  });

  assert.doesNotMatch(normalized, /\{\{CONTENT_PATH\}\}|\{\{THEME_CSS_PATH\}\}/);
  assert.doesNotMatch(normalized, /\/Users\/sun\/code\/aippt\/html2ppt/);
  assert.equal((normalized.match(new RegExp(contentPath, 'g')) || []).length, 2);
  assert.equal((normalized.match(new RegExp(themeCssPath, 'g')) || []).length, 2);
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
