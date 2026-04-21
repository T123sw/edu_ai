const fs = require('fs/promises');
const path = require('path');
const crypto = require('crypto');
const { repoRoot } = require('../config');
const { AppError } = require('../domain/errors');
const { parseContentProtocol, parseSingleSlideContent } = require('../domain/content-protocol');
const { defaultComponentCatalogPath, defaultLayoutCatalogPath } = require('../domain/catalogs');
const {
  applyRuntimePromptPaths,
  buildSlideExecutionPrompt,
  extractSlidePlanEntry,
} = require('../domain/generation-prompts');
const { buildPlannerDigest } = require('../domain/planner-digest');
const { rebalanceDeckDesignPlan } = require('../domain/deck-plan-rebalance');
const { mergeQualityReports } = require('../domain/layout-quality');
const {
  buildDeckDesignPlanPrompt,
  htmlRestrictPath,
  validateDeckDesignPlan,
  validatePlannerPlanMatchesContent,
} = require('../domain/deck-plan');
const { nowIso, withLifecycleFields } = require('../domain/status');
const { getTheme, resolveThemeCss } = require('../domain/themes');
const { extractSlides, replaceSlide, inferLayout, inferTitle } = require('../domain/fragment');
const { buildStandaloneHtmlFromFragment } = require('../lib/build-standalone-html');
const { exportHtmlToPptx } = require('../lib/export-html-to-pptx');
const { ensureDir, fileExists, hashRequestForIdempotency, readJson, writeJson } = require('../lib/file-utils');
const { inspectHtmlLayout } = require('../lib/layout-geometry-inspector');
const { localizeMediaAssets } = require('../lib/media-assets');
const {
  createJob,
  createRevision,
  findByIdempotency,
  getJob,
  getRequest,
  getRevision,
  getRevisionPaths,
  initStore,
  listJobIds,
  listRevisionIds,
  updateJob,
  updateRevision,
} = require('../store/job-store');

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

function requireFresh(modulePath) {
  const resolved = require.resolve(modulePath);
  delete require.cache[resolved];
  return require(resolved);
}

function makeJobId() {
  return `job_${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`;
}

function buildJobError(error) {
  return {
    code: error.code || 'INTERNAL_ERROR',
    message: error.message || 'Unknown error',
    details: error.details || undefined,
  };
}

function validateCreatePayload(payload) {
  if (!payload || typeof payload !== 'object') {
    throw new AppError('INVALID_REQUEST', 'Request body must be a JSON object.', 400);
  }

  if (!String(payload.content_markdown || '').trim()) {
    throw new AppError('INVALID_REQUEST', 'content_markdown is required.', 400);
  }

  if (!String(payload.theme_id || '').trim()) {
    throw new AppError('INVALID_REQUEST', 'theme_id is required.', 400);
  }

  parseContentProtocol(payload.content_markdown);

  const metadata = payload.metadata || {};
  const required = ['request_id', 'timestamp', 'idempotency_key', 'user_id'];
  for (const key of required) {
    if (!String(metadata[key] || '').trim()) {
      throw new AppError('INVALID_REQUEST', `metadata.${key} is required.`, 400);
    }
  }
}

function validateRevisionPayload(payload) {
  if (!payload || typeof payload !== 'object') {
    throw new AppError('INVALID_REQUEST', 'Request body must be a JSON object.', 400);
  }

  if (payload.mode !== 'single_slide') {
    throw new AppError('INVALID_REVISION_MODE', 'v1 only supports mode=single_slide.', 400);
  }

  if (!Array.isArray(payload.target_slides) || payload.target_slides.length !== 1) {
    throw new AppError(
      'INVALID_TARGET_SLIDES',
      'v1 requires target_slides to contain exactly one slide index.',
      400
    );
  }

  if (!String(payload.updated_content || '').trim() && !String(payload.user_instruction || '').trim()) {
    throw new AppError(
      'EMPTY_REVISION_INPUT',
      'updated_content and user_instruction cannot both be empty.',
      400
    );
  }

  if (String(payload.updated_content || '').trim()) {
    parseSingleSlideContent(payload.updated_content);
  }
}

