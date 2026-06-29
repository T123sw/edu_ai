# Phase 6-A image_search 工具实施计划

**创建日期**：2026-06-11  
**基于设计**：`docs/agent_architecture_design_2026-05-25.md` 第十六章 §16.4 / 第十三章 Phase 6-A  
**前置启发**：`docs/agent架构设计` + `docs/tvir总结`  
**总工期**：4 天（含 SearXNG 部署）  
**风险等级**：低（不改 graph/state/planner，纯增量；旧 web_search 流不动）

---

## 一、目标与非目标

### 目标

1. 落地一个独立的 `image_search` 工具，由 SearXNG 提供检索后端
2. **激活已写好的 `VisionReflector`**（当前为死代码——没有上游产 `images`）
3. 让现有 `generate_report` 能引入"外部搜索得到的真实图片"作为配图素材（而不仅限于 RAG 文档嵌入图）
4. 为 Phase 6-B（Planner 子图 + visual_need 规划）打底，使其能直接调用 image_search 而无须工具层再变更

### 非目标

- ❌ 不做 Planner 子图改造（属 Phase 6-B）
- ❌ 不做 PlanStep.visual_need 字段（属 Phase 6-B-3）
- ❌ 不做大纲编辑 HITL（属 Phase 6-B-4）
- ❌ 不做 Polisher 节点（属 Phase 6-C）
- ❌ 不做 diagram_gen 工具（Phase 6-A 内并列任务，但本计划只覆盖 image_search）
- ❌ 不做 image proxy 后端（导出场景需求，6-A 仅预留 `proxy_url` 占位字段）
- ❌ 不实现 batch query（单次请求一个 query，靠 ThreadPool 多 step 并发）

---

## 二、关键决策（已锁定）

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| 1 | Provider | SearXNG 自托管 | 零额度费用、JSON API 干净、可控隐私边界 |
| 2 | 工具结果是否进 `_call_cache` | **不进**（NEVER_CACHE 白名单） | HITL 刷新图片时需要重搜，且网络结果本身就该重跑 |
| 3 | `capability.allow_image_search` 默认 | **False** + step 级覆盖 | 普通对话不暴露此工具，避免无意义搜图；Phase 6-B 时由 strict mode 按 `visual_need.required=True` 临时启用 |
| 4 | `proxy_url` 字段 | **预留占位**（不实现 proxy 后端） | PPT/PDF 导出时绕 CORS 用，6-A 阶段不构建 proxy 服务，schema 留口 |
| 5 | batch query | **不支持** | 工具单次单 query，并发由 Executor 的 ThreadPoolExecutor 在多个 image_search step 之间承担 |

---

## 三、SearXNG 部署指引

### 3.1 docker-compose 起服务

新增文件：`infra/searxng/docker-compose.yml`（仓库根目录 `infra/` 不存在则新建）

```yaml
services:
  searxng:
    image: searxng/searxng:latest
    container_name: edu-ai-searxng
    ports:
      - "8888:8080"            # 主机 8888 → 容器 8080，避开常用 8080
    volumes:
      - ./settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - BASE_URL=http://localhost:8888/
      - INSTANCE_NAME=edu-ai-internal
    restart: unless-stopped
    networks:
      - edu-ai
networks:
  edu-ai:
    name: edu-ai
    driver: bridge
```

### 3.2 settings.yml 关键配置

新增文件：`infra/searxng/settings.yml`

```yaml
use_default_settings: true

general:
  instance_name: "edu-ai-internal"
  enable_metrics: false

server:
  secret_key: "REPLACE_ME_WITH_OPENSSL_RAND_HEX_32"   # 部署时替换
  limiter: false                                       # 内网调用不限流
  image_proxy: false                                   # 我们后期自建 proxy，不走 searxng
  http_protocol_version: "1.1"

search:
  safe_search: 1                # 0=off, 1=moderate, 2=strict；默认 moderate
  autocomplete: ""
  default_lang: "auto"
  formats:
    - html
    - json                      # **必开**，否则我们的 provider 拿不到 JSON

# 仅启用图片搜索引擎，关掉其他类别可加速冷启动
engines:
  - name: bing images
    disabled: false
  - name: duckduckgo images
    disabled: false
  - name: google images
    disabled: false
  - name: brave.images
    disabled: false
  # 其他默认禁用
```

