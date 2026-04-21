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
const { loadCatalogBundle, summarizeCatalogEntries } = require('../src/domain/catalogs');
const { localizeMediaAssets } = require('../src/lib/media-assets');
const {
  buildStandaloneHtmlFromFragment,
  ensurePreviewRuntimeBridge,
} = require('../src/lib/build-standalone-html');
const {
  normalizeRepoAssetPaths,
  normalizeVideoSourceTags,
  runChromeExport,
} = require('../src/lib/export-html-to-pptx');
const {
  createJob: createStoredJob,
  createRevision: createStoredRevision,
  getRevisionPaths,
  updateJob,
} = require('../src/store/job-store');
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

function formatPath(...segments) {
  return path.join(__dirname, '../format', ...segments);
}

async function readGenerationReferenceText() {
  const files = [
    path.join(__dirname, '../prompts/slide-executor.md'),
    path.join(__dirname, '../references/agent-workflow.md'),
    path.join(__dirname, '../references/html-to-pptx-restrict.md'),
    path.join(__dirname, '../references/content-protocol.md'),
    path.join(__dirname, '../references/layout-catalog.json'),
    path.join(__dirname, '../references/component-catalog.json'),
  ];
  const parts = await Promise.all(files.map((filePath) => fs.readFile(filePath, 'utf8')));
  return parts.join('\n');
}

test('theme registry resolves known theme ids', () => {
  const resolved = resolveThemeCss('heu_academic_elegant');
  assert.match(resolved, /theme-heu-academic-elegant\.css$/);
});

test('runner can normalize json and html document outputs', async () => {
  const { normalizeAgentOutputByKind } = require('../src/agents/claude-code-runner');

  assert.equal(normalizeAgentOutputByKind('{"ok":true}', 'json'), '{"ok":true}');
  assert.match(
    normalizeAgentOutputByKind('<!DOCTYPE html><html><body><h1>Demo</h1></body></html>', 'html_document'),
    /<html>/i
  );
});

test('phase progress mapping stays stable', () => {
  assert.equal(progressForPhase('accepted'), 0);
  assert.equal(progressForPhase('planning_deck'), 25);
  assert.equal(progressForPhase('generating_slides'), 40);
  assert.equal(progressForPhase('completed'), 100);
});

test('planner and executor prompts stay concise while requiring teaching recipes', async () => {
  const planner = await fs.readFile(path.join(__dirname, '../prompts/deck-planner.md'), 'utf8');
  const executor = await fs.readFile(path.join(__dirname, '../prompts/slide-executor.md'), 'utf8');
  const reference = await fs.readFile(path.join(__dirname, '../references/deck-design-plan.md'), 'utf8');

  assert.match(planner, /Teaching Objective|教学目的/);
  assert.match(planner, /Teaching Recipe|内容配方/);
  assert.match(planner, /不要编造|不编造|unsupported factual/);
  assert.match(executor, /Focused catalog summary/);
  assert.match(executor, /required slots|必需槽位/);
  assert.match(reference, /Density/);
  assert.ok(planner.split('\n').length < 80);
  assert.ok(executor.split('\n').length < 90);
});

test('deck planner prompt stays concise while preferring fallback over sparse layout shells', async () => {
  const { buildDeckDesignPlanPrompt } = require('../src/domain/deck-plan');
  const prompt = await buildDeckDesignPlanPrompt({
    contentPath: '/tmp/content.md',
    outputPath: '/tmp/deck_design_plan.md',
    themeCssPath: '/tmp/theme.css',
  });

  assert.match(prompt, /light.*cover.*toc.*section.*thanks.*media/i);
  assert.match(prompt, /content.*standard.*full|standard.*full.*content/i);
  assert.match(prompt, /fallback.*sparse|sparse.*fallback/i);
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
    inferLayout('<div class="slide layout-content-blank layout-standard-text"><div class="title-main">组合页</div></div>'),
    'content_blank'
  );
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

test('fragment helpers infer new dense teaching layouts', () => {
  assert.equal(
    inferLayout('<div class="slide layout-architecture-pipeline-spotlight"><div class="title-main">架构页</div></div>'),
    'architecture-pipeline-spotlight'
  );
  assert.equal(
    inferLayout('<div class="slide layout-dual-core-support"><div class="title-main">双核页</div></div>'),
    'dual-core-support'
  );
  assert.equal(
    inferLayout('<div class="slide layout-thesis-evidence-grid"><div class="title-main">论证页</div></div>'),
    'thesis-evidence-grid'
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

  const decorated = normalizeSlideDecorations(source, 'heu_academic_elegant');
  const redecorated = normalizeSlideDecorations(decorated, 'heu_academic_elegant');

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
  assert.equal((decorated.match(/class="slide-brand"/g) || []).length, 0);
  assert.equal((decorated.match(/class="slide-brand-image"/g) || []).length, 0);
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

  const decorated = normalizeSlideDecorations(source, 'heu_academic_elegant');

  assert.doesNotMatch(decorated, /thanks-orbit|thanks-accent-line/);
  assert.match(decorated, /class="[^"]*\bthanks-safe-decor\b/);
  assert.match(decorated, /class="[^"]*\bthanks-safe-line\b/);
  assert.doesNotMatch(decorated, /thanks-safe-panel|thanks-safe-corner|footer-area|slide-brand/);
  assert.doesNotMatch(decorated, /slide-top-rule|slide-top-accent/);
});

test('slide decoration normalizer rewrites long thanks titles into ppt-safe Q&A copy', () => {
  const source = [
    '<div class="slide layout-thanks">',
    '<div class="thanks-content">',
    '<div class="title-en">Q&A / THANKS</div>',
    '<div class="title-main">总结与 Q&A</div>',
    '<div class="thanks-note">欢迎交流与讨论。</div>',
    '</div>',
    '</div>',
  ].join('');

  const decorated = normalizeSlideDecorations(source);

  assert.match(decorated, /<div class="title-main">Q&amp;A<\/div>/);
  assert.match(decorated, /<div class="thanks-note">总结与答疑。欢迎交流与讨论。<\/div>/);
});