function toArtifactUrl(jobId, revisionId, fileName) {
  return `/ppt/artifacts/${encodeURIComponent(jobId)}/${encodeURIComponent(revisionId)}/${encodeURIComponent(fileName)}`;
}

function buildDeckOutline(slides) {
  return slides
    .map((slide, index) => {
      return `${index + 1}. ${slide.title || `Slide ${slide.slide_number}`} / Role=${slide.role || 'unknown'} / Blocks=${
        slide.blockTypes.join(', ') || 'none'
      }`;
    })
    .join('\n');
}

async function runInitialSlideGeneration({ runner, runtimeContent, revisionPaths, themeId }) {
  const parsed = parseContentProtocol(runtimeContent);
  const slidesDir = path.join(revisionPaths.revisionDir, 'slides');
  await ensureDir(slidesDir);

  const deckOutline = buildDeckOutline(parsed.slides);
  const deckDesignPlan = await fs.readFile(revisionPaths.deckDesignPlanPath, 'utf8');
  const themeCssPath = resolveThemeCss(themeId);
  const totalSlides = parsed.slides.length;
  const tasks = parsed.slides.map(async (slide, index) => {
    const slideIndex = index + 1;
    const paddedIndex = String(slideIndex).padStart(2, '0');
    const promptPath = path.join(slidesDir, `slide-${paddedIndex}.prompt.txt`);
    const outputPath = path.join(slidesDir, `slide-${paddedIndex}.fragment.html`);
    const prompt = await buildSlideExecutionPrompt({
      contentPath: revisionPaths.contentPath,
      deckDesignPlanPath: revisionPaths.deckDesignPlanPath,
      outputPath,
      themeCssPath,
      targetSlidePlan: extractSlidePlanEntry(deckDesignPlan, slideIndex),
      targetSlideMarkdown: (slide.rawLines || []).join('\n').trim(),
      slideIndex,
      totalSlides,
      deckOutline,
    });

    await fs.writeFile(promptPath, prompt, 'utf8');
    await runner.run({
      promptPath,
      outputPath,
      workspaceDir: revisionPaths.revisionDir,
      prompt,
    });

    const slideHtml = await fs.readFile(outputPath, 'utf8');
    const extracted = extractSlides(slideHtml);
    if (extracted.length !== 1) {
      throw new AppError(
        'AGENT_GENERATION_FAILED',
        `Parallel slide generation expected exactly one .slide for slide ${slideIndex}, got ${extracted.length}.`,
        500
      );
    }
    return extracted[0];
  });

  const slideFragments = await Promise.all(tasks);
  const mergedFragmentHtml = `${slideFragments.join('\n')}\n`;
  await fs.writeFile(revisionPaths.fragmentPath, mergedFragmentHtml, 'utf8');
  await fs.writeFile(
    revisionPaths.promptPath,
    [
      '# Parallel slide generation',
      `slide_count: ${totalSlides}`,
      '',
      ...parsed.slides.map((slide, index) => {
        const paddedIndex = String(index + 1).padStart(2, '0');
        return `- slide ${index + 1}: slides/slide-${paddedIndex}.prompt.txt -> slides/slide-${paddedIndex}.fragment.html (${slide.title})`;
      }),
      '',
    ].join('\n'),
    'utf8'
  );

  return mergedFragmentHtml;
}