### 3.3 启动验证

```bash
cd infra/searxng
# 生成 secret_key 并替换
openssl rand -hex 32   # 拷贝结果，替换 settings.yml 里的 REPLACE_ME_...

docker compose up -d
docker logs edu-ai-searxng | tail -20   # 看是否 "starting search engine ..."

# 冒烟测试
curl 'http://localhost:8888/search?q=quicksort+diagram&categories=images&format=json' \
  | jq '.results | length'
# 期望：> 0
```

### 3.4 环境变量

在 `.env` 增加：
```bash
SEARXNG_BASE_URL=http://localhost:8888
IMAGE_SEARCH_PROVIDER=searxng
IMAGE_SEARCH_TIMEOUT_S=8
IMAGE_SEARCH_DEFAULT_COUNT=6
IMAGE_SEARCH_MAX_COUNT=12
```

---

## 四、Provider 抽象与 SearXNG 实现

### 4.1 文件结构

```
Edu_AI/api/src/app/chat/runtime/agent_tools/handlers/
├── image_search.py              # 新增 handler
└── providers/
    ├── __init__.py
    ├── image_base.py            # ImageSearchProvider Protocol + build_default()
    └── searxng_provider.py      # SearxngImageSearchProvider 实现
```

### 4.2 Protocol 定义

```python
# providers/image_base.py
from __future__ import annotations

import os
from typing import Protocol


class ImageSearchProvider(Protocol):
    name: str

    def search(
        self,
        *,
        query: str,
        count: int,
        style: str,
        safe: bool,
        license_: str,
        owner: str | None,
    ) -> list[dict]:
        """Return list of raw image dicts. Provider-specific schema is fine —
        normalize_for_tool() will reduce to our internal shape."""
        ...


def build_default_provider() -> ImageSearchProvider | None:
    """Construct provider per env. Returns None if not configured."""
    name = (os.getenv("IMAGE_SEARCH_PROVIDER") or "").lower()
    if name == "searxng":
        from .searxng_provider import SearxngImageSearchProvider
        base = os.getenv("SEARXNG_BASE_URL", "").rstrip("/")
        if not base:
            return None
        timeout = float(os.getenv("IMAGE_SEARCH_TIMEOUT_S", "8"))
        return SearxngImageSearchProvider(base_url=base, timeout=timeout)
    return None
```

### 4.3 SearXNG 实现

```python
# providers/searxng_provider.py
from __future__ import annotations

import httpx


class SearxngImageSearchProvider:
    name = "searxng"

    def __init__(self, *, base_url: str, timeout: float = 8.0):
        self._base = base_url
        self._timeout = timeout

    def search(
        self,
        *,
        query: str,
        count: int,
        style: str,
        safe: bool,
        license_: str,
        owner: str | None,
    ) -> list[dict]:
        params = {
            "q": _build_query(query, style),
            "categories": "images",
            "format": "json",
            "safesearch": "1" if safe else "0",
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self._base}/search", params=params)
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results") or []
        out: list[dict] = []
        for item in results[: count * 3]:    # 取 3 倍冗余，过滤后再截到 count
            out.append({
                "url": item.get("img_src") or item.get("url") or "",
                "source_page": item.get("url") or "",
                "title": (item.get("title") or "").strip(),
                "width": int(item.get("img_width", item.get("resolution", "0x0").split("x")[0] or 0) or 0),
                "height": int(item.get("img_height", item.get("resolution", "0x0").split("x")[-1] or 0) or 0),
                "thumbnail": item.get("thumbnail_src") or item.get("thumbnail") or "",
                "license": None,   # SearXNG 不返回 license，统一为 None
                "_provider": "searxng",
            })
        return out


def _build_query(query: str, style: str) -> str:
    # style 仅作 query 修饰，SearXNG 无 style 参数
    suffix = {
        "diagram": " diagram OR flowchart OR architecture",
        "chart":   " chart OR graph OR plot",
        "real":    " photo OR photograph",
        "any":     "",
    }.get(style, "")
    return query + suffix
```

