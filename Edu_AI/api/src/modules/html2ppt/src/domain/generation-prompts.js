const fs = require('fs/promises');
const path = require('path');
const { repoRoot } = require('../config');
const {
  defaultComponentCatalogPath,
  defaultLayoutCatalogPath,
  getComponent,
  getLayout,
  loadCatalogBundle,
  summarizeCatalogEntries,
} = require('./catalogs');
const { parsePlanEntryFields } = require('./deck-plan-outline');
const { htmlRestrictPath } = require('./deck-plan');
const { resolveThemeCss } = require('./themes');

const slideExecutorPromptPath = path.join(repoRoot, 'prompts', 'slide-executor.md');
const promptPaths = {
  formatDir: path.join(repoRoot, 'format'),
  layoutCssPath: path.join(repoRoot, 'format', 'layout.css'),
  brandConfigPath: path.join(repoRoot, 'style', 'theme-brand-config.json'),
  contentProtocolPath: path.join(repoRoot, 'references', 'content-protocol.md'),
  layoutCatalogPath: defaultLayoutCatalogPath,
  componentCatalogPath: defaultComponentCatalogPath,
  htmlRestrictPath,
  agentWorkflowPath: path.join(repoRoot, 'references', 'agent-workflow.md'),
};

const runtimeReplacementKeys = {
  CONTENT_PATH: 'contentPath',
  DECK_DESIGN_PLAN_PATH: 'deckDesignPlanPath',
  THEME_CSS_PATH: 'themeCssPath',
  OUTPUT_PATH: 'outputPath',
  FORMAT_DIR: 'formatDir',
  LAYOUT_CSS_PATH: 'layoutCssPath',
  BRAND_CONFIG_PATH: 'brandConfigPath',
  CONTENT_PROTOCOL_PATH: 'contentProtocolPath',
  LAYOUT_CATALOG_PATH: 'layoutCatalogPath',
  COMPONENT_CATALOG_PATH: 'componentCatalogPath',
  HTML_RESTRICT_PATH: 'htmlRestrictPath',
  AGENT_WORKFLOW_PATH: 'agentWorkflowPath',
};

async function readEntryPromptTemplate() {
  return fs.readFile(slideExecutorPromptPath, 'utf8');
}

function toPromptPath(filePath) {
  return String(filePath || '').replace(/\\/g, '/');
}

function applyRuntimePromptPaths(template, replacements = {}) {
  const values = {
    ...promptPaths,
    contentPath: '',
    deckDesignPlanPath: '',
    themeCssPath: resolveThemeCss('heu_academic_elegant'),
    outputPath: '',
    ...replacements,
  };

  return Object.entries(runtimeReplacementKeys).reduce((output, [placeholderKey, camelCaseKey]) => {
    const replacement = values[placeholderKey] ?? values[`{{${placeholderKey}}}`] ?? values[camelCaseKey] ?? '';
    return output.replaceAll(`{{${placeholderKey}}}`, toPromptPath(replacement));
  }, String(template || ''));
}

function splitKeyList(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function selectFocusedCatalogKeys(targetSlidePlan = '') {
  const fields = parsePlanEntryFields(targetSlidePlan);
  const selected = {
    layouts: splitKeyList(fields.layout?.value),
    components: splitKeyList(fields.components?.value).filter((componentKey) => componentKey.toLowerCase() !== 'none'),
  };

  return {
    layouts: [...new Set(selected.layouts)],
    components: [...new Set(selected.components)],
  };
}

function expandFocusedCatalogKeys(bundle, selected = {}) {
  const layouts = new Set(selected.layouts || []);
  const components = new Set(selected.components || []);

  for (const layoutKey of [...layouts]) {
    const entry = getLayout(bundle, layoutKey);
    if (entry?.fallback_layout) {
      layouts.add(entry.fallback_layout);
    }
  }

  for (const componentKey of [...components]) {
    const entry = getComponent(bundle, componentKey);
    if (entry?.fallback_layout) {
      layouts.add(entry.fallback_layout);
    }
  }

  return {
    layouts: [...layouts],
    components: [...components],
  };
}

function extractSlidePlanEntry(deckPlan = '', slideIndex) {
  const targetSlideIndex = Number(slideIndex);
  if (!Number.isInteger(targetSlideIndex) || targetSlideIndex < 1) {
    return '';
  }

  const lines = String(deckPlan || '').split(/\r?\n/);
  const slideHeadingPattern = /^###\s+Slide\s+(\d+)\b/i;
  let start = -1;
  let end = lines.length;

  for (let index = 0; index < lines.length; index += 1) {
    const match = lines[index].match(slideHeadingPattern);
    if (!match) continue;

    if (start !== -1) {
      end = index;
      break;
    }

    if (Number(match[1]) === targetSlideIndex) {
      start = index;
    }
  }

  if (start === -1) return '';
  return lines.slice(start, end).join('\n').trim();
}

async function buildSlideExecutionPrompt({
  contentPath,
  deckDesignPlanPath,
  outputPath,
  themeCssPath = resolveThemeCss('heu_academic_elegant'),
  targetSlidePlan = '',
  targetSlideMarkdown = '',
  slideIndex,
  totalSlides,
  deckOutline = '',
}) {
  const template = await readEntryPromptTemplate();
  const normalized = applyRuntimePromptPaths(template, {
    contentPath,
    deckDesignPlanPath,
    outputPath,
    themeCssPath,
  });
  const catalogBundle = await loadCatalogBundle();
  const focusedCatalog = summarizeCatalogEntries(
    catalogBundle,
    expandFocusedCatalogKeys(catalogBundle, selectFocusedCatalogKeys(targetSlidePlan))
  );

  return `${normalized}

## 运行时要求
- 当前任务实际使用的内容文件：\`${contentPath}\`
- 当前任务实际使用的 deck design plan：\`${deckDesignPlanPath}\`
- 当前任务实际使用的主题 CSS：\`${themeCssPath}\`
- 目标输出路径：\`${outputPath}\`
- 必须先读取 deck design plan，并执行其中对本页声明的 layout、components、视觉风格和全局注意事项。
- 如果内容里的 Media block 含有 \`Local-Path\` 或 \`Local-Poster-Path\`，必须优先使用这些本地相对路径。
- 请直接把最终 HTML fragment 写入上面的目标文件。
- 不要修改仓库根目录的 \`content.md\`，也不要写入其他无关文件。

## Focused catalog summary
\`\`\`json
${focusedCatalog}
\`\`\`

## Target slide plan
${targetSlidePlan || '(No matching slide plan entry found.)'}

## 单页并行生成覆盖规则
- 现在是并行生成模式：你只生成第 ${slideIndex} / ${totalSlides} 页。
- 必须只输出一个 slide 根节点，不能输出其它页，不能输出完整 HTML 文档。
- 仍然使用完整内容文件理解上下文，但本次只能把“目标页源码”填入页面。
- 目标输出路径：\`${outputPath}\`
- 请直接把这一页 HTML fragment 写入目标输出路径。

## 全 Deck 页序上下文
${deckOutline}

## 目标页源码
\`\`\`md
${String(targetSlideMarkdown || '').trim()}
\`\`\`
`;
}

module.exports = {
  applyRuntimePromptPaths,
  buildSlideExecutionPrompt,
  extractSlidePlanEntry,
  selectFocusedCatalogKeys,
};
