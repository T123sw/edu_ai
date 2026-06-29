# Phase 6-A.2 — Agent 搜来的图片本地化 实施计划

**创建日期**：2026-06-29
**基于现状**：`docs/Phase6A_image_search_实施计划_2026-06-11.md`（§一"非目标"专门把"image proxy 后端"留作后续工作）
**前置 Commit**：`793723e feat(agent): Phase 6-A/6-B`（图片搜索 + Planner 视觉规划已上线）
**总工期**：3-4 天
**风险等级**：低-中（新增独立子系统，下载失败有 fallback；不动 image_search / image_injector 现有 API 形态）

---

## 一、问题陈述

当前 Phase 6-A 状态：

```python
# image_injector 注入 Markdown 用的是源站 URL
![SAI Notes #07: What is a Vector Database?](https://substackcdn.com/.../diagram.png)
                                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                外网原始 URL，未本地化
```

带来的问题（按严重度）：

| # | 风险 | 实际影响 |
|---|---|---|
| 1 | 源站删图 / 换 URL | 报告里 broken image |
| 2 | 源站启用 hotlink protection（403 Referer 校验） | 学生打开报告图加载不出来 |
| 3 | 国内访问国外 CDN 慢 / 被墙 | 加载延迟，时不时失败 |
| 4 | 离线导出 PPT/PDF | 必然失败（没网就没图）|
| 5 | 法务追溯 | 没有本地副本，无法证明"引用时是这样" |
| 6 | 教学场景重看 | 老师第二天打开，图可能跟首次生成时不一样 |

Phase 6-A handler 已经预留了 `proxy_url: None` 字段，就是为这一步打底。

---

## 二、目标与非目标

### 目标

1. 报告 / PPT / 教案中 agent 搜来的图片**永久持久化在本地**
2. 同一 URL **只下一次**（按 URL hash 去重）
3. Markdown 里的链接改用项目自己的路径，**前端 / 导出工具 / 离线场景都能加载**
4. 下载失败时**优雅回落到原 URL**——不阻断报告生成
5. 保留**完整来源元数据**（source_page / license / fetched_at / alt）方便法务追溯
6. 提供一个 FastAPI 路由 `/api/images/searched/{hash}.{ext}` 服务本地文件

### 非目标

- ❌ 不做"代理回源"（本地未命中 → 实时拉源站）。下载只在 `image_injector` 注入前同步完成一次
- ❌ 不做自动清理（按时间过期、引用计数等）。预留人工清理脚本入口即可
- ❌ 不做格式转换（webp/svg → png 等）。保留原格式
- ❌ 不接入数据库表。元数据用 sidecar JSON 文件
- ❌ 不做 CDN 加速 / 图床外推。本地服务即可
- ❌ 不处理 SVG（搜索结果几乎不返回 SVG，暂时不专门支持）

---

## 三、关键决策（已锁定）

| # | 决策点 | 选择 | 理由 |
|---|---|---|---|
| 1 | 存储根路径 | `Edu_AI/api/src/storage/searched_images/` | 与 chat_images / images 并列，命名清晰区分 |
| 2 | 子目录分片 | 按日期：`{YYYYMMDD}/{hash}.{ext}` | 简单 / 便于按时间清理 / 单目录文件数可控 |
| 3 | 文件名 hash 算法 | `sha256(URL).hexdigest()[:16]` | 16 字符够防碰撞；用 URL 而非内容做 hash → 同 URL 直接命中缓存 |
| 4 | 扩展名 | 优先源 URL，回落 Content-Type | URL 上有 `.png` 直接用；没有 → 看 HTTP 响应 header |
| 5 | 元数据格式 | sidecar JSON：`{hash}.json` 与图同目录 | 无需 DB 迁移；可移植；调试友好 |
| 6 | **下载时机** | **异步并行（A 模式）** | `_run()` 一开始就 fire downloads，与 LLM 生成并行；总耗时 ≈ max(LLM, download)；下载默默吸收在 LLM 时间里 |
| 7 | 单图下载超时 | 10 秒 | 介于"足够慢源站"和"不卡死"之间 |
| 8 | 单图大小上限 | 10 MB | 防止极端图爆磁盘；超大当作失败 |
| 9 | 失败处理 | 保留原 URL + 记一条 sidecar JSON 标 `download_failed` | 不阻断 generate_report |
| 10 | **Markdown URL 形式** | **相对路径** `/api/images/searched/{hash}.{ext}` | 前端 / 导出工具都能用；不耦合域名 |
| 11 | FastAPI 路由 | `GET /api/images/searched/{hash_with_ext}` | RESTful |
| 12 | **路由鉴权** | **走向 B：仅校验必须登录**（沿用 `get_current_user`）+ sidecar 仍记 course_ids / accessed_by 为未来 ACL 预留 | 当前系统没有"学生-课程"关系数据，无法做完整方案 3 ACL；走 B 让学生能看老师报告里的图，等选课关系落地再升级 |
| 13 | 跨 owner 共享 | 是，按 URL hash 去重 = 全局共享 | 同一张"vector database 架构图"alice 搜过，bob 直接复用本地缓存 |
| 14 | 并发下载 | 单报告内 `ThreadPoolExecutor(max_workers=4)` 并发 | 与 LLM 生成并行 → 缩短整体耗时；并发数低不滥用源站 |
| 15 | HTTP client | `httpx.Client`（已有依赖） | 复用 SearXNG provider 依赖栈 |
| 16 | User-Agent / Referer | 标准浏览器 UA，**不带 Referer** | 绕过 hotlink 检查 |
| 17 | 失败重试 | 同源 1 次重试（间隔 1s） | 抗瞬时网络抖动 |
| 18 | 与 image_search handler 的边界 | handler 只搜不下，**新增 `image_downloader` 模块** | 职责清晰，handler 保持纯函数 |
| 19 | sidecar accessed_by / course_ids 累积 | 每次 `localize_image` 读旧 sidecar 合并 owner / course_id 再写回 | 全局去重前提下保留多用户/多课程归属链 |
| 20 | join 超时（等下载） | LLM 完成后再等 5 秒下载，超时则用原 URL | 避免下载死循环卡死整个 generate_report |