async function runDeckPlanning({ runner, revisionPaths, themeId }) {
  const startedAt = nowIso();
  const startedMs = Date.now();
  const runtimeContent = await fs.readFile(revisionPaths.contentPath, 'utf8');
  const plannerDigest = await buildPlannerDigest({ themeId });
  await fs.writeFile(revisionPaths.plannerDigestPath, plannerDigest, 'utf8');
  const prompt = await buildDeckDesignPlanPrompt({
    contentPath: revisionPaths.contentPath,
    outputPath: revisionPaths.deckDesignPlanPath,
    plannerDigestPath: revisionPaths.plannerDigestPath,
  });
  await fs.writeFile(revisionPaths.deckDesignPlanPromptPath, prompt, 'utf8');
  let plan = '';
  let rebalancedPlan = '';
  let failure = null;

  try {
    await runner.run({
      promptPath: revisionPaths.deckDesignPlanPromptPath,
      outputPath: revisionPaths.deckDesignPlanPath,
      workspaceDir: revisionPaths.revisionDir,
      prompt,
    });

    plan = await fs.readFile(revisionPaths.deckDesignPlanPath, 'utf8');
    validateDeckDesignPlan(plan);
    validatePlannerPlanMatchesContent({
      deckPlanMarkdown: plan,
      contentMarkdown: runtimeContent,
    });

    rebalancedPlan = rebalanceDeckDesignPlan({
      deckPlanMarkdown: plan,
      contentMarkdown: runtimeContent,
    });
    validateDeckDesignPlan(rebalancedPlan);

    if (rebalancedPlan !== plan) {
      await fs.writeFile(revisionPaths.deckDesignPlanPath, rebalancedPlan, 'utf8');
    }

    return rebalancedPlan;
  } catch (error) {
    failure = error;
    throw error;
  } finally {
    try {
      await writeJson(revisionPaths.deckPlanningReportPath, {
        started_at: startedAt,
        finished_at: nowIso(),
        duration_ms: Math.max(0, Date.now() - startedMs),
        success: !failure,
        prompt_chars: prompt.length,
        content_chars: runtimeContent.length,
        planner_digest_chars: plannerDigest.length,
        plan_chars: plan.length,
        rebalanced: Boolean(plan) && rebalancedPlan !== plan,
        error: failure ? buildJobError(failure) : null,
      });
    } catch {}
  }
}

function buildRevisionPrompt({
  deckDesignPlanPath,
  targetSlideIndex,
  targetOutputPath,
  themeId,
  originalSlideHtml,
  originalSlideTitle,
  originalSlideLayout,
  previousSlide,
  nextSlide,
  updatedContent,
  userInstruction,
}) {
  const themeCssPath = resolveThemeCss(themeId);

  return `# 任务目标
你要重写一个单页 slide，而不是重做整套 PPT。

## 唯一可信来源
- Deck design plan：\`${deckDesignPlanPath}\`
- 内容协议：\`${promptPaths.contentProtocolPath}\`
- Layout catalog：\`${promptPaths.layoutCatalogPath}\`
- Component catalog：\`${promptPaths.componentCatalogPath}\`
- HTML-to-PPTX restrictions：\`${promptPaths.htmlRestrictPath}\`
- Agent workflow：\`${promptPaths.agentWorkflowPath}\`
- 版式模板目录：\`${promptPaths.formatDir}\`
- 布局骨架：\`${promptPaths.layoutCssPath}\`
- 当前主题：\`${themeCssPath}\`
- 品牌配置：\`${promptPaths.brandConfigPath}\`

## 本次任务
- 目标页码：第 ${targetSlideIndex} 页
- 目标输出路径：\`${targetOutputPath}\`
- 你必须只生成一个合法的 slide 根节点：\`<div class="slide ...">...</div>\`
- 请直接把这个单页 HTML 写入目标输出路径
- 不要输出解释，不要重写其他页面

## 原页面信息
- 原页面标题：${originalSlideTitle}
- 原页面版式：${originalSlideLayout}
${previousSlide ? `- 上一页：第 ${previousSlide.slide_index} 页 / ${previousSlide.title} / ${previousSlide.layout}` : '- 上一页：无'}
${nextSlide ? `- 下一页：第 ${nextSlide.slide_index} 页 / ${nextSlide.title} / ${nextSlide.layout}` : '- 下一页：无'}

## 原页面 HTML
\`\`\`html
${originalSlideHtml}
\`\`\`

## 修改输入
${updatedContent ? `### updated_content\n${updatedContent}\n` : ''}
${userInstruction ? `### user_instruction\n${userInstruction}\n` : ''}

## 强约束
- 必须先读取 deck design plan，并保持其中的全局视觉风格、layout 和 component 决策
- 只能使用 layout catalog、component catalog、layout.css、当前主题 CSS 中已注册的 class
- 绝对禁止自定义新的 class
- 必须遵守 HTML-to-PPTX restrictions
- 品牌位规则必须遵守 theme-brand-config.json
- 页面总页数由系统保持不变，你只负责重写这一页
- 输出必须是单页 slide fragment，不是完整 HTML 文档
- 如果 updated_content 的 Media block 含有 \`Local-Path\` 或 \`Local-Poster-Path\`，必须优先使用这些本地相对路径
`;
}

