const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs/promises');
const os = require('os');
const path = require('path');

const {
  buildDeckDesignPlanPrompt,
  validatePlannerPlanMatchesContent,
  validateDeckDesignPlan,
} = require('../src/domain/deck-plan');
const { rebalanceDeckDesignPlan } = require('../src/domain/deck-plan-rebalance');
const { buildPlannerDigest } = require('../src/domain/planner-digest');
const { runDeckPlanning } = require('../src/services/ppt-service');

test('deck design plan prompt references content digest reference and output', async () => {
  const prompt = await buildDeckDesignPlanPrompt({
    contentPath: '/tmp/job/content.md',
    outputPath: '/tmp/job/deck_design_plan.md',
    plannerDigestPath: '/tmp/job/planner-digest.md',
  });

  assert.match(prompt, /\/tmp\/job\/content\.md/);
  assert.match(prompt, /\/tmp\/job\/deck_design_plan\.md/);
  assert.match(prompt, /\/tmp\/job\/planner-digest\.md/);
  assert.match(prompt, /references\/deck-design-plan\.md/);
  assert.doesNotMatch(prompt, /layout-catalog\.json|component-catalog\.json|theme-heu-academic-elegant\.css/);
  assert.doesNotMatch(prompt, /\{\{CONTENT_PATH\}\}|\{\{OUTPUT_PATH\}\}|\{\{PLANNER_DIGEST_PATH\}\}/);
});

test('planner prompt stays static-only and does not mention dynamic slide fields', async () => {
  const prompt = await buildDeckDesignPlanPrompt({
    contentPath: '/tmp/content.md',
    outputPath: '/tmp/deck_design_plan.md',
    plannerDigestPath: '/tmp/planner-digest.md',
  });

  assert.doesNotMatch(prompt, /Dynamic Brief|Dynamic:/);
  assert.doesNotMatch(prompt, /0-3\s*(个)?\s*(动态页|游戏页|动画页)/);
  assert.doesNotMatch(prompt, /game\.data\.json|animation\.html|games\//);
  assert.match(prompt, /ignore .*notes.*(append|extra).*slide|never add, remove, merge, split, or reorder slides/i);
});

test('planner digest summarizes theme layouts and components compactly', async () => {
  const digest = await buildPlannerDigest({
    themeId: 'heu_academic_elegant',
  });

  assert.match(digest, /Theme/);
  assert.match(digest, /content_blank/);
  assert.match(digest, /standard_text/);
  assert.match(digest, /architecture_pipeline_spotlight/);
  assert.match(digest, /dual_core_support/);
  assert.match(digest, /thesis_evidence_grid/);
  assert.match(digest, /bullet_list/);
  assert.match(digest, /Brand/);
  assert.doesNotMatch(digest, /- standard_text_structured \|/);
  assert.ok(digest.split(/\r?\n/).length < 220);
});

test('deck design plan validation requires the three supported sections', () => {
  const validPlan = [
    '# Deck Design Plan',
    '',
    '## Metadata',
    '- Deck name: Demo',
    '- Visual style: Consulting',
    '- Page count: 2',
    '',
    '## Design Specification',
    '- Follow CRAP principles.',
    '',
    '## Content Outline',
    '### Slide 1',
    '- Layout: cover',
    '',
  ].join('\n');

  assert.doesNotThrow(() => validateDeckDesignPlan(validPlan));
  assert.throws(
    () => validateDeckDesignPlan('## Metadata\n## Content Outline\n'),
    /deck_design_plan.md is missing required section: Design Specification/
  );
});

test('deck design plan validation accepts teaching recipe fields', () => {
  const plan = [
    '# Deck Design Plan',
    '',
    '## Metadata',
    '- Deck name: Demo',
    '',
    '## Design Specification',
    '- Keep prompts short.',
    '',
    '## Content Outline',
    '### Slide 1',
    '- Layout: comparison_vs',
    '- Components: bullet_list',
    '- Teaching Objective: Explain why protocol standardization matters.',
    '- Teaching Recipe: problem + contrast + summary',
    '- Density: full',
    '- Fallback: split slide if left/right panels exceed 3 points each',
  ].join('\n');

  assert.doesNotThrow(() => validateDeckDesignPlan(plan));
});

test('planner/content validator rejects invented slides before expansion', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 源页一',
    '',
    '### Blocks',
    '- Bullets:',
    '  - One',
    '',
    '---',
    '',
    '## Slide 2',
    '- Role: content',
    '- Title: 源页二',
    '',
    '### Blocks',
    '- Bullets:',
    '  - Two',
  ].join('\n');
  const plan = [
    '# Deck Design Plan',
    '',
    '## Metadata',
    '- Deck name: Demo',
    '',
    '## Design Specification',
    '- Keep it concise.',
    '',
    '## Content Outline',
    '### Slide 1',
    '- **Slide**: 1',
    '- **Role**: content',
    '- **Title**: 源页一',
    '',
    '### Slide 2',
    '- **Slide**: 2',
    '- **Role**: content',
    '- **Title**: 概念匹配练习',
    '',
    '### Slide 3',
    '- **Slide**: 3',
    '- **Role**: content',
    '- **Title**: 源页二',
  ].join('\n');

  assert.throws(
    () => validatePlannerPlanMatchesContent({ deckPlanMarkdown: plan, contentMarkdown }),
    /invented|not present in content/i
  );
});

