# html2ppt-service

一个基于 Node.js 的 PPT 生成服务。

它接收主系统提供的 `content_markdown`，调用 Claude Code 生成 slide HTML fragment，再自动完成：
- 媒体资源本地化
- 完整 HTML 包装
- PPTX 导出
- job / revision / manifest / 调试产物落盘

当前内部主流程：

`主系统 -> PPT 服务 API -> 任务队列 -> Claude Code -> HTML 构建 -> PPTX 导出 -> 本地产物存储`

---

## Layout Content Quality

生成链路现在把 layout 视为教学表达单元，而不是单纯外观模板。`layout-catalog.json` 与 `component-catalog.json` 增加了紧凑的 teaching recipe、内容容量和 fallback 提示；planner / executor prompt 会优先使用当前页的 focused catalog summary，避免把整份 catalog 都塞进执行上下文。

后处理阶段会写出 `layout-quality-report.json`，其中包含：

- 内容过空的 `CONTENT_DENSITY_LOW`
- 优先级版式关键槽位缺失的 `REQUIRED_SLOT_EMPTY`
- 内容标记缺失、重复文本版式、结构化页过密等既有 warning
- 导出前的轻量几何检查 warning，例如关键容器溢出或元素越出 slide

这套质量链路的目标是：在导出 PPTX 前尽量提前发现“页太空”“槽位没填”“元素超界”这类课堂可讲性问题。

---

## 1. 当前能力

- 异步创建 PPT 任务
- 查询任务状态
- 获取最新成功结果
- 单页 revision
- 纯 Markdown 内容协议解析
- 图片 / 视频本地化
- 品牌位 logo 支持
- 导出失败时保留浏览器调试产物

---

## 2. 目录结构

```text
.
├── assets/                     # 品牌 logo、本地媒体测试文件
├── data/                       # job / revision / 导出产物（本地生成，默认忽略）
├── docs/
│   ├── api/                    # 对主系统的接口草案
│   ├── ops/                    # 部署与迁移说明
│   └── superpowers/            # 设计/计划记录，非运行时依赖
├── dom-to-pptx/                # DOM -> PPTX 导出适配库
├── format/                     # frames / presets / components / layout.css
├── prompts/                    # planner、slide executor、revision executor 提示词
├── references/                 # 内容协议、catalog、导出限制与工作流参考
├── scripts/
│   ├── build-standalone-html.js
│   └── export-html-to-pptx.js
├── src/
│   ├── agents/
│   ├── domain/
│   ├── lib/
│   ├── queue/
│   ├── services/
│   ├── store/
│   └── server.js
├── style/
├── test/
└── test-harness/               # 本地导出调试 harness
```

---

## 3. 运行环境

建议环境：

- Node.js 20+
- Google Chrome
- Claude Code CLI

当前默认 Chrome 路径：

```text
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

---

## 4. 安装依赖

```bash
npm install
```

建议先复制一份环境变量模板：

```bash
cp .env.example .env
```

---

## 5. 启动服务

最常用方式：

```bash
PPT_SERVICE_PORT=46080 \
PPT_CLAUDE_CMD=claude \
PPT_CLAUDE_ARGS='["-p","--output-format","text","--permission-mode","bypassPermissions"]' \
node src/server.js
```

也可以直接：

```bash
npm start
```

但如果没有提前设置 `PPT_CLAUDE_CMD` 和 `PPT_CLAUDE_ARGS`，服务无法真正完成生成任务。

说明：
- 服务当前监听在 `127.0.0.1`，默认不对外网卡开放
- `PPT_CLAUDE_CMD` / `PPT_CLAUDE_ARGS` 是生成链路真正可用的前提
- 如果项目根目录存在 `.env`，服务会在启动时自动加载其中的环境变量

---

## 6. 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `PPT_SERVICE_PORT` | 服务端口 | `4300` |
| `PPT_DATA_DIR` | job / revision / 产物目录 | `<repo>/data` |
| `PPT_WORKER_CONCURRENCY` | 队列并发数 | `1` |
| `PPT_CHROME_PATH` | Chrome 可执行文件路径 | macOS 默认 Chrome 路径 |
| `PPT_CHROME_ARGS` | Chrome 额外参数，JSON 数组或类 shell 字符串 | 空 |
| `PPT_CLAUDE_CMD` | Claude Code 命令 | `claude` |
| `PPT_CLAUDE_ARGS` | Claude Code 参数，JSON 数组或类 shell 字符串 | 空 |
| `PPT_DEFAULT_THEME_ID` | 默认主题 ID | `heu_academic_elegant` |

当前代码内置的主题 ID：
- `heu_academic_elegant`
- `heu_academic_basic`

---

## 7. 内容协议

`content_markdown` 必须遵守纯 Markdown 固定字段协议，详见：

- [references/content-protocol.md](references/content-protocol.md)

核心结构：

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

### 7.1 `Role` 允许值

- `cover`
- `toc`
- `section`
- `content`
- `thanks`

### 7.2 `Blocks` 支持类型

- `Lead`
- `Bullets`
- `Meta`
- `Toc`
- `Cards`
- `Comparison`
- `Process`
- `Media`

### 7.3 `Notes` 是否必须

不是。`### Notes` 整段可以完全省略。

### 7.4 媒体规则

- 每页最多 1 个 `Media` block
- 图片支持：
  - `png`
  - `jpg`
  - `jpeg`
  - `webp`
  - `svg`
- 视频支持：
  - `mp4`
  - `webm`
  - `mov`