class PptService {
  constructor({ queue, runner }) {
    this.queue = queue;
    this.runner = runner;
  }

  async init() {
    await initStore();
    await this.recoverInterruptedWork();
  }

  async recoverInterruptedWork() {
    const jobIds = await listJobIds();
    for (const jobId of jobIds) {
      const job = await getJob(jobId);
      const revisionIds = await listRevisionIds(jobId);

      for (const revisionId of revisionIds) {
        const revision = await getRevision(jobId, revisionId);
        if (revision.status === 'queued' || revision.status === 'running') {
          await updateRevision(jobId, revisionId, (current) =>
            withLifecycleFields(current, {
              status: 'failed',
              phase: 'failed',
              message: '服务重启导致任务中断',
              finished_time: nowIso(),
              error: {
                code: 'SERVICE_RESTARTED',
                message: 'Service restarted while the task was running.',
              },
            })
          );
        }
      }

      if (job.status === 'queued' || job.status === 'running') {
        await updateJob(jobId, (current) =>
          withLifecycleFields(current, {
            status: 'failed',
            phase: 'failed',
            message: '服务重启导致任务中断',
            finished_time: nowIso(),
            active_revision_id: null,
            error: {
              code: 'SERVICE_RESTARTED',
              message: 'Service restarted while the task was running.',
            },
          })
        );
      }
    }
  }

  async createJob(payload) {
    validateCreatePayload(payload);
    getTheme(payload.theme_id);

    const tenantId = payload.metadata.tenant_id || 'default';
    const requestHash = hashRequestForIdempotency(payload);
    const existing = await findByIdempotency(tenantId, payload.metadata.idempotency_key);
    if (existing) {
      if (existing.request_hash !== requestHash) {
        throw new AppError(
          'INVALID_REQUEST',
          'The same idempotency_key was already used with a different request payload.',
          409
        );
      }

      const job = await getJob(existing.job_id);
      return {
        job_id: job.job_id,
        status: job.status,
      };
    }

    const jobId = makeJobId();
    await createJob({ jobId, request: payload });
    const revisionId = await createRevision(jobId, { kind: 'initial' });

    this.queue.enqueue(async () => {
      await this.processInitialGeneration(jobId, revisionId);
    }).catch(() => {});

    return {
      job_id: jobId,
      status: 'queued',
    };
  }

  async getJobStatus(jobId) {
    const job = await getJob(jobId);
    return {
      job_id: job.job_id,
      status: job.status,
      phase: job.phase,
      progress: job.progress,
      message: job.message,
      create_time: job.create_time,
      updated_time: job.updated_time,
      finished_time: job.finished_time,
      latest_revision_id: job.latest_revision_id,
      error: job.error || null,
    };
  }

  async getResults(jobId) {
    const job = await getJob(jobId);
    const latestRevisionId = job.latest_success_revision_id;
    if (!latestRevisionId) {
      throw new AppError('INVALID_REQUEST', 'No successful result is available for this job yet.', 409);
    }

    const request = await getRequest(jobId);
    const revision = await getRevision(jobId, latestRevisionId);
    const manifest = await readJson(revision.artifacts.manifest_path);

    return {
      job_id: jobId,
      latest_revision_id: latestRevisionId,
      theme_id: job.theme_id,
      results: {
        deck_design_plan_url: toArtifactUrl(jobId, latestRevisionId, 'deck_design_plan.md'),
        html_fragment_url: toArtifactUrl(jobId, latestRevisionId, 'deck.fragment.html'),
        html_full_url: toArtifactUrl(jobId, latestRevisionId, 'deck.html'),
        pptx_url: toArtifactUrl(jobId, latestRevisionId, 'deck.pptx'),
        manifest_url: toArtifactUrl(jobId, latestRevisionId, 'manifest.json'),
      },
      slide_count: manifest.slide_count,
      metadata: request.metadata,
    };
  }