test('slide decoration normalizer backfills sparse teaching slots for card, comparison, capability, and media layouts', () => {
  const source = [
    [
      '<div class="slide">',
      '<div class="cards-grid">',
      '<div class="surface-card">',
      '<div class="card-subtitle">Layer One</div>',
      '<div class="card-title">信息获取</div>',
      '<div class="card-desc">连接外部知识来源。</div>',
      '</div>',
      '<div class="surface-card">',
      '<div class="card-subtitle">Layer Two</div>',
      '<div class="card-title">逻辑计算</div>',
      '<div class="card-desc">完成推理和转换。</div>',
      '</div>',
      '<div class="surface-card">',
      '<div class="card-subtitle">Layer Three</div>',
      '<div class="card-title">交互执行</div>',
      '<div class="card-desc">把建议转化为动作。</div>',
      '</div>',
      '</div>',
      '</div>',
    ].join(''),
    [
      '<div class="slide layout-standard-text-comparison">',
      '<div class="content-area">',
      '<div class="comparison-grid">',
      '<div class="surface-card comparison-card">',
      '<div class="card-title">Skill（能力）- What</div>',
      '<div class="card-subtitle">能力抽象</div>',
      '</div>',
      '<div class="surface-card comparison-card">',
      '<div class="card-title">MCP（协议）- How</div>',
      '<div class="card-subtitle">协议标准</div>',
      '</div>',
      '</div>',
      '</div>',
      '</div>',
    ].join(''),
    [
      '<div class="slide layout-capability-map-grid">',
      '<div class="content-area">',
      '<div class="capability-map">',
      '<div class="capability-hero">',
      '<div class="capability-hero-title">六个模块</div>',
      '<div class="capability-hero-text">支撑 PPT 生成全流程。</div>',
      '</div>',
      '</div>',
      '</div>',
      '</div>',
    ].join(''),
    [
      '<div class="slide layout-media-focus">',
      '<div class="media-focus-content-panel">',
      '<div class="quote-box"><div class="quote-text">图片是视觉主角。</div></div>',
      '<div class="surface-card text-details text-list">',
      '<div class="list-item">右侧只保留短说明。</div>',
      '</div>',
      '</div>',
      '</div>',
    ].join(''),
  ].join('\n');

  const decorated = normalizeSlideDecorations(source);

  assert.match(decorated, /class="card-example"/);
  assert.match(decorated, /class="card-question"/);
  assert.doesNotMatch(decorated, /class="card-ghost-number"/);
  assert.match(decorated, /class="comparison-summary-bar"/);
  assert.match(decorated, /class="capability-relation"/);
  assert.match(decorated, /class="capability-takeaway"/);
  assert.match(decorated, /class="media-observation-list"/);
  assert.match(decorated, /class="media-conclusion"/);
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
  assert.doesNotMatch(output, /class="slide-brand"/);
  assert.doesNotMatch(output, /class="slide-brand-image"/);
  assert.doesNotMatch(output, /class="slide-top-accent"/);
  assert.match(output, /class="slide-header-hairline"/);
  assert.match(output, /class="[^"]*\bslide-header-mark-accent\b/);
  assert.match(output, /class="cover-subtitle-accent"/);
  assert.match(normalizedFragment, /class="slide-safe-decor"/);
  assert.doesNotMatch(normalizedFragment, /class="slide-brand"/);
  assert.match(normalizedFragment, /class="slide-header-hairline"/);
  assert.match(normalizedFragment, /class="cover-subtitle-accent"/);
});

test('standalone html includes realtime preview bridge behavior', async () => {
  const workDir = path.join(process.env.PPT_DATA_DIR, 'standalone-preview-bridge-test');
  await fs.mkdir(workDir, { recursive: true });
  const fragmentPath = path.join(workDir, 'deck.fragment.html');
  const outputPath = path.join(workDir, 'deck.html');

  await fs.writeFile(
    fragmentPath,
    '<div class="slide layout-standard-text"><div class="title-main">Slide A</div></div>',
    'utf8'
  );

  buildStandaloneHtmlFromFragment({
    fragmentPath,
    outputPath,
    themeId: 'heu_academic_elegant',
  });

  const output = await fs.readFile(outputPath, 'utf8');
  assert.match(output, /type:\s*'ppt-preview-ready'/);
  assert.match(output, /const singleSlidePreviewMode = searchParams\.get\('preview_mode'\) === 'single-slide';/);
  assert.match(output, /if \(data\.type !== 'ppt-preview-go-to-slide'\) return;/);
});

test('legacy deck html can be retrofitted with realtime preview bridge behavior', () => {
  const legacy = [
    '<!DOCTYPE html>',
    '<html><body>',
    '<div class="slide layout-standard-text"><div class="title-main">Old Slide</div></div>',
    '</body></html>',
  ].join('\n');

  const retrofitted = ensurePreviewRuntimeBridge(legacy);

  assert.match(retrofitted, /type:\s*'ppt-preview-ready'/);
  assert.match(retrofitted, /const singleSlidePreviewMode = searchParams\.get\('preview_mode'\) === 'single-slide';/);
  assert.equal(
    (retrofitted.match(/ppt-preview-ready/g) || []).length,
    1
  );
});

test('thanks template uses real HEU logo instead of placeholder text', async () => {
  const template = await fs.readFile(formatPath('presets', 'thanks-body.html'), 'utf8');
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
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
  assert.match(layoutCss, /\.layout-thanks \.title-main\s*{[^}]*width:\s*520px/s);
  assert.match(layoutCss, /\.layout-thanks \.title-main\s*{[^}]*max-width:\s*520px/s);
  assert.doesNotMatch(layoutCss, /\.layout-thanks \.title-main\s*{[^}]*min-width:/s);
  assert.match(layoutCss, /\.layout-thanks \.title-main\s*{[^}]*white-space:\s*nowrap/s);
  assert.match(layoutCss, /\.layout-thanks \.title-main\s*{[^}]*text-align:\s*center/s);
  assert.match(layoutCss, /\.layout-thanks \.thanks-content\s*{[^}]*padding-top:\s*72px/s);
  assert.match(layoutCss, /\.layout-thanks \.title-en\s*{[^}]*width:\s*320px/s);
  assert.match(layoutCss, /\.layout-thanks \.title-en\s*{[^}]*max-width:\s*320px/s);
  assert.match(layoutCss, /\.layout-thanks \.title-en\s*{[^}]*white-space:\s*nowrap/s);
  assert.match(layoutCss, /\.layout-thanks \.title-en\s*{[^}]*text-align:\s*center/s);
  assert.match(layoutCss, /\.layout-thanks \.title-en\s*{[^}]*margin-bottom:\s*22px/s);
  assert.doesNotMatch(layoutCss, /\.thanks-safe-panel-primary|\.thanks-safe-panel-secondary|\.thanks-safe-corner-right/);
  assert.doesNotMatch(template, /logo-placeholder|HEU LOGO/);
  assert.doesNotMatch(template, /contact-info|info-item/);
});

test('cover template uses dedicated cover subtitle structure', async () => {
  const template = await fs.readFile(formatPath('presets', 'cover-body.html'), 'utf8');
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
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
  const template = await fs.readFile(formatPath('frame', 'standard-text-body.html'), 'utf8');

  assert.doesNotMatch(template, /<ol\b|<ul\b/);
  assert.doesNotMatch(template, /process-track|process-grid|comparison-grid|sidebar-rail|dual-panel-aside/);
});

