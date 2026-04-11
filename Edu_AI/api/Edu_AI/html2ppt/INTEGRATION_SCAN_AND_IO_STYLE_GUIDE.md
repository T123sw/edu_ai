# html2ppt 模块扫描与对接文档（含输入输出与样式示例）

## 1. 文档目的与范围

本文档用于把 `html2ppt` 模块快速接入现有系统，重点覆盖：

- 目录与代码职责扫描
- API 输入输出整理
- 任务状态与产物结构
- 内容协议（`content_markdown`）关键约束
- 样式/版式示例（主题、品牌位、布局类）
- 最小联调流程

适用目录：

- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt`

参考来源：

- `d:\Downloads\content-protocol.md`
- `d:\Downloads\ppt-service-api-draft.md`
- `d:\Downloads\README.md`
- 当前模块源码（`src/`, `format/`, `style/`, `scripts/`）

---

## 2. 目录扫描结论（对接视角）

### 2.1 核心运行文件（必须关注）

- `src/server.js`
  - HTTP 路由入口，监听 `127.0.0.1`
- `src/services/ppt-service.js`
  - 主业务编排：建任务、修订、生成、导出、状态推进
- `src/store/job-store.js`
  - 文件存储层：`job.json/revision.json/request.json`
- `src/lib/export-html-to-pptx.js`
  - HTML -> PPTX 导出链路（本地 server + headless Chrome）
- `src/agents/claude-code-runner.js`
  - 调用 Claude Code 生成 slide fragment
- `src/domain/content-protocol.js`
  - `content_markdown` 语法/媒体校验
- `src/lib/media-assets.js`
  - 远程或本地媒体本地化到 revision `media/`

### 2.2 内容与样式资源（必须保留）

- `format/*.html`
  - 各版式 HTML 骨架
- `format/layout.css`
  - 版式布局骨架样式
- `style/theme-*.css`
  - 主题样式
- `style/theme-brand-config.json`
  - 主题品牌位配置（logo 资源、alt、class）
- `assets/`
  - 品牌图和本地测试媒体

### 2.3 协议与说明（建议与你系统文档对齐）

- `content-protocol.md`
- `layout-contracts.md`
- `ppt-service-api-draft.md`
- `README.md`

### 2.4 工具与测试

- `scripts/build-standalone-html.js`
- `scripts/export-html-to-pptx.js`
- `test/ppt-service.test.js`
- `test-harness/`（本地导出调试）

---

## 3. 运行与配置要点

### 3.1 运行命令

```bash
npm install
npm start
```

或直接：

```bash
node src/server.js
```

### 3.2 关键环境变量

```dotenv
PPT_SERVICE_PORT=46080
PPT_DATA_DIR=./data
PPT_WORKER_CONCURRENCY=1
PPT_CHROME_PATH=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
PPT_CHROME_ARGS=[]
PPT_CLAUDE_CMD=claude
PPT_CLAUDE_ARGS=["-p","--output-format","text","--permission-mode","bypassPermissions"]
PPT_DEFAULT_THEME_ID=heu_academic_elegant
```

说明：

- Linux 部署时，`PPT_CHROME_PATH`、`PPT_CLAUDE_CMD` 必须改成服务器真实路径。
- 服务默认仅绑定 `127.0.0.1`，外部访问需反代。

---

## 4. API 输入输出整理

## 4.1 创建任务

### 请求

`POST /ppt/jobs`

```json
{
  "content_markdown": "# Deck\n- Title: 示例\n\n---\n\n## Slide 1\n- Role: cover\n- Title: 封面\n\n### Blocks\n- Lead: 副标题\n",
  "theme_id": "heu_academic_elegant",
  "metadata": {
    "request_id": "req_001",
    "timestamp": "2026-04-08T10:00:00+08:00",
    "idempotency_key": "idem_001",
    "user_id": "u_001",
    "tenant_id": "tenant_a"
  }
}
```

### 约束

- `content_markdown` 必填，必须通过内容协议校验。
- `theme_id` 必填，当前支持：
  - `heu_academic_elegant`
  - `heu_academic_basic`
- `metadata` 必填项：
  - `request_id`
  - `timestamp`
  - `idempotency_key`
  - `user_id`
- 幂等键按 `(tenant_id || "default", idempotency_key)` 去重。

### 响应

```json
{
  "job_id": "job_xxx",
  "status": "queued"
}
```

---

## 4.2 查询任务状态

### 请求

`GET /ppt/jobs/{job_id}`

### 响应

```json
{
  "job_id": "job_xxx",
  "status": "running",
  "phase": "generating_slides",
  "progress": 40,
  "message": "正在生成 slides",
  "create_time": "2026-04-08T10:00:00.000Z",
  "updated_time": "2026-04-08T10:00:10.000Z",
  "finished_time": null,
  "latest_revision_id": null,
  "error": null
}
```

### 状态与阶段

- `status`: `queued | running | succeeded | failed`
- `phase`: `accepted | preprocessing | generating_slides | building_full_html | exporting_pptx | storing_artifacts | completed | failed`
- `progress` 默认映射：
  - `accepted` = 0
  - `preprocessing` = 10
  - `generating_slides` = 40
  - `building_full_html` = 70
  - `exporting_pptx` = 90
  - `storing_artifacts` = 95
  - `completed` = 100
  - `failed` = 0

---

## 4.3 获取最新成功结果

### 请求

`GET /ppt/jobs/{job_id}/results`

### 响应

```json
{
  "job_id": "job_xxx",
  "latest_revision_id": "rev_0000",
  "theme_id": "heu_academic_elegant",
  "results": {
    "html_fragment_url": "/ppt/artifacts/job_xxx/rev_0000/deck.fragment.html",
    "html_full_url": "/ppt/artifacts/job_xxx/rev_0000/deck.html",
    "pptx_url": "/ppt/artifacts/job_xxx/rev_0000/deck.pptx",
    "manifest_url": "/ppt/artifacts/job_xxx/rev_0000/manifest.json"
  },
  "slide_count": 10,
  "metadata": {
    "request_id": "req_001",
    "timestamp": "2026-04-08T10:00:00+08:00",
    "idempotency_key": "idem_001",
    "user_id": "u_001",
    "tenant_id": "tenant_a"
  }
}
```

---

## 4.4 创建 revision（单页修订）

### 请求

`POST /ppt/jobs/{job_id}/revisions`

```json
{
  "mode": "single_slide",
  "target_slides": [7],
  "updated_content": "## Slide 7\n- Role: content\n- Title: 新标题\n\n### Blocks\n- Bullets:\n  - 要点A\n  - 要点B\n",
  "user_instruction": "请更学术风格，并提升可读性"
}
```

### 约束

- 当前仅支持 `mode = single_slide`
- `target_slides` 必须且仅能包含 1 个页码
- `updated_content` 和 `user_instruction` 不能同时为空
- 若提供 `updated_content`，必须符合“单页 content 协议”

### 响应

```json
{
  "revision_id": "rev_0001",
  "status": "queued"
}
```

---

## 4.5 查询 revision 状态

### 请求

`GET /ppt/jobs/{job_id}/revisions/{revision_id}`

### 响应

```json
{
  "job_id": "job_xxx",
  "revision_id": "rev_0001",
  "status": "running",
  "phase": "building_full_html",
  "progress": 70,
  "message": "正在重建完整 HTML",
  "create_time": "2026-04-08T10:10:00.000Z",
  "updated_time": "2026-04-08T10:10:12.000Z",
  "finished_time": null,
  "error": null
}
```

---

## 4.6 产物下载与静态资源

- `GET /ppt/artifacts/{job_id}/{revision_id}/{file_name}`
  - `file_name` 仅允许：
    - `deck.fragment.html`
    - `deck.html`
    - `deck.pptx`
    - `manifest.json`
- `GET /ppt/artifacts/{job_id}/{revision_id}/media/{file_name}`
- `GET /assets/{path}`

---

## 5. 内容协议（输入）整理

`content_markdown` 基本结构：

```md
# Deck
- Title: ...
- Subtitle: ...
- Theme: ...

---

## Slide 1
- Role: cover
- Title: ...

### Blocks
- Lead: ...

### Notes
...
```

核心规则：

- `Role` 允许值：
  - `cover`
  - `toc`
  - `section`
  - `content`
  - `thanks`
- `### Blocks` 必须存在。
- 每页最多一个 `Media` block。
- 媒体类型：
  - 图像：`png/jpg/jpeg/webp/svg`
  - 视频：`mp4/webm/mov`
- 支持远程 URL 和仓库内相对路径（如 `assets/test/1.jpg`）。
- 运行时会注入：
  - `Local-Path`
  - `Local-Poster-Path`（视频可选）

---

## 6. 输出产物（文件系统）整理

目录结构：

```text
data/jobs/<job_id>/
├── request.json
├── job.json
└── revisions/
    └── rev_0000/
        ├── revision.json
        ├── agent-prompt.txt
        ├── content.md
        ├── deck.fragment.html
        ├── deck.html
        ├── deck.pptx
        ├── manifest.json
        ├── export-debug-dom.html
        ├── export-debug-log.json
        └── media/
```

对接建议：

- 你的系统对外只消费 API 返回 URL，不直接依赖本地路径。
- 排障时可保留 debug 文件；上线后可按策略清理。

---

## 7. 样式与版式示例

## 7.1 主题与品牌位示例

`style/theme-brand-config.json` 示例要点：

```json
{
  "themes": {
    "theme-heu-academic-elegant.css": {
      "brand": {
        "enabled": true,
        "asset": "/assets/HEU/heu-logo.png",
        "position": "top-right",
        "slotClass": "slide-brand",
        "imageClass": "slide-brand-image"
      }
    }
  }
}
```

品牌位片段（`format/brand-slot-fragment.html`）：

```html
<div class="slide-brand">
  <img class="slide-brand-image" src="{{BRAND_ASSET}}" alt="{{BRAND_ALT}}">
</div>
```

---

## 7.2 常用版式 class 示例

```html
<!-- Cover -->
<div class="slide layout-cover">...</div>

<!-- TOC -->
<div class="slide layout-toc">...</div>

<!-- Section -->
<div class="slide layout-section-break">...</div>

<!-- 标准正文 -->
<div class="slide layout-standard-text">...</div>

<!-- 双栏论证 -->
<div class="slide layout-standard-text-dual-panel">...</div>

<!-- 对比 -->
<div class="slide layout-standard-text-comparison">...</div>

<!-- 流程 -->
<div class="slide layout-standard-text-process">...</div>

<!-- 左图右文 -->
<div class="slide layout-image-text">...</div>

<!-- 左文右图 -->
<div class="slide layout-text-media">...</div>

<!-- 媒体聚焦 -->
<div class="slide layout-media-focus">...</div>

<!-- 致谢 -->
<div class="slide layout-thanks">...</div>
```

---

## 7.3 主题 CSS 变量片段示例

（节选自 `style/theme-heu-academic-elegant.css`）

```css
:root {
  --color-primary: #003366;
  --color-secondary: #0066CC;
  --color-accent: #D97706;
  --bg-canvas: #F8FAFC;
  --bg-surface: #FFFFFF;
}
```

---

## 7.4 内容到版式的映射示例（建议）

- `Role=cover` -> `layout-cover`
- `Role=toc` -> `layout-toc`
- `Role=section` -> `layout-section-break`
- `Role=thanks` -> `layout-thanks`
- `Role=content`：
  - `Cards` -> `card-layout`（通过 `.cards-grid` 特征）
  - `Comparison` -> `layout-standard-text-comparison`
  - `Process` -> `layout-standard-text-process`
  - `Media + Bullets` -> `layout-image-text` / `layout-text-media` / `layout-media-focus`
  - 其他文本 -> `layout-standard-text` 系列

---

## 8. 错误码整理（对接需识别）

常见错误码：

- `INVALID_REQUEST`
- `UNSUPPORTED_THEME_ID`
- `JOB_NOT_FOUND`
- `REVISION_NOT_FOUND`
- `INVALID_REVISION_MODE`
- `INVALID_TARGET_SLIDES`
- `EMPTY_REVISION_INPUT`
- `INVALID_CONTENT_FORMAT`
- `UNSUPPORTED_MEDIA_TYPE`
- `MEDIA_DOWNLOAD_FAILED`
- `AGENT_GENERATION_FAILED`
- `SERVICE_RESTARTED`

建议：

- 你的系统把这些错误码映射成稳定的上层错误语义。
- 对 `AGENT_GENERATION_FAILED`、`MEDIA_DOWNLOAD_FAILED` 做重试策略分层。

---

## 9. 最小联调流程（可直接执行）

1. 启动服务：

```bash
npm install
npm start
```

2. 创建任务：

```bash
curl -s -X POST http://127.0.0.1:46080/ppt/jobs \
  -H "Content-Type: application/json" \
  -d "{\"content_markdown\":\"# Deck\\n- Title: Demo\\n\\n---\\n\\n## Slide 1\\n- Role: cover\\n- Title: Demo\\n\\n### Blocks\\n- Lead: Hello\",\"theme_id\":\"heu_academic_elegant\",\"metadata\":{\"request_id\":\"req_demo\",\"timestamp\":\"2026-04-08T10:00:00+08:00\",\"idempotency_key\":\"idem_demo\",\"user_id\":\"u_demo\"}}"
```

3. 轮询状态：

```bash
curl -s http://127.0.0.1:46080/ppt/jobs/<job_id>
```

4. 获取结果：

```bash
curl -s http://127.0.0.1:46080/ppt/jobs/<job_id>/results
```

5. 打开 `pptx_url` 下载验证。

---

## 10. 接入系统建议（简版）

- 上层编排采用两段式：
  - `create job`（立即返回 `job_id`）
  - `poll + fetch results`（异步拿结果）
- 强制业务侧传入幂等键，避免重复创建 job。
- 你的系统不要耦合内部目录结构；只消费 API URL。
- 先集成主流程，再接 revision，以降低初期复杂度。

{
  "content_markdown": "# Deck\n- Title: TCP 三次握手教学课件\n- Subtitle: 面向大一计算机专业\n- Theme: heu_academic_elegant\n\n---\n\n## Slide 1\n- Role: cover\n- Title: TCP 三次握手\n\n### Blocks\n- Lead: 理解连接建立的基本过程\n- Meta:\n  - 课程：计算机网络\n  - 对象：大一学生\n  - 时间：2026春季学期\n\n### Notes\n这一页用于开场，介绍主题和适用对象。\n\n---\n\n## Slide 2\n- Role: toc\n- Title: 目录\n\n### Blocks\n- Toc:\n  - 为什么需要连接建立\n  - 三次握手的三个步骤\n  - 常见问题与易错点\n\n---\n\n## Slide 3\n- Role: content\n- Title: 三次握手的过程\n\n### Blocks\n- Process:\n  - Step-Title: 第一次握手\n    Step-Text: 客户端发送 SYN，请求建立连接。\n  - Step-Title: 第二次握手\n    Step-Text: 服务端返回 SYN + ACK，表示收到请求并同意连接。\n  - Step-Title: 第三次握手\n    Step-Text: 客户端返回 ACK，连接正式建立。\n\n### Notes\n这里要强调每一步的发送方和报文类型。\n\n---\n\n## Slide 4\n- Role: content\n- Title: 抓包示意图\n\n### Blocks\n- Bullets:\n  - 可以在 Wireshark 中观察 SYN、SYN+ACK、ACK\n  - 注意序列号和确认号的变化\n- Media:\n  - Kind: image\n  - URL: assets/test/1.jpg\n  - Alt: TCP 抓包示意图\n  - Caption: 本地测试图片示例\n\n---\n\n## Slide 5\n- Role: thanks\n- Title: Q&A\n\n### Blocks\n- Lead: 谢谢聆听，欢迎提问\n",
  "theme_id": "heu_academic_elegant",
  "metadata": {
    "request_id": "req_ppt_001",
    "timestamp": "2026-04-08T10:00:00+08:00",
    "idempotency_key": "ppt_demo_001",
    "user_id": "teacher_001",
    "tenant_id": "school_a"
  }
}