  async createRevision(jobId, payload) {
    validateRevisionPayload(payload);
    const job = await getJob(jobId);
    if (!job.latest_success_revision_id) {
      throw new AppError('INVALID_REQUEST', 'The job has no successful baseline revision yet.', 409);
    }

    const revisionId = await createRevision(jobId, {
      kind: 'revision',
      mode: payload.mode,
      target_slides: payload.target_slides,
      updated_content: payload.updated_content,
      user_instruction: payload.user_instruction,
    });

    this.queue.enqueue(async () => {
      await this.processRevision(jobId, revisionId);
    }).catch(() => {});

    return {
      revision_id: revisionId,
      status: 'queued',
    };
  }

  async getRevisionStatus(jobId, revisionId) {
    const revision = await getRevision(jobId, revisionId);
    return {
      job_id: jobId,
      revision_id: revision.revision_id,
      status: revision.status,
      phase: revision.phase,
      progress: revision.progress,
      message: revision.message,
      create_time: revision.create_time,
      updated_time: revision.updated_time,
      finished_time: revision.finished_time,
      error: revision.error || null,
    };
  }

  async processInitialGeneration(jobId, revisionId) {
    const request = await getRequest(jobId);
    const revisionPaths = getRevisionPaths(jobId, revisionId);

    try {
      await this.markJobRunning(jobId, revisionId, 'preprocessing', '正在准备生成任务');
      await this.markRevisionRunning(jobId, revisionId, 'preprocessing', '正在准备生成任务');

      const runtimeContent = await this.prepareRuntimeContent({
        markdown: request.content_markdown,
        revisionPaths,
        contentKind: 'deck',
      });
      await fs.writeFile(revisionPaths.contentPath, runtimeContent, 'utf8');

      await this.markJobRunning(jobId, revisionId, 'planning_deck', '正在规划 deck design plan');
      await this.markRevisionRunning(jobId, revisionId, 'planning_deck', '正在规划 deck design plan');

      await runDeckPlanning({
        runner: this.runner,
        revisionPaths,
        themeId: request.theme_id,
      });

      await this.markJobRunning(jobId, revisionId, 'generating_slides', '正在生成 slides');
      await this.markRevisionRunning(jobId, revisionId, 'generating_slides', '正在生成 slides');

      await runInitialSlideGeneration({
        runner: this.runner,
        runtimeContent,
        revisionPaths,
        themeId: request.theme_id,
      });

      const postProcessResult = await this.postProcessGeneratedFragment({
        jobId,
        revisionId,
        themeId: request.theme_id,
        contentMarkdown: runtimeContent,
      });

      await this.markJobRunning(jobId, revisionId, 'building_full_html', '正在构建完整 HTML');
      await this.markRevisionRunning(jobId, revisionId, 'building_full_html', '正在构建完整 HTML');

      buildStandaloneHtmlFromFragment({
        fragmentPath: revisionPaths.fragmentPath,
        outputPath: revisionPaths.fullHtmlPath,
        themeId: request.theme_id,
      });

      const stabilizedPostProcessResult = await this.stabilizeLayoutGeometry({
        revisionPaths,
        themeId: request.theme_id,
        postProcessResult,
      });

      await this.markJobRunning(jobId, revisionId, 'exporting_pptx', '正在导出 PPTX');
      await this.markRevisionRunning(jobId, revisionId, 'exporting_pptx', '正在导出 PPTX');

      await this.processPostProcessedDeckArtifacts({
        jobId,
        revisionId,
        revisionPaths,
        postProcessResult: stabilizedPostProcessResult,
      });
      await this.markRevisionSucceeded(jobId, revisionId, '生成完成');
      await this.markJobSucceeded(jobId, revisionId, '生成完成');
    } catch (error) {
      await this.markRevisionFailed(jobId, revisionId, error, '生成失败');
      await this.markJobFailed(jobId, error, '生成失败');
    }
  }

