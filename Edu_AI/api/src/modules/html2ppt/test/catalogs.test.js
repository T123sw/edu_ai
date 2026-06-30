const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs/promises');
const os = require('os');
const path = require('path');

const {
  getComponent,
  getLayout,
  listLayoutKeys,
  loadCatalogBundle,
  summarizeCatalogEntries,
  loadJsonCatalog,
} = require('../src/domain/catalogs');

test('catalog bundle loads layouts and components from references', async () => {
  const bundle = await loadCatalogBundle();

  assert.equal(bundle.layouts.version, 1);
  assert.equal(bundle.components.version, 1);
  assert.ok(getLayout(bundle, 'content_blank'));
  assert.ok(getLayout(bundle, 'media_focus'));
  assert.ok(getComponent(bundle, 'quote_callout'));
  assert.ok(getComponent(bundle, 'process_steps'));
  assert.ok(listLayoutKeys(bundle).includes('content_blank'));
});

test('catalog entries point to existing template files', async () => {
  const bundle = await loadCatalogBundle();
  const sourcePaths = [
    ...Object.values(bundle.layouts.layouts).map((entry) => entry.source),
    ...Object.values(bundle.components.components).map((entry) => entry.source),
  ];

  for (const sourcePath of sourcePaths) {
    const absolutePath = path.join(__dirname, '..', sourcePath);
    await fs.access(absolutePath);
  }
});

test('catalog sources use the split format directories by entry kind', async () => {
  const bundle = await loadCatalogBundle();

  for (const [layoutKey, entry] of Object.entries(bundle.layouts.layouts)) {
    if (entry.kind === 'frame') {
      assert.match(entry.source, /^format\/frame\//, `${layoutKey} should use format/frame`);
    }
    if (entry.kind === 'preset_slide') {
      assert.match(entry.source, /^format\/presets\//, `${layoutKey} should use format/presets`);
    }
  }

  for (const [componentKey, entry] of Object.entries(bundle.components.components)) {
    assert.match(entry.source, /^format\/components\//, `${componentKey} should use format/components`);
  }
});

test('format root keeps shared css only and no body templates', async () => {
  const formatRoot = path.join(__dirname, '..', 'format');
  const rootFiles = (await fs.readdir(formatRoot, { withFileTypes: true }))
    .filter((entry) => entry.isFile())
    .map((entry) => entry.name);

  assert.deepEqual(rootFiles.sort(), ['layout.css']);
});

test('runtime references replace obsolete root prompt and layout contract files', async () => {
  const repoRoot = path.join(__dirname, '..');

  await fs.access(path.join(repoRoot, 'prompts', 'slide-executor.md'));
  await fs.access(path.join(repoRoot, 'references', 'content-protocol.md'));
  await fs.access(path.join(repoRoot, 'references', 'layout-catalog.json'));
  await fs.access(path.join(repoRoot, 'references', 'component-catalog.json'));
  await fs.access(path.join(repoRoot, 'references', 'html-to-pptx-restrict.md'));

  await assert.rejects(() => fs.access(path.join(repoRoot, 'html-generation-entry-prompt.md')));
  await assert.rejects(() => fs.access(path.join(repoRoot, 'layout-contracts.md')));
});

test('catalog loader rejects malformed JSON catalog shape', async () => {
  const workDir = await fs.mkdtemp(path.join(os.tmpdir(), 'html2ppt-catalog-test-'));
  const catalogPath = path.join(workDir, 'bad.json');
  await fs.writeFile(catalogPath, JSON.stringify({ version: 1 }), 'utf8');

  await assert.rejects(
    () => loadJsonCatalog(catalogPath, 'layouts'),
    /Catalog layouts must contain an object property named layouts/
  );
});

test('catalog entries expose compact teaching metadata', async () => {
  const bundle = await loadCatalogBundle();
  const bullet = getComponent(bundle, 'bullet_list');
  const comparisonVs = getLayout(bundle, 'comparison_vs');

  assert.equal(bullet.teaching_recipe, '结论 + 2-4 个解释点 + 可选例子或课堂提示');
  assert.deepEqual(bullet.content_slots, ['takeaway', 'points', 'example']);
  assert.equal(bullet.min_content_units, 3);
  assert.equal(bullet.max_content_units, 6);
  assert.ok(bullet.chart_affordances.includes('none'));

  assert.equal(comparisonVs.teaching_recipe, '背景问题 + 左侧痛点 + 右侧方案 + 底部教学总结');
  assert.deepEqual(comparisonVs.content_slots, ['problem', 'left_points', 'right_points', 'teaching_summary']);
  assert.equal(comparisonVs.fallback_layout, 'standard_text_comparison');
});

test('chart-style components are registered and point to existing PPT-safe templates', async () => {
  const bundle = await loadCatalogBundle();
  const chartKeys = ['metric_strip', 'bar_chart', 'matrix_2x2', 'timeline', 'relationship_map'];

  for (const key of chartKeys) {
    const entry = getComponent(bundle, key);
    assert.ok(entry, `${key} should be registered`);
    assert.match(entry.source, /^format\/components\//);
    assert.ok(entry.chart_affordances.length > 0);
    assert.ok(entry.content_slots.length > 0);
    if (entry.fallback_layout) {
      assert.ok(getLayout(bundle, entry.fallback_layout), `${key} fallback layout should be registered`);
    }
    await fs.access(path.join(__dirname, '..', entry.source));
  }
});

test('catalog summary helper returns focused entries only', async () => {
  const bundle = await loadCatalogBundle();

  const summary = summarizeCatalogEntries(bundle, {
    layouts: ['comparison_vs'],
    components: ['bullet_list', 'matrix_2x2'],
  });
  const parsed = JSON.parse(summary);

  assert.deepEqual(Object.keys(parsed), ['layouts', 'components']);
  assert.deepEqual(Object.keys(parsed.layouts), ['comparison_vs']);
  assert.deepEqual(Object.keys(parsed.components), ['bullet_list', 'matrix_2x2']);

  assert.deepEqual(Object.keys(parsed.layouts.comparison_vs).sort(), [
    'fallback_layout',
    'hard_constraints',
    'max_content_units',
    'min_content_units',
    'source',
    'teaching_recipe',
    'chart_affordances',
    'content_slots',
  ].sort());
  assert.deepEqual(Object.keys(parsed.components.bullet_list).sort(), [
    'fallback_layout',
    'hard_constraints',
    'max_content_units',
    'min_content_units',
    'source',
    'teaching_recipe',
    'chart_affordances',
    'content_slots',
  ].sort());

  assert.equal(parsed.layouts.comparison_vs.teaching_recipe, '背景问题 + 左侧痛点 + 右侧方案 + 底部教学总结');
  assert.deepEqual(parsed.layouts.comparison_vs.content_slots, ['problem', 'left_points', 'right_points', 'teaching_summary']);
  assert.equal(parsed.components.bullet_list.teaching_recipe, '结论 + 2-4 个解释点 + 可选例子或课堂提示');
  assert.deepEqual(parsed.components.bullet_list.content_slots, ['takeaway', 'points', 'example']);
  assert.equal(parsed.components.matrix_2x2.teaching_recipe, '两个判断维度 + 四类结论');
  assert.deepEqual(parsed.components.matrix_2x2.content_slots, ['x_axis', 'y_axis', 'cells']);
  assert.ok(!Object.prototype.hasOwnProperty.call(parsed.layouts, 'media_focus'));
  assert.ok(!Object.prototype.hasOwnProperty.call(parsed.layouts, 'execution_pipeline'));
});
