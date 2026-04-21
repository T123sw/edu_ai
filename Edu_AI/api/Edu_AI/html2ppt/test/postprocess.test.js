const test = require('node:test');
const assert = require('node:assert/strict');

const { runPostProcessingChain } = require('../src/domain/postprocess');
const { repairOverflowLayouts } = require('../src/domain/layout-repair');

test('post-processing chain normalizes fragment and builds manifest and quality report', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: cover',
    '- Title: Demo',
    '',
    '### Blocks',
    '- Lead: Demo lead',
    '',
  ].join('\n');
  const fragmentHtml = [
    '<div class="slide layout-cover">',
    '<div class="title-main">Demo</div>',
    '</div>',
  ].join('');

  const result = runPostProcessingChain({
    jobId: 'job_1',
    revisionId: 'rev_0000',
    themeId: 'heu_academic_elegant',
    fragmentHtml,
    contentMarkdown,
  });

  assert.match(result.fragmentHtml, /class="slide-safe-decor"/);
  assert.equal(result.manifest.slide_count, 1);
  assert.equal(result.manifest.slides[0].title, 'Demo');
  assert.equal(result.qualityReport.slide_count, 1);
});

test('post-processing chain rejects fragments without slides', () => {
  assert.throws(
    () =>
      runPostProcessingChain({
        jobId: 'job_1',
        revisionId: 'rev_0000',
        themeId: 'heu_academic_elegant',
        fragmentHtml: '<div>No slide</div>',
        contentMarkdown: '',
      }),
    (error) => error.code === 'AGENT_GENERATION_FAILED'
  );
});

test('quality report warns when content slide is too sparse', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: Sparse',
    '',
    '### Blocks',
    '- Lead: One short sentence.',
  ].join('\n');
  const fragmentHtml = [
    '<div class="slide layout-standard-text">',
    '<div class="title-main">Sparse</div>',
    '<div class="content-area"><div class="quote-text">One short sentence.</div></div>',
    '</div>',
  ].join('');

  const result = runPostProcessingChain({
    jobId: 'job_sparse',
    revisionId: 'rev_0000',
    themeId: 'heu_academic_elegant',
    fragmentHtml,
    contentMarkdown,
  });

  assert.equal(result.qualityReport.warnings[0].code, 'CONTENT_DENSITY_LOW');
});

test('quality report warns when preset teaching slots are empty', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: VS',
    '',
    '### Blocks',
    '- Comparison:',
    '  - Left-Title: Old',
    '  - Right-Title: New',
  ].join('\n');
  const fragmentHtml = [
    '<div class="slide layout-comparison-vs-panels">',
    '<div class="title-main">VS</div>',
    '<div class="vs-problem"></div>',
    '<div class="vs-panel"></div>',
    '<div class="vs-panel"></div>',
    '<div class="vs-teaching-summary"></div>',
    '</div>',
  ].join('');

  const result = runPostProcessingChain({
    jobId: 'job_slots',
    revisionId: 'rev_0000',
    themeId: 'heu_academic_elegant',
    fragmentHtml,
    contentMarkdown,
  });

  assert.ok(result.qualityReport.warnings.some((warning) => warning.code === 'REQUIRED_SLOT_EMPTY'));
});

test('quality report warns when architecture spotlight slide misses required slots', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 架构页',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 编码侧：说明。',
    '  - LLM核心：说明。',
    '  - 解码侧：说明。',
    '  - 创新点：说明。',
  ].join('\n');
  const fragmentHtml = [
    '<div class="slide layout-architecture-pipeline-spotlight">',
    '<div class="title-main">架构页</div>',
    '<div class="architecture-summary"></div>',
    '<div class="architecture-stage"></div>',
    '<div class="architecture-stage"></div>',
    '<div class="architecture-stage"></div>',
    '<div class="architecture-spotlight"></div>',
    '</div>',
  ].join('');

  const result = runPostProcessingChain({
    jobId: 'job_arch',
    revisionId: 'rev_0000',
    themeId: 'heu_academic_elegant',
    fragmentHtml,
    contentMarkdown,
  });

  assert.ok(result.qualityReport.warnings.some((warning) => warning.code === 'REQUIRED_SLOT_EMPTY'));
});