  async processRevision(jobId, revisionId) {
    const job = await getJob(jobId);
    const latestSuccessRevisionId = job.latest_success_revision_id;
    const baselinePaths = getRevisionPaths(jobId, latestSuccessRevisionId);
    const revision = await getRevision(jobId, revisionId);
    const revisionPaths = getRevisionPaths(jobId, revisionId);

    try {
      await this.markJobRunning(jobId, revisionId, 'preprocessing', '正在准备修订任务');
      await this.markRevisionRunning(jobId, revisionId, 'preprocessing', '正在准备修订任务');

      const baselineFragmentHtml = await fs.readFile(baselinePaths.fragmentPath, 'utf8');
      const baselineManifest = await readJson(baselinePaths.manifestPath);
      const targetSlideIndex = revision.target_slides[0];
      const slides = extractSlides(baselineFragmentHtml);
      const originalSlideHtml = slides[targetSlideIndex - 1];

      if (!originalSlideHtml) {
        throw new AppError(
          'INVALID_TARGET_SLIDES',
          `Target slide ${targetSlideIndex} does not exist in the current deck.`,
          400
        );
      }

      const previousSlide = baselineManifest.slides[targetSlideIndex - 2] || null;
      const nextSlide = baselineManifest.slides[targetSlideIndex] || null;
      const runtimeUpdatedContent = revision.updated_content
        ? await this.prepareRuntimeContent({
            markdown: revision.updated_content,
            revisionPaths,
            contentKind: 'single-slide',
          })
        : '';
      const prompt = buildRevisionPrompt({
        deckDesignPlanPath: baselinePaths.deckDesignPlanPath,
        targetSlideIndex,
        targetOutputPath: revisionPaths.fragmentPath,
        themeId: job.theme_id,
        originalSlideHtml,
        originalSlideTitle: inferTitle(originalSlideHtml),
        originalSlideLayout: inferLayout(originalSlideHtml),
        previousSlide,
        nextSlide,
        updatedContent: runtimeUpdatedContent,
        userInstruction: revision.user_instruction,
      });

      await fs.writeFile(revisionPaths.contentPath, runtimeUpdatedContent || '', 'utf8');
      await fs.writeFile(revisionPaths.promptPath, prompt, 'utf8');

      await this.markJobRunning(jobId, revisionId, 'generating_slides', '正在重写目标页');
      await this.markRevisionRunning(jobId, revisionId, 'generating_slides', '正在重写目标页');

      await this.runner.run({
        promptPath: revisionPaths.promptPath,
        outputPath: revisionPaths.fragmentPath,
        workspaceDir: revisionPaths.revisionDir,
        prompt,
      });

      const replacementSlideHtml = await fs.readFile(revisionPaths.fragmentPath, 'utf8');
      const mergedFragmentHtml = replaceSlide(baselineFragmentHtml, targetSlideIndex, replacementSlideHtml);
      await fs.writeFile(revisionPaths.fragmentPath, mergedFragmentHtml, 'utf8');
      const postProcessResult = await this.postProcessGeneratedFragment({
        jobId,
        revisionId,
        themeId: job.theme_id,
        contentMarkdown: runtimeUpdatedContent,
      });

      await this.markJobRunning(jobId, revisionId, 'building_full_html', '正在重建完整 HTML');
      await this.markRevisionRunning(jobId, revisionId, 'building_full_html', '正在重建完整 HTML');

      buildStandaloneHtmlFromFragment({
        fragmentPath: revisionPaths.fragmentPath,
        outputPath: revisionPaths.fullHtmlPath,
        themeId: job.theme_id,
      });

      const stabilizedPostProcessResult = await this.stabilizeLayoutGeometry({
        revisionPaths,
        themeId: job.theme_id,
        postProcessResult,
      });

      await this.markJobRunning(jobId, revisionId, 'exporting_pptx', '正在重新导出 PPTX');
      await this.markRevisionRunning(jobId, revisionId, 'exporting_pptx', '正在重新导出 PPTX');

      await this.processPostProcessedDeckArtifacts({
        jobId,
        revisionId,
        revisionPaths,
        postProcessResult: stabilizedPostProcessResult,
      });
      await this.markRevisionSucceeded(jobId, revisionId, '修订完成');
      await this.markJobSucceeded(jobId, revisionId, '修订完成');
    } catch (error) {
      await this.markRevisionFailed(jobId, revisionId, error, '修订失败');
      await this.markJobFailed(jobId, error, '修订失败');
    }
  }