### 4.4 设计要点

- **3 倍冗余**：SearXNG 返回结果质量参差不齐，先取 3×count，由 handler 启发式过滤后截到 count
- **style 修饰 query**：SearXNG 无 style 参数，用关键词加权代替
- **license 字段为 None**：SearXNG 不返回；Polisher 阶段若 license_required 直接全部标 issue（属 6-C）
- **httpx 同步**：与 deepsearch_pipeline 风格一致，不引入 async 复杂度

---

## 五、Handler 实现

### 5.1 handler 主体

新增文件：`Edu_AI/api/src/app/chat/runtime/agent_tools/handlers/image_search.py`

```python
from __future__ import annotations

import datetime as _dt
from urllib.parse import urlparse

from app.chat.runtime.agent_tools.result import error_result, ok_result


_BLOCKED_HOSTS = {
    "pinterest.com", "pinimg.com", "facebook.com",
    "instagram.com", "twitter.com", "x.com",
}
_ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}


def handle_image_search(name: str, args: dict, ctx) -> dict:
    query = str(args.get("query", "")).strip()
    if not query:
        return error_result("image_search", "empty_query", "搜索词为空")

    count = max(1, min(int(args.get("count", 6)), 12))
    style = str(args.get("style", "any"))
    safe = bool(args.get("safe", True))
    license_ = str(args.get("license", "any"))

    provider = getattr(ctx, "image_search_provider", None)
    if provider is None:
        return error_result(
            "image_search",
            "provider_not_configured",
            "未配置图片搜索 provider（检查 SEARXNG_BASE_URL）",
        )

    try:
        raw = provider.search(
            query=query, count=count, style=style, safe=safe, license_=license_,
            owner=getattr(getattr(ctx, "request", None), "owner", None),
        )
    except Exception as exc:
        return error_result("image_search", str(exc), f"图片搜索失败: {exc}")

    candidates = [_normalize(img) for img in raw if _passes_heuristics(img)]
    candidates = _dedup_by_source(candidates)[:count]

    return ok_result(
        tool="image_search",
        summary=f"搜到 {len(candidates)} 张候选图（原始 {len(raw)}）",
        payload={
            "images": candidates,    # VisionReflector 期望字段名
            "query": query,
            "trace": {
                "provider": getattr(provider, "name", "unknown"),
                "raw_count": len(raw),
                "filtered_count": len(candidates),
            },
        },
    )


def _passes_heuristics(img: dict) -> bool:
    if int(img.get("width") or 0) < 200 or int(img.get("height") or 0) < 200:
        return False
    url = str(img.get("url") or "")
    if not url:
        return False
    ext = url.rsplit(".", 1)[-1].lower().split("?")[0]
    if ext not in _ALLOWED_EXT:
        return False
    host = (urlparse(url).hostname or "").lower()
    return not any(b in host for b in _BLOCKED_HOSTS)


def _normalize(img: dict) -> dict:
    return {
        "url": img["url"],
        "source_page": img.get("source_page") or "",
        "title": (img.get("title") or "")[:200],
        "width": int(img.get("width") or 0),
        "height": int(img.get("height") or 0),
        "thumbnail": img.get("thumbnail") or img["url"],
        "license": img.get("license"),
        "proxy_url": None,             # 占位，Phase 后期由 proxy 服务填
        "provenance": {
            "provider": img.get("_provider", "unknown"),
            "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        },
    }


def _dedup_by_source(images: list[dict]) -> list[dict]:
    seen, out = set(), []
    for img in images:
        key = img["source_page"] or img["url"]
        if key in seen:
            continue
        seen.add(key)
        out.append(img)
    return out
```

---

## 六、6 处接线 Diff

### 6.1 registry.py（注册 handler）

```python
# agent_tools/registry.py
from app.chat.runtime.agent_tools.handlers.image_search import handle_image_search  # NEW

def get_tool_handler(name: str) -> ToolHandler | None:
    if name == "rag_search":     return handle_rag_search
    if name == "web_search":     return handle_web_search
    if name == "image_search":   return handle_image_search   # NEW
    if name == "draft_outline":  return handle_draft_outline
    return _GENERATE_HANDLERS.get(name)
```