---

## 四、模块结构

```
Edu_AI/api/src/
├── app/
│   ├── chat/workflows/report/
│   │   ├── image_injector.py                # 改造：注入前调 downloader
│   │   └── image_downloader.py              # 新增
│   └── api/
│       └── searched_images.py               # 新增：FastAPI 路由
├── storage/
│   └── searched_images/                     # 新增：根目录
│       └── 20260629/
│           ├── a3f8b2c1d4e6f7a9.png        # 图本体
│           └── a3f8b2c1d4e6f7a9.json       # sidecar metadata
└── tests/
    └── chat/workflows/report/
        ├── test_image_downloader.py        # 新增
        ├── test_image_injector_localization.py  # 新增
        └── test_searched_images_route.py    # 新增
```

---

## 五、数据流（端到端）

```
generate_report 后台任务
    ↓
build_report_markdown → 纯文本 body
    ↓
inject_images_into_report(body, accumulated_images, max_images=3)
    ↓
新行为：for each asset in candidates[:max_images]:
    ↓
    download_and_localize(asset)            ← image_downloader
        ├─ hash = sha256(asset.url)[:16]
        ├─ 检查本地：storage/searched_images/*/{hash}.* 已存在？
        │       → 是：跳过下载，复用现有
        │       → 否：httpx GET → 写入 {today}/{hash}.{ext} + sidecar JSON
        ├─ 成功 → 返回 LocalizedAsset{local_url="/api/images/searched/{hash}.{ext}",
        │                              source_url=原 url, alt=...}
        └─ 失败 → 返回原 asset（保留原 URL）+ 写 sidecar JSON 标 download_failed
    ↓
拼成 ![alt](/api/images/searched/{hash}.{ext}) 注入 Markdown
    ↓
artifact 落库

读取阶段：
前端拉 artifact.content → 渲染 Markdown
    ↓
浏览器加载 /api/images/searched/{hash}.png
    ↓
FastAPI searched_images.py GET 路由
    ↓
StreamingResponse (本地文件) 或 404
```

---

## 六、核心接口设计

### 6.1 `image_downloader.py`

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class LocalizedAsset:
    """A successfully-localized image asset, ready to be embedded."""
    local_url: str              # "/api/images/searched/{hash}.png"
    local_path: Path            # absolute filesystem path
    source_url: str
    source_page: str
    title: str
    alt: str
    content_type: str
    size_bytes: int
    hash: str                   # 16-char sha256 prefix
    fetched_at: str             # ISO 8601 UTC

@dataclass
class DownloadFailure:
    """Failure record — caller falls back to source URL."""
    source_url: str
    reason: str                 # e.g. "http_403" / "timeout" / "too_large" / "invalid_content_type"


def localize_image(
    asset: dict,
    *,
    storage_root: Path | None = None,
) -> LocalizedAsset | DownloadFailure:
    """Download an image_search asset to local storage.

    Idempotent: if {hash}.{ext} already exists, returns the cached LocalizedAsset
    without re-downloading.
    """


