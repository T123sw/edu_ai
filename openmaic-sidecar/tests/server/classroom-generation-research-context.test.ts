import { beforeEach, describe, expect, it, vi } from 'vitest';

// edu_ai patch (docs/spec/patches/001-researchContext-injection.md):
// verifies that an externally injected `researchContext` reaches
// `generateSceneOutlinesFromRequirements`, merged with (not replacing) any
// internal web search result.

const mocks = vi.hoisted(() => ({
  resolveModel: vi.fn(),
  isProviderKeyRequired: vi.fn(),
  generateSceneOutlinesFromRequirements: vi.fn(),
  applyOutlineFallbacks: vi.fn(),
  generateSceneContent: vi.fn(),
  generateSceneActions: vi.fn(),
  createSceneWithActions: vi.fn(),
  persistClassroom: vi.fn(),
  callLLM: vi.fn(),
  resolveClassroomWebSearchConfig: vi.fn(),
  buildSearchQuery: vi.fn(),
  searchWeb: vi.fn(),
  formatSearchResultsAsContext: vi.fn(),
  getStageModel: vi.fn(),
}));

vi.mock('@/lib/server/resolve-model', () => ({
  resolveModel: mocks.resolveModel,
}));

vi.mock('@/lib/ai/providers', () => ({
  isProviderKeyRequired: mocks.isProviderKeyRequired,
}));

vi.mock('@/lib/ai/llm', () => ({
  callLLM: mocks.callLLM,
}));

vi.mock('@/lib/generation/outline-generator', () => ({
  generateSceneOutlinesFromRequirements: mocks.generateSceneOutlinesFromRequirements,
  applyOutlineFallbacks: mocks.applyOutlineFallbacks,
}));

vi.mock('@/lib/generation/scene-generator', () => ({
  generateSceneContent: mocks.generateSceneContent,
  generateSceneActions: mocks.generateSceneActions,
  createSceneWithActions: mocks.createSceneWithActions,
}));

vi.mock('@/lib/server/classroom-storage', () => ({
  persistClassroom: mocks.persistClassroom,
}));

vi.mock('@/lib/server/web-search-config', () => ({
  resolveClassroomWebSearchConfig: mocks.resolveClassroomWebSearchConfig,
}));

vi.mock('@/lib/server/search-query-builder', () => ({
  buildSearchQuery: mocks.buildSearchQuery,
}));

vi.mock('@/lib/web-search', () => ({
  searchWeb: mocks.searchWeb,
  formatSearchResultsAsContext: mocks.formatSearchResultsAsContext,
}));

vi.mock('@/lib/server/model-routes', () => ({
  getStageModel: mocks.getStageModel,
}));

vi.mock('@/lib/logger', () => ({
  createLogger: () => ({
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  }),
}));

const outline = {
  id: 'outline-1',
  type: 'slide',
  title: 'Injected Context Basics',
  description: 'Explain injected research context',
  keyPoints: ['Uses domain supplement'],
  order: 1,
} as const;

const slideContent = {
  elements: [],
  remark: 'Uses domain supplement',
};

async function generateWithInput(input: Record<string, unknown>) {
  const { generateClassroom } = await import('@/lib/server/classroom-generation');
  return generateClassroom(
    { requirement: 'Teach injected context basics', ...input } as never,
    { baseUrl: 'http://localhost' },
  );
}

describe('classroom generation researchContext injection', () => {
  beforeEach(() => {
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    mocks.resolveModel.mockResolvedValue({
      model: { id: 'language-model' },
      modelInfo: {},
      modelString: 'test:model',
      providerId: 'test',
      apiKey: '',
    });
    mocks.isProviderKeyRequired.mockReturnValue(false);
    mocks.callLLM.mockResolvedValue({ text: 'ok' });
    mocks.getStageModel.mockReturnValue(undefined);
    mocks.generateSceneOutlinesFromRequirements.mockResolvedValue({
      success: true,
      data: {
        languageDirective: 'Use English.',
        outlines: [outline],
      },
    });
    mocks.applyOutlineFallbacks.mockImplementation((value) => value);
    mocks.generateSceneContent.mockResolvedValue(slideContent);
    mocks.generateSceneActions.mockResolvedValue([]);
    mocks.createSceneWithActions.mockImplementation((sceneOutline, content, actions, api) => {
      const sceneResult = api.scene.create({
        type: sceneOutline.type,
        title: sceneOutline.title,
        order: sceneOutline.order,
        content: {
          type: 'slide',
          canvas: {
            id: 'slide-1',
            viewportSize: 1000,
            viewportRatio: 0.5625,
            elements: content.elements,
          },
        },
        actions,
      });
      return sceneResult.success ? (sceneResult.data ?? null) : null;
    });
    mocks.persistClassroom.mockImplementation(async ({ id, scenes }) => ({
      id,
      url: `http://localhost/classroom/${id}`,
      scenesCount: scenes.length,
      createdAt: '2026-06-22T00:00:00.000Z',
    }));
  });

  it('passes an injected researchContext through untouched when web search is off', async () => {
    await generateWithInput({ researchContext: 'RAG: chapter 3 covers retries.' });

    expect(mocks.resolveClassroomWebSearchConfig).not.toHaveBeenCalled();
    expect(mocks.generateSceneOutlinesFromRequirements).toHaveBeenCalledWith(
      expect.anything(),
      undefined,
      undefined,
      expect.any(Function),
      undefined,
      expect.objectContaining({ researchContext: 'RAG: chapter 3 covers retries.' }),
    );
  });

  it('leaves researchContext undefined when neither web search nor injection is provided', async () => {
    await generateWithInput({});

    expect(mocks.generateSceneOutlinesFromRequirements).toHaveBeenCalledWith(
      expect.anything(),
      undefined,
      undefined,
      expect.any(Function),
      undefined,
      expect.objectContaining({ researchContext: undefined }),
    );
  });

  it('merges web search results with the injected researchContext (web first, then injection)', async () => {
    mocks.resolveClassroomWebSearchConfig.mockReturnValue({
      providerId: 'bocha',
      apiKey: 'test-key',
      baseUrl: 'https://example.test',
    });
    mocks.buildSearchQuery.mockResolvedValue({
      query: 'injected context basics',
      hasPdfContext: false,
      rawRequirementLength: 10,
      rewriteAttempted: false,
      finalQueryLength: 10,
    });
    mocks.searchWeb.mockResolvedValue({ sources: [{ title: 'Web Source' }] });
    mocks.formatSearchResultsAsContext.mockReturnValue('Web: general retry background.');

    await generateWithInput({
      enableWebSearch: true,
      researchContext: 'RAG: chapter 3 covers retries.',
    });

    expect(mocks.generateSceneOutlinesFromRequirements).toHaveBeenCalledWith(
      expect.anything(),
      undefined,
      undefined,
      expect.any(Function),
      undefined,
      expect.objectContaining({
        researchContext: 'Web: general retry background.\n\nRAG: chapter 3 covers retries.',
      }),
    );
  });

  it('falls back to the injected researchContext alone when web search is skipped (no key configured)', async () => {
    mocks.resolveClassroomWebSearchConfig.mockReturnValue(null);

    await generateWithInput({
      enableWebSearch: true,
      researchContext: 'RAG: chapter 3 covers retries.',
    });

    expect(mocks.searchWeb).not.toHaveBeenCalled();
    expect(mocks.generateSceneOutlinesFromRequirements).toHaveBeenCalledWith(
      expect.anything(),
      undefined,
      undefined,
      expect.any(Function),
      undefined,
      expect.objectContaining({ researchContext: 'RAG: chapter 3 covers retries.' }),
    );
  });
});