test('deck planning writes and validates deck_design_plan.md before slide generation', async () => {
  const revisionDir = await fs.mkdtemp(path.join(os.tmpdir(), 'html2ppt-deck-plan-'));
  const revisionPaths = {
    revisionDir,
    contentPath: path.join(revisionDir, 'content.md'),
    deckDesignPlanPath: path.join(revisionDir, 'deck_design_plan.md'),
    deckDesignPlanPromptPath: path.join(revisionDir, 'deck-design-plan.prompt.txt'),
    plannerDigestPath: path.join(revisionDir, 'planner-digest.md'),
    deckPlanningReportPath: path.join(revisionDir, 'deck-planning-report.json'),
  };
  await fs.writeFile(
    revisionPaths.contentPath,
    [
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
    ].join('\n'),
    'utf8'
  );

  const calls = [];
  const runner = {
    async run({ promptPath, outputPath, prompt }) {
      calls.push({ promptPath, outputPath, prompt });
      await fs.writeFile(
        outputPath,
        [
          '# Deck Design Plan',
          '',
          '## Metadata',
          '- Deck name: Demo',
          '- Visual style: Academic clean',
          '- Page count: 1',
          '',
          '## Design Specification',
          '- Follow CRAP principles.',
          '',
          '## Content Outline',
          '### Slide 1',
          '- Role: cover',
          '- Title: Demo',
          '- Layout: cover',
          '- Components: none',
          '',
        ].join('\n'),
        'utf8'
      );
    },
  };

  const plan = await runDeckPlanning({
    runner,
    revisionPaths,
    themeId: 'heu_academic_elegant',
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].promptPath, revisionPaths.deckDesignPlanPromptPath);
  assert.equal(calls[0].outputPath, revisionPaths.deckDesignPlanPath);
  assert.match(calls[0].prompt, /deck_design_plan\.md/);
  assert.match(calls[0].prompt, /planner-digest\.md/);
  assert.match(plan, /## Metadata[\s\S]*## Design Specification[\s\S]*## Content Outline/);
  assert.equal(await fs.readFile(revisionPaths.deckDesignPlanPath, 'utf8'), plan);
  assert.match(await fs.readFile(revisionPaths.plannerDigestPath, 'utf8'), /Theme/);

  const planningReport = JSON.parse(await fs.readFile(revisionPaths.deckPlanningReportPath, 'utf8'));
  assert.ok(planningReport.duration_ms >= 0);
  assert.ok(planningReport.prompt_chars > 0);
  assert.ok(planningReport.content_chars > 0);
  assert.ok(planningReport.planner_digest_chars > 0);
  assert.equal(planningReport.rebalanced, false);
});

test('deck plan rebalancer routes dense bullet pages into new semantic layouts', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 前沿架构剖析：NExT-GPT的设计哲学',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 编码侧：输入特征对齐到 LLM。',
    '  - LLM核心：统一理解与调度。',
    '  - 解码侧：信号词元驱动多模态生成。',
    '  - 创新点：模态切换指令微调。',
    '',
    '---',
    '',
    '## Slide 2',
    '- Role: content',
    '- Title: 音频离散化：语义与声学的解耦表征',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 语义词元：表示说了什么。',
    '  - 声学词元：表示如何说。',
    '  - 残差向量量化：保留高频细节。',
    '  - 优势：实现内容与风格解耦控制。',
    '',
    '---',
    '',
    '## Slide 3',
    '- Role: content',
    '- Title: 核心挑战：为何必须走向离散化？',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 原因一：连续空间不适合离散预测。',
    '  - 原因二：生成建模复杂度过高。',
    '  - 原因三：统一表征需要通用符号。',
    '  - 原因四：离散符号更利于推理。',
  ].join('\n');
  const deckPlan = [
    '# Deck Design Plan',
    '',
    '## Metadata',
    '- Deck name: Demo',
    '',
    '## Design Specification',
    '- Keep it concise.',
    '',
    '## Content Outline',
    '### Slide 1',
    '- **Layout Level**: frame',
    '- **Layout**: standard_text_structured',
    '- **Components**: none',
    '- **Teaching Recipe**: 核心判断 + 分层解释 + 小步骤',
    '- **Density**: full',
    '- **Fallback**: standard_text_structured',
    '',
    '### Slide 2',
    '- **Layout Level**: frame',
    '- **Layout**: standard_text_structured',
    '- **Components**: none',
    '- **Teaching Recipe**: 核心判断 + 分层解释 + 小步骤',
    '- **Density**: full',
    '- **Fallback**: standard_text_structured',
    '',
    '### Slide 3',
    '- **Layout Level**: frame',
    '- **Layout**: standard_text_structured',
    '- **Components**: none',
    '- **Teaching Recipe**: 核心判断 + 分层解释 + 小步骤',
    '- **Density**: full',
    '- **Fallback**: standard_text_structured',
  ].join('\n');

  const rebalanced = rebalanceDeckDesignPlan({
    deckPlanMarkdown: deckPlan,
    contentMarkdown,
  });

  assert.match(rebalanced, /### Slide 1[\s\S]*- \*\*Layout\*\*: architecture_pipeline_spotlight/);
  assert.match(rebalanced, /### Slide 2[\s\S]*- \*\*Layout\*\*: dual_core_support/);
  assert.match(rebalanced, /### Slide 3[\s\S]*- \*\*Layout\*\*: thesis_evidence_grid/);
});

test('deck plan rebalancer reroutes generic bullet layouts beyond standard_text_structured', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 前沿架构剖析：NExT-GPT的设计哲学',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 编码侧：输入特征对齐到 LLM。',
    '  - LLM核心：统一理解与调度。',
    '  - 解码侧：信号词元驱动多模态生成。',
    '  - 创新点：模态切换指令微调。',
    '',
    '---',
    '',
    '## Slide 2',
    '- Role: content',
    '- Title: 音频离散化：语义与声学的解耦表征',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 语义词元：表示说了什么。',
    '  - 声学词元：表示如何说。',
    '  - 残差向量量化：保留高频细节。',
    '  - 优势：实现内容与风格解耦控制。',
  ].join('\n');
  const deckPlan = [
    '# Deck Design Plan',
    '',
    '## Metadata',
    '- Deck name: Demo',
    '',
    '## Design Specification',
    '- Keep it concise.',
    '',
    '## Content Outline',
    '### Slide 1',
    '- **Layout Level**: frame',
    '- **Layout**: thesis_evidence_grid',
    '- **Components**: none',
    '- **Teaching Recipe**: 核心判断 + 四个论点',
    '- **Density**: full',
    '- **Fallback**: standard_text',
    '',
    '### Slide 2',
    '- **Layout Level**: frame',
    '- **Layout**: standard_text',
    '- **Components**: bullet_list',
    '- **Teaching Recipe**: 核心判断 + 四个论点',
    '- **Density**: full',
    '- **Fallback**: thesis_evidence_grid',
  ].join('\n');

  const rebalanced = rebalanceDeckDesignPlan({
    deckPlanMarkdown: deckPlan,
    contentMarkdown,
  });

  assert.match(rebalanced, /### Slide 1[\s\S]*- \*\*Layout\*\*: architecture_pipeline_spotlight/);
  assert.match(rebalanced, /### Slide 2[\s\S]*- \*\*Layout\*\*: dual_core_support/);
});

test('deck plan rebalancer ignores notes that request dynamic companion slides', () => {
  const contentMarkdown = [
    '# Deck',
    '- Title: Demo',
    '',
    '---',
    '',
    '## Slide 1',
    '- Role: content',
    '- Title: 音频离散化',
    '',
    '### Blocks',
    '- Bullets:',
    '  - 语义词元：表示说了什么。',
    '  - 声学词元：表示如何说。',
    '  - 残差向量量化：保留高频细节。',
    '  - 优势：实现内容与风格解耦控制。',
    '',
    '### Notes',
    '这一页同时作为课堂互动锚点。',
    '请在本页后追加一个拖拽匹配游戏页，让学生把术语与定义进行匹配。',
    '',
    '---',
    '',
    '## Slide 2',
    '- Role: content',
    '- Title: 统一对齐',
    '',
    '### Blocks',
    '- Process:',
    '  - Step-Title: 编码与量化',
    '    Step-Text: 先离散化。',
    '  - Step-Title: 嵌入映射',
    '    Step-Text: 再统一空间。',
    '',
    '### Notes',
    '这一页同时作为动画演示锚点。',
    '请在本页后追加一个动画页，按阶段展示跨模态对齐流程。',
  ].join('\n');
  const deckPlan = [
    '# Deck Design Plan',
    '',
    '## Metadata',
    '- Deck name: Demo',
    '',
    '## Design Specification',
    '- Keep it concise.',
    '',
    '## Content Outline',
    '### Slide 1',
    '- **Slide**: 1',
    '- **Role**: content',
    '- **Title**: 音频离散化',
    '- **Layout Level**: frame',
    '- **Layout**: thesis_evidence_grid',
    '- **Components**: none',
    '- **Density**: full',
    '- **Fallback**: standard_text',
    '',
    '### Slide 2',
    '- **Slide**: 2',
    '- **Role**: content',
    '- **Title**: 统一对齐',
    '- **Layout Level**: frame',
    '- **Layout**: standard_text_process_grid',
    '- **Components**: process_steps',
    '- **Density**: standard',
    '- **Fallback**: execution_pipeline',
  ].join('\n');

  const rebalanced = rebalanceDeckDesignPlan({
    deckPlanMarkdown: deckPlan,
    contentMarkdown,
  });

  assert.doesNotMatch(rebalanced, /Dynamic:|Dynamic Brief:/);
});
