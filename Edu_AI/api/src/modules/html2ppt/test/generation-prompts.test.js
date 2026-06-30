const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildSlideExecutionPrompt,
  extractSlidePlanEntry,
  selectFocusedCatalogKeys,
} = require('../src/domain/generation-prompts');

test('focused catalog key selection uses the current slide plan only', () => {
  const planEntry = [
    '### Slide 6',
    '- Layout: comparison_vs',
    '- Components: bullet_list, matrix_2x2',
    '- Density: full',
  ].join('\n');

  const selected = selectFocusedCatalogKeys(planEntry);

  assert.deepEqual(selected.layouts, ['comparison_vs']);
  assert.deepEqual(selected.components, ['bullet_list', 'matrix_2x2']);
});

test('focused catalog key selection accepts bold deck plan fields', () => {
  const planEntry = [
    '### Slide 6',
    '- **Layout**: content_blank',
    '- **Components**: bullet_list, timeline',
    '- **Density**: full',
  ].join('\n');

  const selected = selectFocusedCatalogKeys(planEntry);

  assert.deepEqual(selected.layouts, ['content_blank']);
  assert.deepEqual(selected.components, ['bullet_list', 'timeline']);
});

test('focused catalog key selection ignores none components', () => {
  const selected = selectFocusedCatalogKeys(['### Slide 1', '- Layout: cover', '- Components: None'].join('\n'));

  assert.deepEqual(selected.layouts, ['cover']);
  assert.deepEqual(selected.components, []);
});

test('focused catalog key selection ignores nested catalog-looking bullets', () => {
  const planEntry = [
    '### Slide 10: Title',
    '- Layout: comparison_vs',
    '- Components: bullet_list, matrix_2x2',
    '- Visible Content:',
    '  - Layout: media_focus',
    '  - Components: image_frame',
  ].join('\n');

  const selected = selectFocusedCatalogKeys(planEntry);

  assert.deepEqual(selected.layouts, ['comparison_vs']);
  assert.deepEqual(selected.components, ['bullet_list', 'matrix_2x2']);
});

test('slide plan extraction returns only the requested slide entry', () => {
  const deckPlan = [
    '# Deck Design Plan',
    '',
    '## Content Outline',
    '### Slide 5',
    '- Layout: media_focus',
    '- Components: image_frame',
    '',
    '### Slide 6',
    '- Layout: comparison_vs',
    '- Components: bullet_list',
    '',
    '### Slide 7',
    '- Layout: closing',
    '- Components: none',
  ].join('\n');

  const entry = extractSlidePlanEntry(deckPlan, 6);

  assert.match(entry, /### Slide 6/);
  assert.match(entry, /comparison_vs/);
  assert.doesNotMatch(entry, /media_focus/);
  assert.doesNotMatch(entry, /closing/);
});

test('slide execution prompt includes focused catalog summary and omits unrelated layouts', async () => {
  const prompt = await buildSlideExecutionPrompt({
    contentPath: '/tmp/content.md',
    deckDesignPlanPath: '/tmp/deck_design_plan.md',
    outputPath: '/tmp/slide-06.fragment.html',
    themeCssPath: '/tmp/theme.css',
    targetSlidePlan: [
      '### Slide 6',
      '- Layout: comparison_vs',
      '- Components: bullet_list',
    ].join('\n'),
    targetSlideMarkdown: '## Slide 6\n- Role: content\n- Title: VS',
    slideIndex: 6,
    totalSlides: 10,
    deckOutline: '6. VS / Role=content / Blocks=Comparison',
  });

  assert.match(prompt, /Focused catalog summary/);
  assert.match(prompt, /comparison_vs/);
  assert.match(prompt, /bullet_list/);
  assert.match(prompt, /standard_text_comparison/);
  assert.doesNotMatch(prompt, /media_focus/);
  assert.doesNotMatch(prompt, /\{\{CONTENT_PATH\}\}/);
});

test('focused catalog summary still includes deprecated layouts when explicitly selected', async () => {
  const prompt = await buildSlideExecutionPrompt({
    contentPath: '/tmp/content.md',
    deckDesignPlanPath: '/tmp/deck_design_plan.md',
    outputPath: '/tmp/slide.fragment.html',
    themeCssPath: '/tmp/theme.css',
    targetSlidePlan: [
      '### Slide 5',
      '- Layout: standard_text_structured',
      '- Components: none',
    ].join('\n'),
    targetSlideMarkdown: '## Slide 5\n- Role: content\n- Title: Legacy',
    slideIndex: 5,
    totalSlides: 10,
    deckOutline: '5. Legacy / Role=content / Blocks=Bullets',
  });

  assert.match(prompt, /standard_text_structured/);
});