- 生产环境推荐使用远程 URL
- 本地联调也允许直接使用仓库内相对路径，例如：
  - `assets/test/1.jpg`
  - `assets/test/2.mp4`

服务会在预处理阶段把媒体下载或复制到当前 revision 的 `media/` 目录，并在运行时内容里补充 `Local-Path` / `Local-Poster-Path`。

---

## 8. API 概览

完整接口草案见：

- [docs/api/ppt-service-api-draft.md](docs/api/ppt-service-api-draft.md)

主要接口：

### 8.1 创建任务

```http
POST /ppt/jobs
```

### 8.2 查询任务状态

```http
GET /ppt/jobs/{job_id}
```

### 8.3 查询最新结果

```http
GET /ppt/jobs/{job_id}/results
```

说明：
- 只返回“当前最新成功版本”的结果
- 如果任务还没有任何成功版本，接口会返回 `409`

### 8.4 创建单页 revision

```http
POST /ppt/jobs/{job_id}/revisions
```

### 8.5 查询 revision 状态

```http
GET /ppt/jobs/{job_id}/revisions/{revision_id}
```

### 8.6 访问产物

```http
GET /ppt/artifacts/{job_id}/{revision_id}/{file_name}
GET /ppt/artifacts/{job_id}/{revision_id}/media/{file_name}
GET /assets/{path}
```

---

## 9. 本地手动联调

### 9.1 用当前 `content.md` 创建任务

```bash
CONTENT_JSON=$(node -e "const fs=require('fs'); process.stdout.write(JSON.stringify({content_markdown:fs.readFileSync('content.md','utf8'),theme_id:'heu_academic_elegant',metadata:{request_id:'req-local-001',timestamp:new Date().toISOString(),idempotency_key:'idem-local-001',user_id:'user-local-test'}}))")

curl -s -X POST http://127.0.0.1:46080/ppt/jobs \
  -H 'Content-Type: application/json' \
  -d "$CONTENT_JSON"
```

### 9.2 轮询任务状态

```bash
curl -s http://127.0.0.1:46080/ppt/jobs/<job_id>
```

### 9.3 读取结果

```bash
curl -s http://127.0.0.1:46080/ppt/jobs/<job_id>/results
```

### 9.4 访问完整 HTML

```text
http://127.0.0.1:46080/ppt/artifacts/<job_id>/<revision_id>/deck.html
```

### 9.5 单独测试导出脚本

```bash
node scripts/export-html-to-pptx.js \
  data/jobs/<job_id>/revisions/<revision_id>/deck.html \
  /tmp/debug-export.pptx
```

---

## 10. Job / Revision 工作目录

每个任务都会落到：

```text
data/jobs/<job_id>/
```

典型结构：

```text
data/jobs/<job_id>/
├── request.json
├── job.json
└── revisions/
    └── rev_0000/
        ├── agent-prompt.txt
        ├── content.md
        ├── deck.fragment.html
        ├── deck.html
        ├── deck.pptx
        ├── manifest.json
        ├── revision.json
        ├── export-debug-dom.html
        ├── export-debug-log.json
        └── media/
```

说明：
- `export-debug-dom.html` 和 `export-debug-log.json` 主要在导出链路执行后生成
- 它们对定位“HTML 能生成，但 PPTX 导出失败”的问题很有帮助
- `rev_0000` 是初次生成版本，后续每次改单会生成新的 `rev_0001`、`rev_0002` 等目录

---

## 11. 导出调试

如果 revision 卡在：

- `phase = exporting_pptx`
- 或 `revision.json` 里出现 `Timed out waiting for PPTX output`

优先检查：

1. `revision.json`
2. `deck.html`
3. `export-debug-dom.html`
4. `export-debug-log.json`

最常用排查命令：

```bash
sed -n '1,240p' data/jobs/<job_id>/revisions/<revision_id>/revision.json
cat data/jobs/<job_id>/revisions/<revision_id>/export-debug-log.json
```

如果要验证同一个 HTML 是否能单独导出，直接运行：

```bash
node scripts/export-html-to-pptx.js \
  data/jobs/<job_id>/revisions/<revision_id>/deck.html \
  /tmp/manual-check.pptx
```

---

## 12. 测试

运行单元测试：

```bash
npm test
```

当前测试覆盖：

- theme registry
- phase / progress 映射
- fragment 提取与替换
- manifest 生成
- 内容协议解析
- 媒体本地化
- 幂等创建
- revision 请求校验

说明：
- 当前测试以单元测试和服务层回归为主
- 真实 Claude Code + Chrome 的端到端联调仍建议在本机手动验证

---

## 13. 当前限制

v1 当前限制：

- 只支持 Claude Code 作为唯一 agent runner
- 只正式支持单页 revision
- 不支持多页 revision 的实际执行
- 不支持数据库与对象存储
- 不支持用户自定义文件名
- 不支持直接修改已有外部 PPTX
- 当前数据全部落在本地文件系统

---

## 14. 相关文档

- [docs/README.md](docs/README.md)
- [docs/api/ppt-service-api-draft.md](docs/api/ppt-service-api-draft.md)
- [docs/ops/migration-to-linux.md](docs/ops/migration-to-linux.md)
- [references/content-protocol.md](references/content-protocol.md)
- [references/layout-catalog.json](references/layout-catalog.json)
- [references/component-catalog.json](references/component-catalog.json)
- [references/html-to-pptx-restrict.md](references/html-to-pptx-restrict.md)
- [prompts/deck-planner.md](prompts/deck-planner.md)
- [prompts/slide-executor.md](prompts/slide-executor.md)