  async postProcessGeneratedFragment({ jobId, revisionId, themeId, contentMarkdown }) {
    const revisionPaths = getRevisionPaths(jobId, revisionId);
    const fragmentHtml = await fs.readFile(revisionPaths.fragmentPath, 'utf8');
    const { runPostProcessingChain: runFreshPostProcessingChain } = requireFresh('../domain/postprocess');
    const result = runFreshPostProcessingChain({
      jobId,
      revisionId,
      themeId,
      fragmentHtml,
      contentMarkdown,
    });

    await fs.writeFile(revisionPaths.fragmentPath, result.fragmentHtml, 'utf8');
    return result;
  }

  async stabilizeLayoutGeometry({ revisionPaths, themeId, postProcessResult }) {
    let geometryReport;
    try {
      geometryReport = await inspectHtmlLayout(revisionPaths.fullHtmlPath);
    } catch {
      return postProcessResult;
    }

    const { repairOverflowLayouts: repairFreshOverflowLayouts } = requireFresh('../domain/layout-repair');
    const repaired = repairFreshOverflowLayouts(postProcessResult.fragmentHtml, geometryReport);
    if (!repaired.changed) {
      return postProcessResult;
    }

    const nextFragmentHtml = `${repaired.fragmentHtml}\n`;
    await fs.writeFile(revisionPaths.fragmentPath, nextFragmentHtml, 'utf8');
    buildStandaloneHtmlFromFragment({
      fragmentPath: revisionPaths.fragmentPath,
      outputPath: revisionPaths.fullHtmlPath,
      themeId,
    });

    return {
      ...postProcessResult,
      fragmentHtml: nextFragmentHtml,
    };
  }

  async inspectAndMergeQualityReport(postProcessResult, revisionPaths) {
    try {
      const geometryReport = await inspectHtmlLayout(revisionPaths.fullHtmlPath);
      return {
        ...postProcessResult,
        qualityReport: mergeQualityReports(postProcessResult.qualityReport, geometryReport),
      };
    } catch {
      return postProcessResult;
    }
  }

  async processPostProcessedDeckArtifacts({ jobId, revisionId, revisionPaths, postProcessResult }) {
    const mergedResult = await this.inspectAndMergeQualityReport(postProcessResult, revisionPaths);

    await this.exportDeckArtifacts(revisionPaths);
    await this.finalizeArtifacts(jobId, revisionId, mergedResult);
  }

  async exportDeckArtifacts(revisionPaths) {
    await exportHtmlToPptx({
      htmlPath: revisionPaths.fullHtmlPath,
      outputPath: revisionPaths.pptxPath,
      jobWorkspace: revisionPaths.revisionDir,
    });
  }

  async finalizeArtifacts(jobId, revisionId, postProcessResult) {
    const revisionPaths = getRevisionPaths(jobId, revisionId);

    await writeJson(revisionPaths.manifestPath, postProcessResult.manifest);
    await writeJson(revisionPaths.qualityReportPath, postProcessResult.qualityReport);

    await this.markRevisionRunning(jobId, revisionId, 'storing_artifacts', '正在写入产物');
    await this.markJobRunning(jobId, revisionId, 'storing_artifacts', '正在写入产物');
  }