### 6.2 tool_meta.py（ToolMeta + NEVER_CACHE）

```python
# agent_tools/tool_meta.py
_TOOL_META: dict[str, ToolMeta] = {
    # ... 原有 ...
    "image_search": ToolMeta(            # NEW
        name="image_search",
        parallel_safe=True,
        mutates_state=False,
    ),
}

# NEW 常量，executor 读
NEVER_CACHE: frozenset[str] = frozenset({"image_search"})
```

### 6.3 executor.py（NEVER_CACHE + capability 检查）

```python
# agent_tools/executor.py
from app.chat.runtime.agent_tools.tool_meta import NEVER_CACHE  # NEW

def execute_tool(name: str, args: dict, ctx) -> dict:
    if ctx.step_count >= ctx.max_steps:
        return error_result(name, "budget_exceeded", "已达最大工具调用次数")
    if not _capability_allows(name, ctx.capability):
        return error_result(name, "permission_denied", "capability 不允许此工具")
    if name not in NEVER_CACHE and ctx.already_called(name, args):  # MOD
        return ctx.get_cached_result(name, args)
    # ... 余下不变

def _capability_allows(name: str, capability) -> bool:
    if name == "rag_search"   and not getattr(capability, "allow_rag", False):   return False
    if name == "web_search"   and not getattr(capability, "allow_web", False):   return False
    if name == "image_search" and not getattr(capability, "allow_image_search", False):  # NEW
        return False
    return True
```

### 6.4 schemas.py（schema + build_tool_schemas 接入）

```python
# agent_tools/schemas.py
SCHEMA_IMAGE_SEARCH = {
    "type": "function",
    "function": {
        "name": "image_search",
        "description": (
            "为正在生成的报告/PPT/教案小节搜索配图。"
            "仅在确实需要视觉素材的章节使用（流程/结构/案例/人物/场景类），"
            "概念定义类章节不需要调用。"
            "使用英文检索词通常命中率更高。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "图片检索关键词（英文更佳）"},
                "count": {"type": "integer", "default": 6, "description": "候选数量上限，1-12"},
                "style": {
                    "type": "string",
                    "enum": ["real", "diagram", "chart", "any"],
                    "default": "any",
                    "description": "real=照片 / diagram=示意图 / chart=数据图 / any=不限",
                },
            },
            "required": ["query"],
        },
    },
}

def build_tool_schemas(capability) -> list[dict]:
    schemas = []
    if getattr(capability, "allow_rag", False):
        schemas.append(SCHEMA_RAG_SEARCH)
    if getattr(capability, "allow_web", False):
        schemas.append(SCHEMA_WEB_SEARCH)
    if getattr(capability, "allow_image_search", False):   # NEW
        schemas.append(SCHEMA_IMAGE_SEARCH)
    schemas.extend([
        SCHEMA_DRAFT_OUTLINE,
        SCHEMA_GENERATE_REPORT,
        SCHEMA_GENERATE_PPT,
        SCHEMA_GENERATE_LESSON_PLAN,
        SCHEMA_GENERATE_QUIZ,
    ])
    return schemas
```

### 6.5 context.py（注入 provider）

```python
# agent_tools/context.py
class ToolExecutionContext:
    def __init__(
        self,
        *,
        capability,
        max_steps: int,
        rag_retriever=None,
        web_retriever=None,
        workflow_registry=None,
        background_runner=None,
        agent_gateway=None,
        request=None,
        snapshot=None,
        image_search_provider=None,    # NEW
    ):
        # ... 原有 ...
        self.image_search_provider = image_search_provider
```

### 6.6 reply_service_v2.py（构造 ctx 时注入）

```python
# application/reply_service_v2.py
from app.chat.runtime.agent_tools.handlers.providers.image_base import build_default_provider  # NEW

# 在构造 ToolExecutionContext 处：
ctx = ToolExecutionContext(
    capability=capability,
    max_steps=...,
    rag_retriever=rag_search_tool,
    web_retriever=web_search_tool,
    # ... 原有 ...
    image_search_provider=build_default_provider(),   # NEW
)
```

