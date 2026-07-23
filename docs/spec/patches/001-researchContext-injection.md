# Patch 001 · researchContext 注入

> 对应 [SPEC-04 §4](../SPEC-04_GenerateClassroom_课件生成与注入.md#4-内容注入补丁researchcontext迁移的核心改动)。
> 作用：让 edu_ai 能把自己的 RAG/教材/知识图谱补充内容（`researchContext`）传给 sidecar 的
> `generate-classroom`，与 sidecar 内部 web search 的结果**合并叠加**，而不是相互替代/短路。
> 上游 `GenerateClassroomInput` 原本没有这个字段，只能靠内部 web search 产生
> `researchContext`。三处改动均为**新增字段/新增分支**，不改动任何既有字段语义，
> 跟上游 diff 成本低，冲突面小。

## 改动 1：`lib/server/classroom-generation.ts` —— 接口加字段

`GenerateClassroomInput` 新增可选字段 `researchContext?: string`：

```ts
export interface GenerateClassroomInput {
  requirement: string;
  pdfContent?: { text: string; images: string[] };
  enableWebSearch?: boolean;
  webSearchProviderId?: WebSearchProviderId;
  webSearchApiKey?: string;
  baiduSubSources?: BaiduSubSources;
  enableImageGeneration?: boolean;
  enableVideoGeneration?: boolean;
  enableTTS?: boolean;
  agentMode?: 'default' | 'generate';
  /**
   * edu_ai patch (docs/spec/patches/001-researchContext-injection.md):
   * externally injected domain supplement (RAG / textbook / knowledge graph).
   * Merged with (not a replacement for) the internal web search result.
   */
  researchContext?: string;
}
```

## 改动 2：`app/api/generate-classroom/route.ts` —— 请求体透传

在组装 `body` 时新增一条透传：

```ts
...(rawBody.researchContext ? { researchContext: rawBody.researchContext } : {}),
```

## 改动 3：`lib/server/classroom-generation.ts` （原行号约 275 附近）—— 合并叠加

原逻辑：`researchContext` 只在 `input.enableWebSearch` 为真时由内部 web search 产生。
补丁在该 `if` 块之后新增合并分支，web 结果与注入内容**拼接**而非互斥：

```ts
  // edu_ai patch (docs/spec/patches/001-researchContext-injection.md):
  // merge externally injected domain supplement on top of (not instead of) web search.
  if (input.researchContext) {
    researchContext = [researchContext, input.researchContext].filter(Boolean).join('\n\n');
  }
```

下游 `generateSceneOutlinesFromRequirements(..., { researchContext })` 无需改动，天然消费合并后的文本。

## 验证

- `pnpm exec tsc --noEmit` 通过（新增字段/分支不破坏既有类型）。
- `researchContext` 为空时行为与打补丁前完全一致（`enableWebSearch=false` 且无注入 → `researchContext=undefined`，走原纯 LLM 生成路径）。
- 只传 `researchContext`（`enableWebSearch=false`）时，生成大纲应体现注入内容（对应 AC-04-1/2）。
- 同时传 `enableWebSearch=true` 且 `researchContext` 时，两段内容都应出现在最终拼接文本中，用 `\n\n` 分隔（对应 AC-04-3）。

## 涉及文件

- `openmaic-sidecar/lib/server/classroom-generation.ts`
- `openmaic-sidecar/app/api/generate-classroom/route.ts`