  async markJobRunning(jobId, revisionId, phase, message) {
    await updateJob(jobId, (job) =>
      withLifecycleFields(job, {
        status: 'running',
        phase,
        message,
        active_revision_id: revisionId,
        error: null,
      })
    );
  }

  async markRevisionRunning(jobId, revisionId, phase, message) {
    await updateRevision(jobId, revisionId, (revision) =>
      withLifecycleFields(revision, {
        status: 'running',
        phase,
        message,
        error: null,
      })
    );
  }

  async markRevisionSucceeded(jobId, revisionId, message) {
    await updateRevision(jobId, revisionId, (revision) =>
      withLifecycleFields(revision, {
        status: 'succeeded',
        phase: 'completed',
        progress: 100,
        message,
        finished_time: nowIso(),
        error: null,
      })
    );
  }

  async markJobSucceeded(jobId, revisionId, message) {
    await updateJob(jobId, (job) =>
      withLifecycleFields(job, {
        status: 'succeeded',
        phase: 'completed',
        progress: 100,
        message,
        finished_time: nowIso(),
        latest_revision_id: revisionId,
        latest_success_revision_id: revisionId,
        active_revision_id: null,
        error: null,
      })
    );
  }

  async markRevisionFailed(jobId, revisionId, error, message) {
    await updateRevision(jobId, revisionId, (revision) =>
      withLifecycleFields(revision, {
        status: 'failed',
        phase: 'failed',
        message,
        finished_time: nowIso(),
        error: buildJobError(error),
      })
    );
  }

  async markJobFailed(jobId, error, message) {
    await updateJob(jobId, (job) =>
      withLifecycleFields(job, {
        status: 'failed',
        phase: 'failed',
        message,
        finished_time: nowIso(),
        active_revision_id: null,
        error: buildJobError(error),
      })
    );
  }

  async resolveArtifactPath(jobId, revisionId, fileName) {
    await getRevision(jobId, revisionId);
    const allowed = new Set([
      'deck.fragment.html',
      'deck_design_plan.md',
      'deck.html',
      'deck.pptx',
      'manifest.json',
      'layout-quality-report.json',
    ]);
    if (!allowed.has(fileName)) {
      throw new AppError('INVALID_REQUEST', `Unsupported artifact file: ${fileName}`, 400);
    }
    const revisionPaths = getRevisionPaths(jobId, revisionId);
    const map = {
      'deck.fragment.html': revisionPaths.fragmentPath,
      'deck_design_plan.md': revisionPaths.deckDesignPlanPath,
      'deck.html': revisionPaths.fullHtmlPath,
      'deck.pptx': revisionPaths.pptxPath,
      'manifest.json': revisionPaths.manifestPath,
      'layout-quality-report.json': revisionPaths.qualityReportPath,
    };
    const target = map[fileName];
    if (!(await fileExists(target))) {
      throw new AppError('INVALID_REQUEST', `Artifact not found: ${fileName}`, 404);
    }
    return target;
  }

  async resolveMediaArtifactPath(jobId, revisionId, fileName) {
    await getRevision(jobId, revisionId);
    if (!String(fileName || '').trim() || fileName.includes('/') || fileName.includes('\\')) {
      throw new AppError('INVALID_REQUEST', `Unsupported media file: ${fileName}`, 400);
    }
    const revisionPaths = getRevisionPaths(jobId, revisionId);
    const target = path.join(revisionPaths.mediaDir, fileName);
    if (!(await fileExists(target))) {
      throw new AppError('INVALID_REQUEST', `Media artifact not found: ${fileName}`, 404);
    }
    return target;
  }

  async prepareRuntimeContent({ markdown, revisionPaths, contentKind }) {
    const localized = await localizeMediaAssets(markdown, {
      mediaDir: revisionPaths.mediaDir,
      contentKind,
    });
    return localized.runtimeMarkdown;
  }
}

module.exports = {
  applyRuntimePromptPaths,
  PptService,
  runDeckPlanning,
  runInitialSlideGeneration,
};