test('process templates separate short track, four-step grid, and five-step list examples', async () => {
  const trackTemplate = await fs.readFile(formatPath('frame', 'standard-text-process-body.html'), 'utf8');
  const gridTemplate = await fs.readFile(formatPath('frame', 'standard-text-process-grid-body.html'), 'utf8');
  const listTemplate = await fs.readFile(formatPath('frame', 'standard-text-process-list-body.html'), 'utf8');

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

test('chart-style component templates use ppt-safe DOM structures', async () => {
  const files = [
    'metric-strip-fragment.html',
    'bar-chart-fragment.html',
    'matrix-2x2-fragment.html',
    'timeline-fragment.html',
    'relationship-map-fragment.html',
  ];

  for (const fileName of files) {
    const template = await fs.readFile(formatPath('components', fileName), 'utf8');
    assert.doesNotMatch(template, /<canvas\b|<script\b|style="/);
    assert.doesNotMatch(template, /::before|::after/);
    assert.match(template, /surface-card|chart-|matrix-|timeline-|relationship-/);
  }

  const matrixTemplate = await fs.readFile(formatPath('components', 'matrix-2x2-fragment.html'), 'utf8');
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
  assert.match(matrixTemplate, /class="matrix-corner"/);
  assert.match(matrixTemplate, /class="[^"]*\bmatrix-cell-top-left\b/);
  assert.match(matrixTemplate, /class="[^"]*\bmatrix-cell-top-right\b/);
  assert.match(matrixTemplate, /class="[^"]*\bmatrix-cell-bottom-left\b/);
  assert.match(matrixTemplate, /class="[^"]*\bmatrix-cell-bottom-right\b/);
  assert.match(layoutCss, /\.matrix-corner\s*{[^}]*grid-column:\s*1[^}]*grid-row:\s*1/s);
  assert.match(layoutCss, /\.matrix-cell-top-left\s*{[^}]*grid-column:\s*2[^}]*grid-row:\s*2/s);
  assert.match(layoutCss, /\.matrix-cell-top-right\s*{[^}]*grid-column:\s*3[^}]*grid-row:\s*2/s);
  assert.match(layoutCss, /\.matrix-cell-bottom-left\s*{[^}]*grid-column:\s*2[^}]*grid-row:\s*3/s);
  assert.match(layoutCss, /\.matrix-cell-bottom-right\s*{[^}]*grid-column:\s*3[^}]*grid-row:\s*3/s);

  const relationshipTemplate = await fs.readFile(formatPath('components', 'relationship-map-fragment.html'), 'utf8');
  assert.equal((relationshipTemplate.match(/class="relationship-link"/g) || []).length, 3);
});

