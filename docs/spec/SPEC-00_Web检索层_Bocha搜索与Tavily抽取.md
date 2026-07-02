# SPEC-00 · Web 检索层（Bocha 搜索 + Tavily Extract）· Phase 1.5 前置

> **验收文档**：[`../acceptance/ACC-00_Web检索层_验收.md`](../acceptance/ACC-00_Web检索层_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> **定位**：Phase 1.5 **前置基础设施**——必须先于 Phase 2（课件生成 SPEC-04）完成。用托管 API 替换 edu_ai 现有自建 web 检索。
> **关联**：SPEC-04（课件 researchContext 的 web 部分调本层）、SPEC-03（RAG 入库链路复用）、SPEC-06（provider/key 安全边界）。
> 最近更新：2026-07-02 · 状态：草案 v0.2（收尾边界已更新：旧 web 文本链路 + 图片 SearXNG 均切 Bocha）

---

## 0. 背景与动机

**现状**：edu_ai 已有完整 web 检索链路（已跑通、有测试）：

```
POST /agent/deepsearch-and-crawl  (app/api/deepsearch.py)
 → run_deepsearch_and_crawl       (app/services/deepsearch_service.py)
   1. _execute_deepsearch(query)  → URL 列表   (EduAgent LangGraph + SearxNG)
   2. _execute_crawl(urls)        → 爬正文     (EduAgent crawler_service + automation_spider/Selenium)
   3. _clean_crawl_results        → 清洗       (ContentCleaner)
   4. save_crawl_batch            → 存批次     (storage_service)
   5. _import_to_knowledge_base   → 入 RAG + course KB
```

**问题（用户实测，2026-07-01）**：deepsearch **慢、不稳、内容未审查（直接取前几链接）**；SearxNG **有限流、上线扛不住多用户**；自建 Selenium 爬虫维护脆。

**方案**：用**托管 API** 替换最脆的两段——搜索用 **Bocha（博查）**、全文抽取用 **Tavily Extract**——全托管、可扩展、质量更好、免自建 SearxNG/爬虫。**上层清洗/存储/入 RAG 全部复用不变。**

---

## 1. 目标与非目标

**目标**：
- edu_ai 侧新增 `websearch` 集成模块：Bocha 搜索 + Tavily Extract 全文抽取。
- **内部替换** `deepsearch_service` 的"找 URL"和"取全文"两步，`run_deepsearch_and_crawl` 签名、`/agent/deepsearch-and-crawl` 端点、前端 **全部不变**。
- 双档：`basic`（Bocha 摘要，快）/ `full`（Bocha URL → Tavily Extract 全文）。
- 主对话 `web_search` 改接 Bocha basic，避免继续调用旧 `deepsearch_pipeline`。
- 图片搜索 `image_search` 也从 SearXNG 切到 Bocha，Bocha 作为统一外部搜索入口。
- 本阶段完成 `api/src` 内旧 `deepsearch_pipeline` / `deepsearch_loader` / EduAgent web 文本检索引用清理。

**非目标**：
- 不改前端端点/请求主签名（只加一个可选 `depth`）。
- 不做课件生成（Phase 2 SPEC-04）。
- 不动 sidecar 的 web search 能力（保留可用，见 §10）。
- 不改变 `image_search` 工具名、planner/executor/reflect/report 注入流程和下游 payload 结构。

---

## 2. 双档架构（`depth` × `save_to_kb` 正交）

```
depth=basic (默认)  Bocha 搜索 → [url + AI摘要]                    快/省，供 researchContext 实时注入 / 前端展示
depth=full          Bocha 搜索 → URL → Tavily Extract 批量抽全文    深度研究，入 RAG 沉淀

save_to_kb=true   → 结果入 RAG（复用现有 import 链路）
save_to_kb=false  → 只返回结果，不落库
```

| 组合 | 效果 |
| --- | --- |
| basic + 入库 | Bocha 摘要入 RAG |
| basic + 不入库 | 摘要直接返回（researchContext/前端） |
| full + 入库 | Tavily 全文入 RAG（深度研究主用法） |
| full + 不入库 | 全文直接返回 |

---

## 3. Bocha 搜索契约（已核对 OpenMAIC `lib/web-search/bocha.ts` + 博查文档）

```
POST {BOCHA_BASE_URL}/v1/web-search            # 默认 https://api.bocha.cn
Authorization: Bearer {BOCHA_API_KEY}
Content-Type: application/json
body: { query, freshness: "noLimit", summary: true, count: <1..50> }
```

响应（`code==200`）：`data.webPages.value[]`：

| 字段 | 含义 | 内部映射 |
| --- | --- | --- |
| `name` | 标题 | `title` |
| `url` | 链接 | `url`（→ 供 Tavily Extract） |
| `summary` | **AI 摘要**（`summary:true` 时） | `content`（basic 档内容） |
| `snippet` | 短摘要 | `content` 兜底 |
| `datePublished`/`dateLastCrawled` | 时间 | `date` |
| `siteName` | 站名 | `site` |
| `data.images` | 图片链接 | `images`（供 `image_search` Bocha provider 归一化） |

- `count` 默认取 `WEB_SEARCH_DEFAULT_COUNT`，clamp 1..50。
- 错误：`code != 200` → 抛 `WebSearchError`（带 code/message/log_id）。

### 3.1 Bocha 图片搜索契约（替换 SearXNG）

`image_search` 不再使用本地 SearXNG。执行阶段新增 `BochaImageSearchProvider`，实现现有 `ImageSearchProvider` 协议：

- `name = "bocha"`。
- 输入保持 `query/count/style/safe/license_/owner`，下游调用方无感知。
- style 通过 query 增强表达，例如 `diagram/chart/photo`，不改变 handler 返回结构。
- 将 Bocha 响应中的图片 URL、缩略图、来源页、标题、尺寸字段映射为 raw image dict。
- 如果 Bocha 真实响应不稳定返回尺寸，执行阶段根据真实冒烟结果决定：补足尺寸字段，或放宽 `image_search` handler 的尺寸过滤，避免有效图片被 `width=0/height=0` 全部过滤。

后续 `build_default_image_search_provider()` 只支持：

- 空值：未配置图片搜索 provider。
- `bocha`：使用 Bocha 图片 provider。

`IMAGE_SEARCH_PROVIDER=searxng`、`SEARXNG_BASE_URL`、`searxng_provider.py` 均进入本阶段下线范围。

---

## 4. Tavily Extract 契约（已核对 Tavily 官方文档）

```
POST {TAVILY_BASE_URL}/extract                 # 默认 https://api.tavily.com
Authorization: Bearer {TAVILY_API_KEY}
body: {
  urls: [ ... ],                    # 单次最多 20
  extract_depth: "basic"|"advanced",# basic=1 credit/5url, advanced=2/5url
  format: "markdown",               # 干净正文
  timeout: <1..60>
}
```

响应：`results[{ url, raw_content }]` + `failed_results[{ url, error }]`。

- **批量**：一次传 Bocha 返回的一批 URL（≤20），一次调用抽全，不逐个爬。
- **长度可控**：`chunks_per_source` + 按 query 重排（可选），避免全文超模型上下文预算。
- **中文**：Extract 是"抓页面+提正文"，语言无关 → 中文页面照抽（绕开 Tavily search 中文弱）。
- **部分失败**：`failed_results` 里的 URL 跳过、不整批崩（映射为 `status="failed"`）。

---

## 5. 新模块与落点

`Edu_AI/api/src/app/integrations/websearch/`

```python
# bocha_search.py
def search_bocha(query: str, *, count: int, freshness: str, api_key: str, base_url: str) -> list[WebSearchHit]: ...
#   WebSearchHit = {url, title, content(summary/snippet), date, site, images?}

# tavily_extract.py
def extract_tavily(urls: list[str], *, depth: str, timeout: int, api_key: str, base_url: str) -> list[ExtractResult]: ...
#   ExtractResult = {url, content(markdown), status, error?}
#   自动分批 ≤20/次

# __init__.py
def get_web_searcher() -> Callable   # 按 WEB_SEARCH_PROVIDER 装配（当前 bocha）
def get_web_extractor() -> Callable  # 按 WEB_EXTRACT_PROVIDER 装配（当前 tavily）
```

httpx 同步/异步、超时、重试（幂等 + 瞬时错误退避）、key 脱敏。

---

## 6. 替换映射（旧 → 新，复用清单）

| 步骤 | 旧实现 | 新实现 | 处置 |
| --- | --- | --- | --- |
| 找 URL | `_execute_deepsearch`（EduAgent+SearxNG） | **`search_bocha`** | 替换 |
| 取全文 | `_execute_crawl`（Selenium 爬虫） | **`extract_tavily`**（构造成 `CrawlResult`/`CrawlBatchResult` 同形态） | 替换 |
| 清洗 | `_clean_crawl_results`（ContentCleaner） | 同 | **复用** |
| 存批次 | `save_crawl_batch`（storage_service） | 同 | **复用** |
| 入 RAG + course KB | `_import_to_knowledge_base` / `import_crawl_results_to_rag` | 同 | **复用** |
| 端点/签名/前端 | `POST /agent/deepsearch-and-crawl` / `run_deepsearch_and_crawl` | **不变**（+可选 `depth`） | **保持** |
| 图片搜索 | `SearxngImageSearchProvider` | **`BochaImageSearchProvider`** | 替换 |

> 关键：`extract_tavily` 的输出要**适配现有 `CrawlResult` 形态**（`{url,title,content,content_type,status,metadata,file_path}`），这样 §6 后三行零改动复用。

---

## 7. 服务层改造（`deepsearch_service.py`）

- `_execute_deepsearch(query)` → 内部改调 `search_bocha`，返回 `hits`（含 url+summary），`_execute_deepsearch` 仍可只回 `urls` 以兼容。
- 新增 `_execute_extract(urls, query)` → `extract_tavily` → 构造 `CrawlBatchResult`。
- `run_deepsearch_and_crawl(..., depth="basic")`：
  - `basic`：Bocha `hits` 的 `summary` 直接作内容 → （可选入 RAG）→ 返回。
  - `full`：`hits.url` → `extract_tavily` 全文 → 清洗/存储/入 RAG（复用）。
- 删除旧 EduAgent fallback：`deepsearch_loader`、`crawler_service`、`content_cleaner`、`storage_service`、`deepsearch_large_llm` 不再被 `deepsearch_service` 引用。
- `get_crawl_results` / `get_crawl_history` 只使用 edu_ai 自建 `crawl_batch_store`，不回退 EduAgent storage。
- 主对话 `web_search_tool` 改调 `run_deepsearch_and_crawl(depth="basic", save_to_kb=False)`，返回 `{summary, sources}`。

---

## 8. 请求模型变更（最小）

`app/schemas/deepsearch.py`：

```python
class DeepSearchAndCrawlRequest(BaseModel):
    query: str
    depth: Literal["basic", "full"] = "basic"   # ← 新增；前端"深度研究"= full
    max_urls: Optional[int] = 10
    save_to_kb: Optional[bool] = True
    course_id / scope_type / scope_id: ...       # 不变
    # crawl_timeout 语义并入 WEB_EXTRACT_TIMEOUT_S（保留字段兼容，忽略或映射）
```

---

## 9. 配置与安全（.env 已加占位）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `WEB_SEARCH_PROVIDER` | `bocha` | 搜索源 |
| `BOCHA_API_KEY` / `BOCHA_BASE_URL` | / `https://api.bocha.cn` | 博查 key |
| `WEB_SEARCH_DEFAULT_COUNT` / `WEB_SEARCH_FRESHNESS` | `10` / `noLimit` | 搜索参数 |
| `WEB_EXTRACT_PROVIDER` | `tavily` | 抽取源 |
| `TAVILY_API_KEY` / `TAVILY_BASE_URL` | / `https://api.tavily.com` | tavily key |
| `WEB_EXTRACT_DEPTH` / `WEB_EXTRACT_MAX_URLS` / `WEB_EXTRACT_TIMEOUT_S` | `basic` / `20` / `30` | 抽取参数 |
| `IMAGE_SEARCH_PROVIDER` | `bocha` | 图片搜索源；留空表示禁用 |
| `IMAGE_SEARCH_TIMEOUT_S` | `8` | 图片搜索超时 |

安全：**key 不落日志**（脱敏）；Bocha/Tavily 的 baseUrl 为托管固定值，不接受客户端自配（无 SSRF 面）；Tavily Extract 的 URL 来自 Bocha 结果（可信来源），仍对 URL 做基本 scheme 校验（仅 http/https）。

废弃并删除：`SEARXNG_BASE_URL`、`IMAGE_SEARCH_PROVIDER=searxng`。

---

## 10. 与 RAG / researchContext / sidecar 的衔接

- **入 RAG**：复用现有链路，落 `DOCUMENTS_ROOT/web/{owner}/*.md`（带来源头）+ `rag_system.import_document` + course KB。
- **Phase 2 researchContext**：课件生成的 web 部分调本层 `basic`（摘要实时注入），或直接走已入库 RAG（`deepsearch full` 预填后由 RAG Top-K 覆盖）。
- **sidecar**：sidecar 自带的 web search（`lib/web-search`）**保留可用**——web 功能独立于 sidecar，二者不冲突。课件生成默认 `enableWebSearch=false`（web 由 edu_ai 侧本层统一产出注入）；sidecar 的 web search 作为可选/兜底能力保留。SPEC-04 §4 的 sidecar 合并补丁因此降级为可选。

---

## 11. 旧链路下线登记（v0.2 本阶段执行）

本阶段目标是 `Edu_AI/api/src` 内无旧 web 文本检索链路引用，并且图片搜索不再依赖 SearXNG。

**删除/清理清单**：

- `app/deepsearch_pipeline.py`
- `app/deepsearch_loader.py`
- `tests/chat/test_deepsearch_loader.py`
- `deepsearch_service` 里的 EduAgent fallback / crawler / cleaner / storage / large_llm 分支
- `agent_tools.py` / `search_tools.py` 对 `run_deepsearch_pipeline` 的导入和调用
- `app/chat/runtime/agent_tools/handlers/providers/searxng_provider.py`
- `IMAGE_SEARCH_PROVIDER=searxng`
- `SEARXNG_BASE_URL`
- 面向用户或测试的 “检查 IMAGE_SEARCH_PROVIDER / SEARXNG_BASE_URL” 提示
- 测试中把图片 provider 固定为 `searxng` 的断言

**保留**：`deepsearch_importer`、`crawl_batch_store`、`/agent/deepsearch-and-crawl` 端点、`image_search` 工具名和 payload 结构。

---

## 12. 验收清单（→ [ACC-00](../acceptance/ACC-00_Web检索层_验收.md)）

- [ ] Bocha 搜索真实 API 冒烟通过（中文 query → url+summary）
- [ ] Bocha 图片搜索真实 API 冒烟通过（中文 query → 可访问图片 URL）
- [ ] Tavily Extract 真实 API 冒烟通过（一批 url → markdown 全文，中文页面可抽）
- [ ] `depth=basic` / `depth=full` 双档各通
- [ ] 主对话 `web_search_tool` 走 Bocha basic，不再导入 `run_deepsearch_pipeline`
- [ ] `image_search` 在 `IMAGE_SEARCH_PROVIDER=bocha` 时返回 `images[]`，`trace.provider == "bocha"`
- [ ] 结果入 RAG（复用链路），`DOCUMENTS_ROOT/web/{owner}` 落盘 + 可检索
- [ ] `run_deepsearch_and_crawl` 签名 + 端点 + 前端不变（回归）
- [ ] 降级：Bocha 失败返回空、Tavily 部分失败跳过、全失败退回 basic
- [ ] `BOCHA_API_KEY` / `TAVILY_API_KEY` 不出现在日志
- [ ] `rg -n "deepsearch_pipeline|deepsearch_loader|load_eduagent_capabilities|EduAgent|crawler_service|content_cleaner|storage_service|deepsearch_large_llm" Edu_AI/api/src/app Edu_AI/api/src/tests` 无旧链路业务引用
- [ ] `rg -n "SearXNG|searxng|SEARXNG_BASE_URL" Edu_AI/api/src/app Edu_AI/api/src/tests Edu_AI/api/src/.env.example` 无运行时依赖