### 6.7 capability 定义（添加 allow_image_search 字段）

需在 capability 数据类（搜 `allow_rag` 的定义位置）追加：
```python
allow_image_search: bool = False
```

Phase 6-A 阶段在哪些入口启用？建议两种激活：
- **报告/PPT/教案生成入口**：根据资源类型预先开启
- **Phase 6-B 上线后**：strict mode 按 visual_need.required 临时覆盖

### 6.8 VisionReflector applies_to（一行改动）

```python
# runtime/reflection/vision.py
class VisionReflector(BaseReflector):
    priority = 20
    _APPLIES_TO = {"image_search", "web_search", "rag_search"}   # MOD: 新增 image_search
```

### 6.9 nodes/tools.py 输出格式化

```python
# nodes/tools.py _format_tool_result_for_context
if tool_name == "image_search":
    payload = result.get("payload", {})
    images = payload.get("images") or []
    return (
        f"图片检索完成：候选 {len(images)} 张。"
        f"VisionReflector 将审查相关性与质量，过滤后保留合格图片。"
    )
```

### 6.10 nodes/constants.py 中文名/提示

```python
# nodes/constants.py
_TOOL_NAMES_CN["image_search"] = "图片搜索"
_OBSERVE_HINTS["image_search"] = (
    "（若候选全部被审查淘汰，可换更具体的英文 query 或调整 style 重新搜索）"
)
_ARG_KEYS_CN["style"] = "风格"
_ARG_KEYS_CN["count"] = "数量"
```

---

## 七、Phase 6-A 阶段如何对接报告生成

**Phase 6-A 不改 Planner、不改 generate_report 的 schema**。承接现状：

1. 用户对话中 agent 决定调 `image_search`（capability 开启时）
2. Executor 跑工具 → 结果含 `payload.images`
3. tools_node → reflect_node：VisionReflector 接管，VLM 审图，`filtered_data={"images": good}` 写入 `state.reflect_filtered`
4. 下一轮 executor 把 filtered 图通过现有 `_inject_reflect_hint` 路径让 LLM 看到
5. LLM 在最后调 `generate_report` 时，可以把图 URL 写进 confirmed_outline 或 focus 字段（**Phase 6-A 临时方案**）
6. 报告 handler 现有的 `image_injector` 路径保持不变（仍只注入 RAG 嵌入图）

**说明**：6-A 阶段的"图进报告"是间接的——靠 LLM 在 confirmed_outline 文字里写 `![alt](url)` 实现。这能立刻看到效果。

**Phase 6-B 时升级**：state 新增 `visual_assets: dict[section_id, list]`，reflect_node 直接累积，generate_report schema 增加 `visual_assets` 字段，image_injector 改为按 section_id 注入。

---

## 八、测试矩阵

### 8.1 单元测试

新增文件：`Edu_AI/api/src/tests/chat/runtime/agent_tools/test_image_search_handler.py`

| 用例 | 输入 | 期望 |
|---|---|---|
| T1: provider 未配置 | `ctx.image_search_provider = None` | `error_result(provider_not_configured)` |
| T2: 空 query | `args={"query": ""}` | `error_result(empty_query)` |
| T3: provider 抛异常 | mock provider.search raise | `error_result` 含异常信息 |
| T4: 正常返回 | mock 返回 10 张图（含 3 张低质） | `ok_result`，candidates 长度 ≤ count，低质被过滤 |
| T5: 启发式过滤 | mock 返回宽 100 / pinterest 域 / .pdf 后缀 | 全部被丢弃 |
| T6: source_page 去重 | mock 返回 3 张同一 source_page | 仅保留 1 张 |
| T7: count 上限 | `args={"count": 100}` | 实际截到 12（MAX_COUNT） |

### 8.2 SearXNG provider 集成测试

文件：`tests/chat/runtime/agent_tools/handlers/providers/test_searxng_provider_integration.py`  
（标记 `@pytest.mark.integration`，CI 跳过，本地手跑）