test('advanced teaching layout templates are registered and ppt-safe', async () => {
  const prompt = await readGenerationReferenceText();
  const contracts = prompt;
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');
  const layoutNames = [
    'comparison-vs-panels',
    'execution-pipeline',
    'pillar-cards-banner',
    'capability-map-grid',
  ];

  for (const layoutName of layoutNames) {
    const template = await fs.readFile(
      formatPath('presets', `${layoutName}-body.html`),
      'utf8'
    );
    const className = `layout-${layoutName}`;

    assert.match(template, new RegExp(`class="slide ${className}"`));
    assert.match(template, /class="header-area"/);
    assert.match(template, /class="title-divider"/);
    assert.doesNotMatch(template, /<ul\b|<ol\b|::before|::after|style="/);
    assert.match(prompt, new RegExp(`format/presets/${layoutName}-body\\.html`));
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
    formatPath('presets', 'comparison-vs-panels-body.html'),
    'utf8'
  );
  assert.doesNotMatch(vsTemplate, /vs-spine/);
  assert.doesNotMatch(layoutCss, /\.vs-spine\s*{/);
  assert.doesNotMatch(themeCss, /\.vs-spine\s*{/);
  assert.doesNotMatch(prompt, /vs-spine/);
  assert.doesNotMatch(contracts, /vs-spine/);
  const pipelineTemplate = await fs.readFile(
    formatPath('presets', 'execution-pipeline-body.html'),
    'utf8'
  );
  assert.doesNotMatch(pipelineTemplate, /▶/);
  assert.match(pipelineTemplate, /class="pipeline-arrow-svg"/);
  assert.doesNotMatch(layoutCss, /\.pipeline-number\s*{[^}]*position:\s*absolute/s);
  assert.doesNotMatch(layoutCss, /\.pipeline-number\s*{[^}]*top:\s*-/s);
  assert.match(contracts, /不要连续使用 `comparison-vs-panels`|不要连续使用同一种增强版式/s);
});

test('priority presets expose fuller teaching recipe slots', async () => {
  const vs = await fs.readFile(formatPath('presets', 'comparison-vs-panels-body.html'), 'utf8');
  const pipeline = await fs.readFile(formatPath('presets', 'execution-pipeline-body.html'), 'utf8');
  const capability = await fs.readFile(formatPath('presets', 'capability-map-grid-body.html'), 'utf8');
  const pillar = await fs.readFile(formatPath('presets', 'pillar-cards-banner-body.html'), 'utf8');
  const media = await fs.readFile(formatPath('presets', 'media-focus-body.html'), 'utf8');

  assert.match(vs, /class="vs-problem"/);
  assert.match(vs, /class="vs-teaching-summary"/);

  assert.equal((pipeline.match(/class="pipeline-teaching-note"/g) || []).length, 3);
  assert.match(pipeline, /pipeline-step-output/);

  assert.match(capability, /class="capability-relation"/);
  assert.match(capability, /class="capability-takeaway"/);

  assert.equal((pillar.match(/class="pillar-example"/g) || []).length, 3);
  assert.match(pillar, /pillar-summary-bar/);

  assert.match(media, /class="media-observation-list"/);
  assert.match(media, /class="media-conclusion"/);
});

test('comparison vs teaching slots fit a conservative vertical budget', async () => {
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
  const themeCss = await fs.readFile(
    path.join(__dirname, '../style/theme-heu-academic-elegant.css'),
    'utf8'
  );

  const blockFor = (css, selector) => {
    const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = css.match(new RegExp(`${escaped}\\s*{(?<body>[^}]*)}`, 's'));
    assert.ok(match, `missing CSS block for ${selector}`);
    return match.groups.body;
  };
  const pxProp = (block, prop) => {
    const match = block.match(new RegExp(`${prop}:\\s*(?<value>\\d+(?:\\.\\d+)?)px`));
    assert.ok(match, `missing px property ${prop}`);
    return Number(match.groups.value);
  };
  const lineHeightPx = (block) => {
    const fontSize = pxProp(block, 'font-size');
    const lineHeight = block.match(/line-height:\s*(?<value>\d+(?:\.\d+)?)/);
    assert.ok(lineHeight, 'missing unitless line-height');
    return fontSize * Number(lineHeight.groups.value);
  };
  const verticalPadding = (block) => {
    const padding = block.match(/padding:\s*(?<top>\d+(?:\.\d+)?)px\s+(?<right>\d+(?:\.\d+)?)px/);
    assert.ok(padding, 'missing two-value padding');
    return Number(padding.groups.top) * 2;
  };

  const contentArea = blockFor(layoutCss, '.layout-comparison-vs-panels .content-area');
  const problemLayout = blockFor(layoutCss, '.vs-problem');
  const gridLayout = blockFor(layoutCss, '.layout-comparison-vs-panels .vs-comparison-grid');
  const teachingSummaryLayout = blockFor(layoutCss, '.vs-teaching-summary');
  const problemTheme = blockFor(themeCss, '.vs-problem');
  const teachingSummaryTheme = blockFor(themeCss, '.vs-teaching-summary');

  const budget =
    pxProp(contentArea, 'padding-top') +
    verticalPadding(problemLayout) +
    lineHeightPx(problemTheme) +
    pxProp(problemLayout, 'margin-bottom') +
    pxProp(gridLayout, 'min-height') +
    pxProp(teachingSummaryLayout, 'margin-top') +
    verticalPadding(teachingSummaryLayout) +
    lineHeightPx(teachingSummaryTheme);

  assert.ok(
    budget <= 720,
    `comparison-vs-panels teaching stack minimum ${budget}px exceeds 720px budget`
  );
});

test('card layout uses profile card styling and the prompt does not expose sidebar', async () => {
  const prompt = await readGenerationReferenceText();
  const contracts = prompt;
  const template = await fs.readFile(formatPath('frame', 'card-layout-body.html'), 'utf8');
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');

  assert.doesNotMatch(prompt, /standard-text-sidebar|format\/standard-text-sidebar-body\.html/);
  assert.doesNotMatch(contracts, /standard-text-sidebar|format\/standard-text-sidebar-body\.html/);
  assert.match(template, /class="content-area card-layout-content"/);
  assert.match(template, /class="surface-card cards-lead"/);
  assert.match(template, /class="cards-summary-bar"/);
  assert.equal((template.match(/class="surface-card"/g) || []).length, 3);
  assert.equal((template.match(/class="card-top-accent"/g) || []).length, 3);
  assert.doesNotMatch(template, /class="card-ghost-number"/);
  assert.doesNotMatch(layoutCss, /\.cards-grid > \.surface-card::before\s*{/);
  assert.doesNotMatch(layoutCss, /\.cards-grid > \.surface-card::after\s*{/);
  assert.doesNotMatch(layoutCss, /content:\s*counter\(feature-card,\s*decimal-leading-zero\)/);
  assert.match(layoutCss, /\.cards-grid > \.surface-card \.card-top-accent\s*{/);
  assert.doesNotMatch(layoutCss, /\.cards-grid > \.surface-card \.card-ghost-number\s*{/);
  assert.match(layoutCss, /\.cards-grid > \.surface-card \.card-title\s*{[^}]*border-bottom:/s);
  assert.doesNotMatch(themeCss, /\.cards-grid > \.surface-card \.card-ghost-number\s*{/);
  assert.match(contracts, /card-top-accent/);
  assert.doesNotMatch(contracts, /card-ghost-number/);
});

test('base components include richer teaching slots without unsafe markup', async () => {
  const bullet = await fs.readFile(formatPath('components', 'bullet-list-fragment.html'), 'utf8');
  const cards = await fs.readFile(formatPath('components', 'card-grid-fragment.html'), 'utf8');
  const comparison = await fs.readFile(formatPath('components', 'comparison-matrix-fragment.html'), 'utf8');
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
  const themeCss = await fs.readFile(
    path.join(__dirname, '../style/theme-heu-academic-elegant.css'),
    'utf8'
  );

  assert.match(bullet, /class="bullet-takeaway"/);
  assert.match(bullet, /class="bullet-example"/);
  assert.equal((bullet.match(/class="list-item"/g) || []).length, 3);
  assert.doesNotMatch(bullet, /<ul\b|<ol\b|style="/);

  assert.match(cards, /class="card-example"/);
  assert.match(cards, /class="card-question"/);
  assert.equal((cards.match(/class="card-top-accent"/g) || []).length, 3);
  assert.doesNotMatch(cards, /class="card-ghost-number"/);

  assert.match(comparison, /class="surface-card comparison-matrix-card"/);
  assert.match(comparison, /class="comparison-table"/);
  assert.match(comparison, /class="comparison-row"/);
  assert.doesNotMatch(comparison, /<table\b|style="/);
  assert.match(layoutCss, /\.comparison-table\s*{[^}]*grid-column:\s*1\s*\/\s*-1/s);
  assert.match(layoutCss, /\.comparison-matrix-card\s*{[^}]*grid-column:\s*1\s*\/\s*-1/s);
  assert.match(layoutCss, /\.comparison-row\s*{[^}]*padding:\s*14px\s+20px/s);
  assert.match(themeCss, /\.comparison-matrix-card\s*{[^}]*padding:\s*10px\s+0/s);
  assert.match(themeCss, /\.comparison-row\s*\+\s*\.comparison-row\s*{[^}]*border-top:/s);
});

test('export text boxes preserve padding as pptx margins', async () => {
  const source = await fs.readFile(path.join(__dirname, '../dom-to-pptx/src/index.js'), 'utf8');
  const utils = await fs.readFile(path.join(__dirname, '../dom-to-pptx/src/utils.js'), 'utf8');
  const bundle = await fs.readFile(path.join(__dirname, '../test-harness/dom-to-pptx.bundle.js'), 'utf8');

  assert.match(utils, /export function getTextBoxMargin\s*\(/);
  assert.match(source, /const textMargin = getTextBoxMargin\(style,\s*config\.scale\)/);
  assert.match(source, /textPayload = \{ text: textParts, align, valign, margin: textMargin \}/);
  assert.doesNotMatch(source, /textPayload = \{ text: textParts, align, valign, inset: padding \}/);
  assert.match(source, /margin:\s*textPayload\.margin/);
  assert.doesNotMatch(source, /inset:\s*textPayload\.inset,\s*[\s\S]*?margin:\s*0,/);
  assert.match(bundle, /const textMargin = getTextBoxMargin\(style,\s*config\.scale\)/);
  assert.match(bundle, /margin:\s*textPayload\.margin/);
  assert.match(source, /const hyperlink = resolveAnchorHyperlink\(child,\s*node\)/);
  assert.match(bundle, /const hyperlink = resolveAnchorHyperlink\(child,\s*node\)/);
  assert.doesNotMatch(source, /containerHyperlink \? \{ hyperlink: containerHyperlink \} : \{\}/);
  assert.doesNotMatch(bundle, /containerHyperlink \? \{ hyperlink: containerHyperlink \} : \{\}/);
});

test('architecture spotlight keeps generic card-desc paragraphs on the same typography scale', async () => {
  const themeCss = await fs.readFile(
    path.join(__dirname, '../style/theme-heu-academic-elegant.css'),
    'utf8'
  );

  assert.match(themeCss, /\.architecture-spotlight\s+\.card-desc/);
  assert.match(
    themeCss,
    /\.layout-architecture-pipeline-spotlight\.layout-overflow-compact[\s\S]*\.architecture-spotlight\s+\.card-desc/
  );
});

test('media focus uses export-safe split media panel and cover cropping', async () => {
  const prompt = await readGenerationReferenceText();
  const contracts = prompt;
  const template = await fs.readFile(formatPath('presets', 'media-focus-body.html'), 'utf8');
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');

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
  const prompt = await readGenerationReferenceText();
  const contracts = prompt;

  assert.match(prompt, /standard-text-dual-panel[\s\S]*1 到 2 个完整 insight card[\s\S]*quote \+ 3 条以上论证/);
  assert.match(prompt, /dual_core_support[\s\S]*两个核心概念 \+ 一个机制 \+ 一个结果/);
  assert.match(prompt, /architecture_pipeline_spotlight[\s\S]*创新点必须独立于三段主链/);
  assert.match(contracts, /standard-text-dual-panel[\s\S]*1 到 2 个完整 insight card[\s\S]*quote \+ 3 条以上论证/);
});

test('structured text template handles dense examples with one panel instead of odd card grids', async () => {
  const template = await fs.readFile(formatPath('frame', 'standard-text-structured-body.html'), 'utf8');

  assert.match(template, /class="slide layout-standard-text-structured"/);
  assert.match(template, /class="structured-lead"/);
  assert.match(template, /class="[^"]*\bstructured-panel\b/);
  assert.match(template, /class="structured-section"/);
  assert.match(template, /class="structured-flow"/);
  assert.doesNotMatch(template, /structured-grid|structured-card|sidebar-card|sidebar-points|quote-box/);
});

test('generation prompt advertises new dense layouts while keeping legacy structured hidden from planner', async () => {
  const prompt = await readGenerationReferenceText();
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
  const textMediaTemplate = await fs.readFile(
    formatPath('frame', 'text-left-media-right-body.html'),
    'utf8'
  );

  assert.match(prompt, /\{\{CONTENT_PATH\}\}/);
  assert.match(prompt, /\{\{THEME_CSS_PATH\}\}/);
  assert.doesNotMatch(prompt, /\/Users\/sun\/code\/aippt\/html2ppt/);
  assert.match(prompt, /standard-text-structured/);
  assert.match(prompt, /legacy compatibility only; do not prefer in new planning/);
  assert.match(prompt, /architecture_pipeline_spotlight/);
  assert.match(prompt, /dual_core_support/);
  assert.match(prompt, /thesis_evidence_grid/);
  assert.doesNotMatch(prompt, /standard-text-sidebar/);
  assert.match(prompt, /5 步|五步/);
  assert.match(prompt, /thanks 页不要再插入右上角 `slide-brand`/);
  assert.match(prompt, /不要输出 `contact-info`|不输出 `contact-info`/);
  assert.match(prompt, /thanks-note/);
  assert.match(prompt, /Q&A.*单行|单行.*Q&A/);
  assert.match(prompt, /装饰.*系统后处理注入|系统后处理.*装饰/);
  assert.match(prompt, /不要手写.*slide-safe-decor|不要.*slide-safe-decor/);
  assert.match(prompt, /页脚.*只保留.*页码|只保留.*右下角页码/);
  assert.match(prompt, /创新点必须独立于三段主链|证据卡是并列关系/);
  assert.match(prompt, /没有.*Local-Poster-Path.*不要输出.*poster|不要输出.*poster.*没有.*Local-Poster-Path/s);
  assert.doesNotMatch(layoutCss, /\.slide::before|\.slide::after/);
  assert.doesNotMatch(textMediaTemplate, /\bposter=/);
  assert.doesNotMatch(textMediaTemplate, /1_poster\.jpg/);
});

test('layout css keeps shared base rules centralized', async () => {
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');

  assert.equal((layoutCss.match(/^\.slide\s*{/gm) || []).length, 1);
  assert.equal((layoutCss.match(/^\.header-area\s*{/gm) || []).length, 1);
  assert.equal((layoutCss.match(/^\.title-divider\s*{/gm) || []).length, 1);
});

test('footer chrome is minimized to page number only', async () => {
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');
  const basicThemeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-basic.css'), 'utf8');

  assert.match(layoutCss, /\.footer-area\s*{[^}]*justify-content:\s*flex-end/s);
  assert.match(layoutCss, /\.footer-logo\s*{[^}]*display:\s*none/s);
  assert.doesNotMatch(themeCss, /\.footer-area\s*{[^}]*border-top/s);
  assert.doesNotMatch(themeCss, /\.footer-area\s*{[^}]*padding-top/s);
  assert.doesNotMatch(basicThemeCss, /\.footer-area\s*{[^}]*border-top/s);
});

test('body templates only include page number footers', async () => {
  const templateDirs = [formatPath('frame'), formatPath('presets')];

  for (const formatDir of templateDirs) {
    const files = (await fs.readdir(formatDir)).filter((fileName) => fileName.endsWith('-body.html'));
    for (const fileName of files) {
      const template = await fs.readFile(path.join(formatDir, fileName), 'utf8');
      assert.doesNotMatch(template, /footer-logo/, `${fileName} should not include footer-logo`);
    }
  }
});

test('elegant theme uses lighter teaching deck rhythm', async () => {
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');

  assert.match(themeCss, /\.title-main\s*{[^}]*font-size:\s*50px[^}]*letter-spacing:\s*0/s);
  assert.match(themeCss, /\.layout-cover \.title-main\s*{[^}]*font-size:\s*64px/s);
  assert.match(themeCss, /\.surface-card\s*{[^}]*border-radius:\s*8px[^}]*box-shadow:\s*var\(--shadow-sm\)/s);
  assert.match(layoutCss, /\.layout-standard-text \.content-area\s*{[^}]*justify-content:\s*flex-start/s);
  assert.match(layoutCss, /\.layout-standard-text \.content-area\s*{[^}]*padding-top:\s*56px/s);
  assert.match(layoutCss, /\.layout-standard-text-comparison \.content-area\s*{[^}]*align-items:\s*stretch/s);
  assert.match(layoutCss, /\.layout-standard-text-comparison \.content-area\s*{[^}]*padding-top:\s*36px/s);
  assert.match(layoutCss, /\.layout-standard-text-structured \.content-area\s*{[^}]*justify-content:\s*flex-start/s);
  assert.match(layoutCss, /\.layout-standard-text-process \.content-area\s*{[^}]*justify-content:\s*flex-start/s);
  assert.match(layoutCss, /\.layout-standard-text-process \.content-area\s*{[^}]*padding-top:\s*56px/s);
  assert.match(layoutCss, /\.cards-grid > \.surface-card\s*{[^}]*min-height:\s*460px/s);
});

test('dense teaching layouts trim oversized whitespace on light content pages', async () => {
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');

  assert.match(layoutCss, /\.text-density-grid\s*{[^}]*grid-template-columns:\s*minmax\(0,\s*1\.42fr\)\s+minmax\(320px,\s*0\.92fr\)/s);
  assert.match(layoutCss, /\.text-support-card\s*{[^}]*justify-content:\s*flex-start/s);
  assert.match(layoutCss, /\.layout-standard-text \.text-details\s*{[^}]*min-height:\s*280px/s);
  assert.match(layoutCss, /\.comparison-summary-bar\s*{[^}]*width:\s*100%/s);
  assert.match(layoutCss, /\.comparison-card\s*{[^}]*min-height:\s*312px[^}]*justify-content:\s*flex-start/s);
  assert.match(layoutCss, /\.process-summary-bar\s*{[^}]*width:\s*100%/s);
  assert.match(layoutCss, /\.process-track\s*{[^}]*min-height:\s*188px/s);
  assert.match(layoutCss, /\.process-step\s*{[^}]*min-height:\s*188px/s);
  assert.match(layoutCss, /\.process-detail-grid\s*{[^}]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/s);
  assert.match(layoutCss, /\.card-layout-content \.cards-grid\s*{[^}]*margin:\s*0/s);
  assert.match(layoutCss, /\.cards-lead,\s*\.cards-summary-bar\s*{[^}]*width:\s*100%/s);
  assert.match(layoutCss, /\.capability-hero-number\s*{[^}]*margin-top:\s*auto[^}]*align-self:\s*flex-end/s);
  assert.doesNotMatch(layoutCss, /\.capability-hero-number\s*{[^}]*position:\s*absolute/s);
  assert.match(themeCss, /\.capability-hero-number\s*{[^}]*font-size:\s*150px/s);
});

test('overflow compact rules exist for comparison and process frames', async () => {
  const layoutCss = await fs.readFile(formatPath('layout.css'), 'utf8');
  const themeCss = await fs.readFile(path.join(__dirname, '../style/theme-heu-academic-elegant.css'), 'utf8');

  assert.match(layoutCss, /\.layout-standard-text-comparison\.layout-overflow-compact \.content-area/s);
  assert.match(layoutCss, /\.layout-standard-text-process\.layout-overflow-compact \.process-grid/s);
  assert.match(themeCss, /\.layout-standard-text-comparison\.layout-overflow-compact \.comparison-summary-bar/s);
  assert.match(themeCss, /\.layout-standard-text-process\.layout-overflow-compact \.process-summary-bar/s);
});

test('prompt and contracts require teaching display compression without dropping blocks', async () => {
  const prompt = await readGenerationReferenceText();
  const workflowReference = await fs.readFile(path.join(__dirname, '../references/agent-workflow.md'), 'utf8');
  const layoutCatalog = await fs.readFile(path.join(__dirname, '../references/layout-catalog.json'), 'utf8');
  const catalogBundle = await loadCatalogBundle();
  const focusedCatalog = summarizeCatalogEntries(catalogBundle, {
    layouts: ['standard_text_structured', 'comparison_vs', 'execution_pipeline'],
    components: ['bullet_list', 'matrix_2x2', 'timeline'],
  });
  const parsedFocusedCatalog = JSON.parse(focusedCatalog);

  assert.match(prompt, /显示层.*压缩|压缩.*显示层/);
  assert.match(prompt, /Notes|讲稿/);
  assert.match(prompt, /Definition|定义.*Compare|对比.*Process|流程.*Analogy|类比.*Takeaway|结论/s);
  assert.match(prompt, /每个.*Block.*可见承载|Block.*可见承载/);
  assert.doesNotMatch(prompt, /不为了适配版式而删减长要点、压缩示例流程/);

  assert.match(workflowReference, /教学表达|显示文案/);
  assert.match(workflowReference, /Definition|定义.*Compare|对比.*Process|流程.*Analogy|类比.*Takeaway|结论/s);
  assert.ok(focusedCatalog.length < layoutCatalog.length / 2);
  assert.deepEqual(Object.keys(parsedFocusedCatalog.layouts), [
    'standard_text_structured',
    'comparison_vs',
    'execution_pipeline',
  ]);
  assert.deepEqual(Object.keys(parsedFocusedCatalog.components), ['bullet_list', 'matrix_2x2', 'timeline']);
  assert.match(focusedCatalog, /teaching_recipe/);
  assert.match(focusedCatalog, /content_slots/);
  assert.match(focusedCatalog, /hard_constraints/);
});

test('layout catalog nudges sparse card, short process, and thanks pages toward fuller output', async () => {
  const layoutCatalog = await fs.readFile(path.join(__dirname, '../references/layout-catalog.json'), 'utf8');

  assert.match(layoutCatalog, /没有 Lead 时，至少补 1 个 card-example 或 card-question/s);
  assert.match(layoutCatalog, /如果只有 3 个短节点且没有补充说明，改用 execution_pipeline/s);
  assert.match(layoutCatalog, /如果输入标题过长.*thanks-note|thanks-note.*如果输入标题过长/s);
});

test('layout geometry inspector covers thanks and sparse-risk teaching containers', async () => {
  const source = await fs.readFile(
    path.join(__dirname, '../src/lib/layout-geometry-inspector.js'),
    'utf8'
  );

  assert.match(source, /\.thanks-content/);
  assert.match(source, /\.footer-decoration/);
  assert.match(source, /\.text-density-grid/);
  assert.match(source, /\.comparison-grid/);
  assert.match(source, /\.comparison-table/);
  assert.match(source, /\.process-track/);
  assert.match(source, /\.timeline/);
  assert.match(source, /\.metric-strip/);
  assert.match(source, /\.matrix-2x2/);
  assert.match(source, /\.relationship-map/);
  assert.match(source, /\.process-detail-grid/);
  assert.match(source, /\.capability-hero/);
  assert.match(source, /ELEMENT_OVERLAP/);
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
  assert.ok(report.warning_count >= 1);
  const markerWarning = report.warnings.find((warning) => warning.code === 'CONTENT_MARKER_MISSING');
  assert.ok(markerWarning);
  assert.match(markerWarning.message, /核心定义/);
});

test('layout quality report flags sparse-risk comparison layouts before they look empty in export', () => {
  const { buildLayoutQualityReport } = require('../src/domain/layout-quality');
  const contentMarkdown = [
    '# Deck',
    '- Title: 稀疏对比测试',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: Skill 与 MCP',
    '',
    '### Blocks',
    '- Comparison:',
    '  - Left-Title: Skill',
    '    Left-Items:',
    '      - 能力抽象',
    '      - 逻辑封装',
    '  - Right-Title: MCP',
    '    Right-Items:',
    '      - 协议标准',
    '      - 工具接入',
    '',
  ].join('\n');
  const fragmentHtml = [
    '<div class="slide layout-standard-text-comparison">',
    '<div class="title-main">Skill 与 MCP</div>',
    '<div class="comparison-grid">',
    '  <div class="surface-card comparison-card">',
    '    <div class="card-title">Skill</div>',
    '    <div class="comparison-details">',
    '      <div class="list-item">能力抽象</div>',
    '      <div class="list-item">逻辑封装</div>',
    '    </div>',
    '  </div>',
    '  <div class="surface-card comparison-card">',
    '    <div class="card-title">MCP</div>',
    '    <div class="comparison-details">',
    '      <div class="list-item">协议标准</div>',
    '      <div class="list-item">工具接入</div>',
    '    </div>',
    '  </div>',
    '</div>',
    '</div>',
  ].join('');

  const report = buildLayoutQualityReport({ contentMarkdown, fragmentHtml });

  assert.ok(report.warnings.some((warning) => warning.code === 'LAYOUT_SPARSE_RISK'));
});

test('layout quality report flags thin three-card layouts that skip examples or second-layer explanation', () => {
  const { buildLayoutQualityReport } = require('../src/domain/layout-quality');
  const contentMarkdown = [
    '# Deck',
    '- Title: 卡片稀疏测试',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 三个关键词',
    '',
    '### Blocks',
    '- Cards:',
    '  - Title: Client',
    '    Text: 发起调用',
    '  - Title: Server',
    '    Text: 提供能力',
    '  - Title: Transport',
    '    Text: 负责传输',
    '',
  ].join('\n');
  const fragmentHtml = [
    '<div class="slide">',
    '<div class="title-main">三个关键词</div>',
    '<div class="cards-grid">',
    '  <div class="surface-card"><div class="card-title">Client</div><div class="card-desc">发起调用</div></div>',
    '  <div class="surface-card"><div class="card-title">Server</div><div class="card-desc">提供能力</div></div>',
    '  <div class="surface-card"><div class="card-title">Transport</div><div class="card-desc">负责传输</div></div>',
    '</div>',
    '</div>',
  ].join('');

  const report = buildLayoutQualityReport({ contentMarkdown, fragmentHtml });

  assert.ok(report.warnings.some((warning) => warning.code === 'LAYOUT_SPARSE_RISK'));
});

test('layout quality report does not misclassify dense three-step process pages as sparse', () => {
  const { buildLayoutQualityReport } = require('../src/domain/layout-quality');
  const contentMarkdown = [
    '# Deck',
    '- Title: 流程稠密测试',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 三步调用',
    '',
    '### Blocks',
    '- Process:',
    '  - Step: 识别意图',
    '  - Step: 选择工具',
    '  - Step: 整合结果',
    '',
  ].join('\n');
  const fragmentHtml = [
    '<div class="slide layout-standard-text-process">',
    '<div class="title-main">三步调用</div>',
    '<div class="content-area">',
    '  <div class="surface-card process-summary-bar">',
    '    <div class="process-summary-title">先交代阶段目标，再给每一步补输入输出。</div>',
    '  </div>',
    '  <div class="process-track">',
    '    <div class="surface-card process-step"><div class="card-title">识别意图</div></div>',
    '    <div class="process-divider"></div>',
    '    <div class="surface-card process-step"><div class="card-title">选择工具</div></div>',
    '    <div class="process-divider"></div>',
    '    <div class="surface-card process-step"><div class="card-title">整合结果</div></div>',
    '  </div>',
    '  <div class="process-detail-grid">',
    '    <div class="surface-card process-detail-card"><div class="list-item">输入：用户问题。</div></div>',
    '    <div class="surface-card process-detail-card"><div class="list-item">输入：工具清单。</div></div>',
    '    <div class="surface-card process-detail-card"><div class="list-item">输入：结构化结果。</div></div>',
    '  </div>',
    '</div>',
    '</div>',
  ].join('');

  const report = buildLayoutQualityReport({ contentMarkdown, fragmentHtml });

  assert.ok(!report.warnings.some((warning) => warning.code === 'LAYOUT_SPARSE_RISK'));
});

test('initial deck generation runs one agent task per slide in parallel and merges in order', async () => {
  const workDir = path.join(process.env.PPT_DATA_DIR, 'parallel-generation-test');
  const revisionPaths = {
    revisionDir: workDir,
    fragmentPath: path.join(workDir, 'deck.fragment.html'),
    contentPath: path.join(workDir, 'content.md'),
    deckDesignPlanPath: path.join(workDir, 'deck_design_plan.md'),
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
  await fs.mkdir(workDir, { recursive: true });
  await fs.writeFile(
    revisionPaths.deckDesignPlanPath,
    [
      '# Deck Design Plan',
      '',
      '## Metadata',
      '- Deck name: 并行测试',
      '',
      '## Design Specification',
      '- Academic clean.',
      '',
      '## Content Outline',
      '### Slide 1',
      '- Layout: cover',
      '- Components: none',
      '',
      '### Slide 2',
      '- Layout: standard_text_structured',
      '- Components: bullet_list',
      '',
    ].join('\n'),
    'utf8'
  );
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
  const firstCall = calls.find((call) => /slides[\\/]slide-01\.prompt\.txt$/.test(call.promptPath));
  const secondCall = calls.find((call) => /slides[\\/]slide-02\.prompt\.txt$/.test(call.promptPath));
  assert.ok(firstCall);
  assert.ok(secondCall);
  assert.match(firstCall.prompt, /只生成第 1 \/ 2 页/);
  assert.match(secondCall.prompt, /只生成第 2 \/ 2 页/);
  assert.match(firstCall.prompt, /deck_design_plan\.md/);
  assert.match(secondCall.prompt, /deck_design_plan\.md/);
  assert.match(firstCall.prompt, /references\/content-protocol\.md/);
  assert.match(firstCall.prompt, /references\/layout-catalog\.json/);
  assert.match(firstCall.prompt, /references\/component-catalog\.json/);
  assert.match(firstCall.prompt, /references\/html-to-pptx-restrict\.md/);
  assert.match(secondCall.prompt, /Focused catalog summary/);
  const secondFocusedSummary = secondCall.prompt.match(/## Focused catalog summary\n```json\n([\s\S]*?)\n```/);
  assert.ok(secondFocusedSummary);
  assert.match(secondFocusedSummary[1], /standard_text_structured/);
  assert.match(secondFocusedSummary[1], /bullet_list/);
  assert.doesNotMatch(secondFocusedSummary[1], /media_focus/);
  assert.doesNotMatch(firstCall.prompt, /layout-contracts\.md|html-generation-entry-prompt\.md/);
  assert.doesNotMatch(firstCall.prompt, /目标输出路径：`[^`]*deck\.fragment\.html`/);
  assert.match(firstCall.promptPath, /slides[\\/]slide-01\.prompt\.txt$/);
  assert.match(secondCall.outputPath, /slides[\\/]slide-02\.fragment\.html$/);

  releases[2]();
  await new Promise((resolve) => setImmediate(resolve));
  releases[1]();
  const merged = await generation;

  assert.match(merged, /第 1 页[\s\S]*第 2 页/);
  assert.equal((merged.match(/class="slide\b/g) || []).length, 2);
  assert.equal(await fs.readFile(revisionPaths.fragmentPath, 'utf8'), merged);
});

test('runtime prompt path normalization resolves placeholders without legacy hard-coded paths', () => {
  const contentPath = '/tmp/html2ppt/jobs/job_1/revisions/rev_0000/content.md';
  const themeCssPath = '/tmp/html2ppt/style/theme-current.css';
  const template = [
    '- 内容大纲：`{{CONTENT_PATH}}`',
    '- 当前主题：`{{THEME_CSS_PATH}}`',
  ].join('\n');

  const normalized = applyRuntimePromptPaths(template, {
    contentPath,
    themeCssPath,
  });

  assert.doesNotMatch(normalized, /\{\{CONTENT_PATH\}\}|\{\{THEME_CSS_PATH\}\}/);
  assert.doesNotMatch(normalized, /\/Users\/sun\/code\/aippt\/html2ppt/);
  assert.equal((normalized.match(new RegExp(contentPath, 'g')) || []).length, 1);
  assert.equal((normalized.match(new RegExp(themeCssPath, 'g')) || []).length, 1);
});

test('service resolves deck design plan as a first-class artifact', async () => {
  const service = createService();
  await service.init();
  const jobId = 'job_deck_plan_artifact';
  await createStoredJob({
    jobId,
    request: createPayload({
      metadata: {
        request_id: 'req-plan-artifact',
        idempotency_key: 'idem-plan-artifact',
      },
    }),
  });
  const revisionId = await createStoredRevision(jobId, { kind: 'initial' });
  const revisionPaths = getRevisionPaths(jobId, revisionId);
  await fs.writeFile(revisionPaths.deckDesignPlanPath, '# Deck Design Plan\n', 'utf8');

  const artifactPath = await service.resolveArtifactPath(jobId, revisionId, 'deck_design_plan.md');

  assert.equal(artifactPath, revisionPaths.deckDesignPlanPath);
});

test('service results expose only static generation artifacts', async () => {
  const service = createService();
  await service.init();
  const jobId = 'job_static_results';
  await createStoredJob({
    jobId,
    request: createPayload({
      metadata: {
        request_id: 'req-static-results',
        idempotency_key: 'idem-static-results',
      },
    }),
  });
  const revisionId = await createStoredRevision(jobId, { kind: 'initial' });
  const revisionPaths = getRevisionPaths(jobId, revisionId);

  await fs.writeFile(revisionPaths.pptxPath, 'pptx', 'utf8');
  await fs.writeFile(
    revisionPaths.manifestPath,
    JSON.stringify(
      {
        slide_count: 3,
        slides: [],
      },
      null,
      2
    ),
    'utf8'
  );

  await updateJob(jobId, (job) => ({
    ...job,
    latest_success_revision_id: revisionId,
    latest_revision_id: revisionId,
    status: 'succeeded',
  }));

  const result = await service.getResults(jobId);

  assert.equal(result.results.bundle_zip_url, undefined);
  assert.equal(result.results.expanded_deck_design_plan_url, undefined);
});

test('service startup skips non-job directories left under data jobs', async () => {
  const invalidJobDir = path.join(process.env.PPT_DATA_DIR, 'jobs', 'manual_visual_check');
  await fs.mkdir(path.join(invalidJobDir, 'revisions', 'rev_0000'), { recursive: true });
  await fs.writeFile(
    path.join(invalidJobDir, 'revisions', 'rev_0000', 'deck.html'),
    '<div class="slide"></div>',
    'utf8'
  );

  const service = createService();

  await assert.doesNotReject(() => service.init());
});

test('service merges geometry warnings before finalizing artifacts', async () => {
  const mergedReports = [];
  const finalizedReports = [];

  class GeometryAwareService extends PptService {
    async inspectAndMergeQualityReport(postProcessResult, revisionPaths) {
      mergedReports.push(revisionPaths.fullHtmlPath);
      return {
        ...postProcessResult,
        qualityReport: {
          slide_count: 1,
          warning_count: 1,
          warnings: [
            ...(postProcessResult.qualityReport?.warnings || []),
            {
              code: 'ELEMENT_OUTSIDE_SLIDE',
              slide_index: 1,
              title: 'Geometry',
              message: 'geometry warning',
            },
          ],
        },
      };
    }

    async exportDeckArtifacts() {}

    async finalizeArtifacts(jobId, revisionId, postProcessResult) {
      finalizedReports.push(postProcessResult.qualityReport);
    }
  }

  const service = new GeometryAwareService({
    queue: { enqueue() { return Promise.resolve(); } },
    runner: {},
  });

  await service.processPostProcessedDeckArtifacts({
    jobId: 'job-geometry',
    revisionId: 'rev_0000',
    revisionPaths: {
      fullHtmlPath: '/tmp/job-geometry/rev_0000/deck.html',
      pptxPath: '/tmp/job-geometry/rev_0000/deck.pptx',
      revisionDir: '/tmp/job-geometry/rev_0000',
    },
    postProcessResult: {
      qualityReport: {
        slide_count: 1,
        warning_count: 0,
        warnings: [],
      },
    },
  });

  assert.deepEqual(mergedReports, ['/tmp/job-geometry/rev_0000/deck.html']);
  assert.equal(finalizedReports.length, 1);
  assert.equal(finalizedReports[0].warning_count, 1);
  assert.equal(finalizedReports[0].warnings[0].code, 'ELEMENT_OUTSIDE_SLIDE');
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

test('content protocol keeps slide title at top level when nested block items also use Title fields', () => {
  const parsed = parseContentProtocol([
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 全模态系统的三大核心特征',
    '',
    '### Blocks',
    '- Cards:',
    '  - Title: 任意到任意（Any-to-Any）',
    '    Text: 示例一。',
    '  - Title: 原生统一（Native Integration）',
    '    Text: 示例二。',
    '  - Title: 动态时空感知（Dynamic Spatio-temporal Awareness）',
    '    Text: 示例三。',
    '',
    '### Notes',
    '说明。',
    '',
  ].join('\n'));

  assert.equal(parsed.slides.length, 1);
  assert.equal(parsed.slides[0].role, 'content');
  assert.equal(parsed.slides[0].title, '全模态系统的三大核心特征');
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