def batch_localize(
    assets: list[dict],
    *,
    storage_root: Path | None = None,
    max_concurrency: int = 1,
) -> list[LocalizedAsset | DownloadFailure]:
    """Download multiple assets sequentially (per decision #14)."""
```

### 6.2 `image_injector.py` 改造

```python
def inject_images_into_report(
    report_markdown: str,
    image_assets: list,
    max_images: int = 3,
    *,
    localize: bool = True,        # NEW: opt-in localization
) -> str:
    if localize and image_assets:
        # Only localize the assets we're actually about to inject
        to_localize = [a for a in image_assets if _asset_url(a)][:max_images]
        results = batch_localize(to_localize)
        # Replace asset URL with localized URL when successful
        image_assets = _apply_localization(to_localize, results)
    # ... rest of existing flow unchanged
```

### 6.3 sidecar JSON 格式

```json
{
    "hash": "a3f8b2c1d4e6f7a9",
    "source_url": "https://substackcdn.com/.../vector-db.png",
    "source_page": "https://example.com/article",
    "title": "SAI Notes #07: What is a Vector Database?",
    "license": null,
    "content_type": "image/png",
    "size_bytes": 234567,
    "fetched_at": "2026-06-29T10:23:45+00:00",
    "fetched_by": "alice",
    "provider": "searxng",
    "downloaded": true
}
```

下载失败的 sidecar：

```json
{
    "hash": "a3f8b2c1d4e6f7a9",
    "source_url": "https://example.com/broken.png",
    "downloaded": false,
    "failure_reason": "http_403",
    "attempted_at": "2026-06-29T10:23:45+00:00",
    "attempts": 2
}
```

### 6.4 FastAPI 路由

```python
# app/api/searched_images.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/images/searched", tags=["images"])

@router.get("/{filename}")
def get_searched_image(filename: str):
    # filename = "{hash}.{ext}"
    path = _resolve_path(filename)
    if path is None:
        raise HTTPException(404, "image not found")
    return FileResponse(path, media_type=_guess_mime(path))