| 用例 | 期望 |
|---|---|
| 真实查询 "quicksort algorithm" | 返回 >= 3 张图，含 width/height/url |
| style="diagram" 修饰 query | result query 含 "diagram OR flowchart" |
| SearXNG 不可达（端口关闭） | provider.search raise httpx.ConnectError |

### 8.3 端到端冒烟测试

新增文件：`Edu_AI/api/src/test_p6a_image_search_e2e.py`（沿用 `test_p3b_report_images.py` 体例）

```python
# 1. 启动一个 ToolExecutionContext，capability.allow_image_search=True
# 2. 模拟 LLM 输出 tool_call image_search(query="rag architecture diagram")
# 3. 跑 tools_node → reflect_node（mock vision_gateway 返回部分合格）
# 4. 断言：reflect_filtered.images 非空，且原始 images 在 tool_exchange 中
```

### 8.4 VisionReflector 复用测试

更新：`tests/chat/runtime/reflection/test_vision_reflector.py`（如不存在则新增）

- T1: tool_name="image_search" + require_images=True → 进入 VLM 审查
- T2: tool_name="image_search" + require_images=False → 直接 pass（不消耗 VLM 配额）
- T3: 所有图被淘汰 + retry_count < max → verdict=retry, severity=blocking
- T4: 所有图被淘汰 + retry_count >= max → 降级为 pass_with_warning

---

## 九、验收清单

### 9.1 部署验收

- [ ] SearXNG docker 容器健康，`docker ps` 显示 running
- [ ] `curl 'http://localhost:8888/search?q=test&categories=images&format=json'` 返回非空 results
- [ ] `.env` 配置正确，应用启动日志显示 "image_search provider: searxng"

### 9.2 代码验收

- [ ] handler / provider / Protocol 三文件就位
- [ ] 6 处接线全部完成（registry / tool_meta+NEVER_CACHE / executor / schemas+build / context / reply_service_v2）
- [ ] capability 定义增加 `allow_image_search` 字段
- [ ] VisionReflector applies_to 一行改动
- [ ] tools.py / constants.py 输出格式化与中文名

### 9.3 测试验收

- [ ] 单元测试 7 个用例全过
- [ ] SearXNG 集成测试本地手跑通过
- [ ] 端到端冒烟测试通过
- [ ] VisionReflector 测试 4 用例全过
- [ ] 现有所有测试不破坏（特别是 Phase 3/5 测试）

### 9.4 行为验收

- [ ] 在 capability 关闭时，LLM 看不到 image_search schema，普通对话不会调用
- [ ] 在 capability 开启时，LLM 主动调用 image_search 后，前端能看到 `tool_call` SSE
- [ ] image_search 工具结果在 tool_exchange 中保留完整 payload
- [ ] 端到端跑一份"快速排序"教学报告，输出 Markdown 中出现至少 1 张外部搜索图（图片可访问）

---

## 十、回滚方案

由于本期改动**全部为增量**，无破坏性改动，回滚极简：

1. **关闭 capability**：所有调用入口将 `allow_image_search` 设为 False，schema 不再下发给 LLM
2. **不依赖此工具的旧路径完全不动**——`web_search` / `rag_search` / `generate_report` 行为不变
3. **VisionReflector**：`_APPLIES_TO` 改回 `{"web_search", "rag_search"}` 即恢复原状（一行 revert）
4. **SearXNG 容器**：`docker compose down` 即可，无残留状态

---

## 十一、4 天工作分解

### Day 1：SearXNG 部署 + Provider 落地（独立可工作）

| 时段 | 内容 | 交付物 |
|---|---|---|
| AM | SearXNG docker 部署、settings.yml 调优、JSON API 跑通 | curl 验证返图 |
| PM | `providers/image_base.py` + `searxng_provider.py` 编码 | provider 单测通过（含 mock httpx） |

**独立可验证**：单跑 `python -c "from providers.image_base import build_default_provider; p = build_default_provider(); print(p.search(query='rag diagram', count=5, style='diagram', safe=True, license_='any', owner=None))"`

### Day 2：Handler + 6 处接线