test('quality report does not warn rich structured slide as too sparse', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: Structured',
    '',
    '### Blocks',
    '- Definition: Structured content',
  ].join('\n');
  const fragmentHtml = [
    '<div class="slide layout-standard-text-structured">',
    '<div class="title-main">Structured</div>',
    '<div class="content-area">',
    '<div class="structured-lead"><div class="structured-lead-text">Core idea.</div></div>',
    '<div class="surface-card structured-panel">',
    '<div class="structured-section"><div class="structured-section-title">One</div><div class="structured-section-text">Alpha</div></div>',
    '<div class="structured-section"><div class="structured-section-title">Two</div><div class="structured-section-text">Beta</div></div>',
    '<div class="structured-section"><div class="structured-section-title">Three</div><div class="structured-flow"><div class="structured-flow-step">Start</div><div class="structured-flow-step">Ship</div></div></div>',
    '</div>',
    '</div>',
    '</div>',
  ].join('');

  const result = runPostProcessingChain({
    jobId: 'job_structured',
    revisionId: 'rev_0000',
    themeId: 'heu_academic_elegant',
    fragmentHtml,
    contentMarkdown,
  });

  assert.ok(
    !result.qualityReport.warnings.some((warning) => warning.code === 'CONTENT_DENSITY_LOW')
  );
});

test('quality report warns when one repeated required slot is empty', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: VS',
    '',
    '### Blocks',
    '- Comparison:',
    '  - Left-Title: Old',
    '  - Right-Title: New',
  ].join('\n');
  const fragmentHtml = [
    '<div class="slide layout-comparison-vs-panels">',
    '<div class="title-main">VS</div>',
    '<div class="vs-problem">Problem framing</div>',
    '<div class="vs-panel">Filled panel</div>',
    '<div class="vs-panel"></div>',
    '<div class="vs-teaching-summary">Takeaway</div>',
    '</div>',
  ].join('');

  const result = runPostProcessingChain({
    jobId: 'job_partial_slots',
    revisionId: 'rev_0000',
    themeId: 'heu_academic_elegant',
    fragmentHtml,
    contentMarkdown,
  });

  assert.ok(result.qualityReport.warnings.some((warning) => warning.code === 'REQUIRED_SLOT_EMPTY'));
});

test('manifest exposure stays static-only even if fragment contains stale dynamic markers', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 普通页',
    '',
    '### Blocks',
    '- Bullets:',
    '  - One',
  ].join('\n');

  const fragmentHtml = [
    '<div class="slide layout-standard-text"><div class="title-main">普通页</div></div>',
    '<div class="slide layout-dynamic-game-launch" data-dynamic-kind="game"><div class="title-main">互动练习：普通页</div></div>',
    '<div class="slide layout-text-media" data-dynamic-kind="animation"><div class="title-main">动画演示：普通页</div></div>',
  ].join('\n');

  const result = runPostProcessingChain({
    jobId: 'job_dynamic_manifest',
    revisionId: 'rev_0000',
    themeId: 'heu_academic_elegant',
    fragmentHtml,
    contentMarkdown,
  });

  assert.ok(!Object.hasOwn(result.manifest, 'dynamic_slide_count'));
  assert.ok(!Object.hasOwn(result.manifest, 'has_game_pages'));
  assert.ok(!Object.hasOwn(result.manifest, 'has_animation_pages'));
  assert.ok(!Object.hasOwn(result.manifest, 'bundle_required'));
});