```

注册：在 `app/api/__init__.py` 或 main app 里 `app.include_router(searched_images.router)`。

---

## 七、失败模式与回落

| 失败类型 | 处理 | Markdown 行为 |
|---|---|---|
| HTTP 4xx | 写 sidecar 标 `http_4xx`，1 次重试 | 回落到原 URL |
| HTTP 5xx | 同上，1 次重试 | 回落 |
| 超时（>10s） | 写 sidecar 标 `timeout` | 回落 |
| Content-Length > 10MB | 直接放弃，标 `too_large` | 回落 |
| Content-Type 非 image/* | 标 `invalid_content_type` | 回落 |
| 网络异常 | 标 `network_error`，1 次重试 | 回落 |
| 本地写文件失败（磁盘满 / 权限） | 标 `local_write_failed` | 回落 |
| 路由层 hash 文件不存在 | 404 | 浏览器显示破图 icon |

**关键点**：下载子系统的任何失败都不能让 generate_report 整体失败。

---

## 八、测试矩阵

### 8.1 image_downloader 单元测试（mock httpx）

| 用例 | 期望 |
|---|---|
| 首次下载成功 → 文件落地 + sidecar JSON 写入 | LocalizedAsset 返回，hash 匹配 |
| 二次下载（缓存命中）→ 不发 HTTP 请求 | 返回已缓存的 LocalizedAsset |
| HTTP 403 → 1 次重试后失败 | DownloadFailure(reason="http_403"), sidecar 含 attempts=2 |
| 超时 | DownloadFailure(reason="timeout") |
| Content-Length 头 > 10MB | DownloadFailure(reason="too_large"), 不实际下载内容 |
| Content-Type 非 image/* | DownloadFailure(reason="invalid_content_type") |
| 文件已存在但 sidecar 缺失 | 重新生成 sidecar（恢复） |
| 单图 URL 缺失 | DownloadFailure(reason="missing_url") |

### 8.2 image_injector 集成测试

| 用例 | 期望 |
|---|---|
| localize=True + 全部下载成功 | Markdown 含 `/api/images/searched/...` |
| localize=True + 部分失败 | 成功的用本地路径，失败的用原 URL |
| localize=False（向后兼容） | 完全等同 Phase 6-A 行为 |
| 单张图被 localize 多次 | 复用同一 hash，文件不重复 |

### 8.3 FastAPI 路由测试

| 用例 | 期望 |
|---|---|
| GET 存在的 hash.png → 200 | FileResponse 内容匹配 |
| GET 不存在的 hash → 404 | JSON error |
| GET 路径含 `../` 注入尝试 | 400/404，绝不放出 storage 外的文件 |
| GET 大文件 → StreamingResponse | 浏览器流式接收 |

### 8.4 真机 e2e（接 SearXNG）

- 跑完整 generate_report 流程
- 验证：报告 Markdown 含 `/api/images/searched/{hash}.png`
- 启 FastAPI dev server，浏览器访问 Markdown 渲染页，图片正常加载
- 删除原源 URL（mock 502），重新加载 Markdown，本地图仍然可访问

---

## 九、验收清单

### 部署 / 配置
- [ ] `storage/searched_images/` 目录在启动时自动创建（如不存在）
- [ ] 路由注册到主 FastAPI app
- [ ] 配置项（可选）：`SEARCHED_IMAGE_MAX_BYTES`, `SEARCHED_IMAGE_DOWNLOAD_TIMEOUT_S`

### 行为
- [ ] 真机 e2e 完整生成的报告 Markdown，所有图链接都是 `/api/images/searched/...` 路径
- [ ] 报告生成后 `storage/searched_images/{今日日期}/` 下有 N 个图 + N 个 sidecar JSON
- [ ] 删掉本地文件再请求路由 → 返回 404，浏览器显示破图（不会回源）
- [ ] 同一 URL 第二次出现 → 复用现有本地文件（看 `fetched_at` 不变）
- [ ] 故意搞个 404 的 URL → Markdown 里保留原 URL，sidecar 标 `download_failed`

### 测试
- [ ] downloader 单元测试 8 个全过
- [ ] injector 集成测试 4 个全过
- [ ] 路由测试 4 个全过
- [ ] 现有 109 个测试不破坏

### 文档
- [ ] image_injector 文档更新（新增 `localize` 参数说明）
- [ ] agent_architecture_design.md 第十六章 §16.4 添加"本地化"小节
- [ ] 本计划文档勾选验收清单

---

## 十、实施步骤（按 PR 切分）

### Step 1 — Downloader 子模块（半天）
- 新增 `image_downloader.py` + 配套测试
- 完全独立，不修改任何现有代码
- 可单独 commit / review

### Step 2 — FastAPI 路由（半天）
- 新增 `app/api/searched_images.py` + 测试
- 注册到主 app
- 启动后 `curl localhost:8000/api/images/searched/...` 可访问

### Step 3 — image_injector 接入 localize（半天）
- 改造 `inject_images_into_report` 接受 `localize=True` 参数
- 默认 `localize=True`（直接上）；可通过参数关闭
- 集成测试覆盖

### Step 4 — 报告 handler 端到端（半天）
- `handle_generate_report._run` 不需要改（image_injector 默认会本地化）
- 真机 e2e 验证整条链路
- 检查 storage 目录里实际有图

### Step 5 — 文档 + 验收 + commit（半天）
- 更新架构文档第十六章
- 勾选验收清单
- 单一 commit 上线（或分 4 个 commit 对应 4 个 step）

**总计** ≈ 3-4 个工作日

---

## 十一、与后续阶段的衔接

- **Phase 6-A.3 候选**：清理脚本（按天 / 按引用 / 手动）
- **Phase 6-A.4 候选**：HEIC / WebP → PNG 转换（PPT 导出兼容）
- **Phase 6-B.6 候选**：sidecar JSON 升级为 SQLite index（支持快速按 source_page / license 反查）
- **Phase 6-C 衔接**：Polisher 节点可以读 sidecar 元数据生成"图片来源"参考文献节

---

## 十二、关键非目标重申

- ❌ **不做代理回源**——本地未命中就是 404，不实时拉源站。如果将来需要，单独做。
- ❌ **不做自动清理**——磁盘满是运维问题，先不解决。
- ❌ **不做权限校验**——v1 公开服务。后期统一加 token 时再补。
- ❌ **不引入数据库表**——sidecar JSON 够用。要 SQL 查询时再升级。
- ❌ **不做格式转换**——保留原 PNG/JPEG/WebP/GIF。SVG 跳过。
- ❌ **不并发下载**——单报告内串行，避免对源站突发。

---

## 附录 A：环境变量

```bash
# 可选，全部有默认值
SEARCHED_IMAGE_STORAGE_ROOT=storage/searched_images
SEARCHED_IMAGE_MAX_BYTES=10485760              # 10 MB
SEARCHED_IMAGE_DOWNLOAD_TIMEOUT_S=10
SEARCHED_IMAGE_USER_AGENT="Mozilla/5.0 (compatible; EduAI/1.0; +https://...)"
```

## 附录 B：依赖

无新增 Python 依赖（httpx 已有）。

可能用到的标准库：
- `hashlib` (sha256)
- `pathlib`
- `json`
- `mimetypes` (MIME guess for FileResponse)
- `datetime` (timestamps)