| 时段 | 内容 | 交付物 |
|---|---|---|
| AM | `image_search.py` handler 编码 + 单元测试 7 例 | 单测全过 |
| PM | 6 处接线（registry / tool_meta / executor / schemas / context / reply_service_v2） + capability 字段 + VisionReflector 一行 | 现有所有测试不破坏 |

**独立可验证**：用 pytest 跑全套，加新增 image_search 单测；mock 一个 capability.allow_image_search=True 的 ToolExecutionContext，手工调 execute_tool("image_search", {"query":"test"}, ctx)，断言返回结构正确

### Day 3：端到端冒烟 + VisionReflector 复用验证

| 时段 | 内容 | 交付物 |
|---|---|---|
| AM | 端到端冒烟测试编写 + 调试 | test_p6a_image_search_e2e.py 通过 |
| PM | VisionReflector 4 用例测试 + 修补边角（如 require_images 默认值、retry 降级） | reflect 测试全过 |

**独立可验证**：跑一遍完整对话："帮我做一份 RAG 报告，要配图" → 观察 SSE 流，应能看到 `tool_call image_search` + `tool_result` + `reflect`

### Day 4：报告端集成 + 文档收尾

| 时段 | 内容 | 交付物 |
|---|---|---|
| AM | 跑通"对话生成报告含外部图"的临时路径（让 LLM 把图 URL 写进 confirmed_outline 文字） | 生成的 Markdown 含 `![alt](url)` 真实生效 |
| PM | 更新主架构文档：第十六章 §16.4.4 验收勾选；本计划文档勾选验收清单；记录已知问题清单 | 本文档全部 ☑️ |

**最终验收**：构造一个真实对话场景，前端看到完整流程：plan → tool_call image_search → 候选图 SSE → reflect 过滤 → 报告生成 → Markdown 含真图。

---

## 十二、已知风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| SearXNG 搜出来质量参差 | 候选过滤后剩 0 张 | 3× 冗余 + retry hint 让 LLM 换 query |
| 图片热链失效 | 报告里图 URL 打不开 | Phase 6-A 阶段接受此风险，导出场景留 proxy_url 占位 |
| VLM 审图慢（每张 1-3s） | 6 张串行 18s | VisionReflector 已用 ThreadPoolExecutor 并发，max_workers=5 |
| SearXNG 单点故障 | image_search 整体失败 | provider 抛异常 → handler 返回 error_result，LLM 看到后跳过继续 |
| 教育场景未成年人保护 | 误搜出不当图 | safesearch=1 默认、style 不允许 "real" 用于人物场景（prompt 约束） |
| 法务/版权 | 引用图片来源不明 | provenance 字段保留 source_page，Phase 6-C Polisher 生成引用列表 |

---

## 十三、与 Phase 6-B 的衔接

Phase 6-A 完成后，下列工作转入 6-B：

1. PlanStep 增加 `visual_need` 字段（`type / query_candidates / insert_position / max_count / purpose`）
2. Planner 子图（skeleton/research/synthesize）在 synthesize 阶段产 visual_need
3. AgentState 增加 `visual_assets: dict[section_id, list]`，reflect_node 把通过审查的图按 section_id 累积
4. generate_report schema 增加 `visual_assets` 参数，image_injector 改造为按 section_id 定向注入
5. strict mode：visual_need.required=True 的 step 自动 `allow_image_search` 局部覆盖为 True

这些都不在本 6-A 计划范围内。本计划只确保：**底层工具就位且能被验证可用**。

---

## 附录 A：环境变量速查

```bash
# Phase 6-A 新增
SEARXNG_BASE_URL=http://localhost:8888
IMAGE_SEARCH_PROVIDER=searxng              # 当前仅支持 searxng
IMAGE_SEARCH_TIMEOUT_S=8                    # 单次 HTTP 超时
IMAGE_SEARCH_DEFAULT_COUNT=6
IMAGE_SEARCH_MAX_COUNT=12

# 已有，确认就绪
VISION_MODEL_ID=...                         # VisionReflector 依赖
QWEN_BASE_URL=...
QWEN_API_KEY=...
```

## 附录 B：依赖

新增 Python 依赖：
```
httpx>=0.27   # 若未在 requirements 中（检查后决定是否新增）
```

部署依赖：
```
docker / docker compose
```