test('overflow repair adds compact classes to risky comparison and process slides', () => {
  const fragmentHtml = [
    '<div class="slide layout-standard-text-comparison">',
    '<div class="comparison-summary-bar"><div class="summary-accent"></div><div class="summary-copy">这是一段特别长的总结文案，用来模拟 comparison 页在 HTML 里已经逼近高度极限并准备发生下溢出的情况，因此需要后处理主动压缩。</div></div>',
    '<div class="comparison-grid">',
    '<div class="surface-card comparison-card"><div class="card-title">方案 A</div><div class="card-subtitle">强调快速集成</div></div>',
    '<div class="surface-card comparison-card"><div class="card-title">方案 B</div><div class="card-subtitle">强调底层统一</div></div>',
    '</div>',
    '</div>',
    '<div class="slide layout-standard-text-process">',
    '<div class="process-summary-bar"><div class="summary-copy"><div class="process-summary-title">主线</div><div class="process-summary-meta">这是一段非常长的流程元信息描述，用来模拟 process 页在导出前已经超过安全预算，需要自动收紧。</div></div></div>',
    '<div class="process-grid"></div>',
    '</div>',
  ].join('\n');
  const geometryReport = {
    warnings: [
      { slide_index: 1, code: 'KEY_CONTAINER_OVERFLOW' },
      { slide_index: 2, code: 'ELEMENT_OUTSIDE_SLIDE' },
    ],
  };

  const repaired = repairOverflowLayouts(fragmentHtml, geometryReport);

  assert.equal(repaired.changed, true);
  assert.match(repaired.fragmentHtml, /layout-standard-text-comparison[^"]*layout-overflow-compact/);
  assert.match(repaired.fragmentHtml, /comparison-overflow-compact/);
  assert.match(repaired.fragmentHtml, /方案 A强调快速集成；方案 B强调底层统一。/);
  assert.match(repaired.fragmentHtml, /layout-standard-text-process[^"]*layout-overflow-compact/);
  assert.match(repaired.fragmentHtml, /process-overflow-compact/);
});

test('overflow repair also compacts thesis evidence, architecture spotlight, and card layouts', () => {
  const fragmentHtml = [
    '<div class="slide layout-thesis-evidence-grid">',
    '<div class="content-area"><div class="surface-card thesis-band"><div class="structured-lead-text">主论点很长，需要压缩布局才能留出证据卡空间。</div></div><div class="thesis-evidence-grid"><div class="surface-card evidence-card"><div class="process-index">01</div><div class="card-title">证据一</div></div></div></div>',
    '</div>',
    '<div class="slide layout-architecture-pipeline-spotlight">',
    '<div class="content-area"><div class="surface-card architecture-summary"><div class="structured-lead-text">架构总结特别长，需要给右侧创新点卡片留出更多高度。</div></div><div class="architecture-pipeline"></div><div class="surface-card architecture-spotlight text-support-card"><div class="card-title">创新点</div><div class="card-desc">这是一段特别长的创新点解释文案，用来模拟右侧文本块的严重下溢出，因此需要后处理自动切换到更紧凑的布局模式。</div></div></div>',
    '</div>',
    '<div class="slide">',
    '<div class="content-area card-layout-content"><div class="cards-lead"><div class="cards-lead-title">卡片引导文案很长。</div></div><div class="cards-grid"><div class="surface-card"><div class="card-title">能力一</div></div></div></div>',
    '</div>',
  ].join('\n');
  const geometryReport = {
    warnings: [
      { slide_index: 1, code: 'KEY_CONTAINER_OVERFLOW' },
      { slide_index: 2, code: 'ELEMENT_OVERLAP' },
      { slide_index: 3, code: 'ELEMENT_OUTSIDE_SLIDE' },
    ],
  };

  const repaired = repairOverflowLayouts(fragmentHtml, geometryReport);

  assert.equal(repaired.changed, true);
  assert.match(repaired.fragmentHtml, /layout-thesis-evidence-grid[^"]*layout-overflow-compact/);
  assert.match(repaired.fragmentHtml, /thesis-overflow-compact/);
  assert.match(repaired.fragmentHtml, /evidence-card-head/);
  assert.match(repaired.fragmentHtml, /layout-architecture-pipeline-spotlight[^"]*layout-overflow-compact/);
  assert.match(repaired.fragmentHtml, /architecture-overflow-compact/);
  assert.match(repaired.fragmentHtml, /class="slide[^"]*layout-overflow-compact[^"]*card-layout-overflow-compact/);
});
