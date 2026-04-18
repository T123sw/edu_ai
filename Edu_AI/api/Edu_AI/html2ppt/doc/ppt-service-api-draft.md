# PPT 服务 API 接口文档草案 v1

## 1. 文档目标

本文档定义 PPT 服务与主系统之间的接口协议。

本服务负责：
- 接收主系统请求
- 异步生成 PPT 相关产物
- 支持后续“单页自然语言迭代修改”

本服务内部推荐流程：

`主系统 -> PPT 服务 API -> 任务队列 -> Agent Worker -> 构建脚本 -> 导出脚本 -> 产物存储`

---

## 2. 设计原则

- 所有生成与修订操作均为异步任务。
- 主系统不关心内部使用哪种 agent，只关心任务状态与产物结果。
- `results` 接口默认返回“当前最新成功版本”的结果。
- revision 成功后，会重新生成整套产物，而不是只改局部文件。
- v1 只正式支持“单页修改”，但接口保留 `mode` 字段，便于后续扩展多页修改。

---

## 3. 通用约定

### 3.1 基础路径

建议服务基础路径为：

```text
/ppt
```

### 3.1.1 静态产物路由

服务应额外提供一个静态产物访问路由：

```http
GET /ppt/artifacts/{job_id}/{revision_id}/{file_name}
```

其中 `file_name` 在 v1 中固定允许以下值：
- `deck.fragment.html`
- `deck.html`
- `deck.pptx`
- `manifest.json`

对于媒体资源，服务应额外提供：

```http
GET /ppt/artifacts/{job_id}/{revision_id}/media/{file_name}
```

说明：
- 用于加载 `deck.html` 中引用的本地化图片与视频
- 当前 revision 目录下的媒体文件由服务在预处理阶段下载或复制到本地

对于仓库级静态资源，服务还应提供：

```http
GET /assets/{path}
```

说明：
- 用于加载品牌 logo 等仓库静态文件
- 当前主题品牌位配置来自 `style/theme-brand-config.json`

### 3.2 时间格式

所有时间字段统一使用 ISO 8601 字符串，例如：

```text
2026-04-05T10:30:00+08:00
```

### 3.3 ID 生成规则

所有 ID 建议由服务端生成，格式不限，但必须全局唯一。

涉及的 ID 包括：
- `job_id`
- `revision_id`

### 3.4 响应格式

所有接口统一返回 JSON。

---

## 4. 任务状态定义

### 4.1 status 字段

所有任务状态统一使用以下枚举值：

- `queued`
- `running`
- `succeeded`
- `failed`
- `canceled`

说明：
- 当前 v1 实际会返回 `queued / running / succeeded / failed`
- `canceled` 作为保留值存在，当前代码尚未实现取消接口

### 4.2 phase 字段

`phase` 用于描述任务当前执行到哪一步，建议取值如下：

- `accepted`
- `preprocessing`
- `generating_slides`
- `building_full_html`
- `exporting_pptx`
- `storing_artifacts`
- `completed`
- `failed`

### 4.3 progress 字段

`progress` 为 `0` 到 `100` 的整数。

v1 建议采用“阶段映射型进度”，便于实现和前端展示，不强求真实精确百分比。

映射如下：

| phase                | progress |
| -------------------- | -------: |
| `accepted`           |        0 |
| `preprocessing`      |       10 |
| `generating_slides`  |       40 |
| `building_full_html` |       70 |
| `exporting_pptx`     |       90 |
| `storing_artifacts`  |       95 |
| `completed`          |      100 |
| `failed`             |     置 0 |

### 4.4 message 字段

`message` 用于向前端或用户展示简短提示信息。

示例：
- `任务已排队`
- `正在生成 slides`
- `正在构建完整 HTML`
- `正在导出 PPTX`
- `生成失败，请稍后重试`

---

## 5. metadata 字段定义

v1 建议保留以下元信息：

| 字段              | 类型   | 必填 | 说明                                                            |
| ----------------- | ------ | ---: | --------------------------------------------------------------- |
| `request_id`      | string |   是 | 主系统本次请求的唯一标识，便于链路追踪                          |
| `timestamp`       | string |   是 | 主系统发起请求的时间                                            |
| `idempotency_key` | string |   是 | 幂等键，用于防止同一个业务请求被重复执行                        |
| `user_id`         | string |   是 | 发起请求的用户 ID                                               |
| `tenant_id`       | string |   否 | 租户 ID，用于多租户隔离与权限控制；若主系统没有租户概念，可省略 |

### 5.1 idempotency_key 说明

`idempotency_key` 用于防止同一个业务请求因为网络重试、重复点击或系统超时重发，而在服务端被重复创建为两个任务。

典型场景：
- 主系统调用创建任务接口
- 服务端实际上已创建成功
- 但主系统因网络超时没收到响应
- 主系统自动重试一次

如果没有 `idempotency_key`，服务端可能会重复创建两个 job。  
如果有 `idempotency_key`，服务端可以识别“这是同一个请求”，并直接返回第一次创建的结果。

---

## 6. 接口一：创建 PPT 任务

### 6.1 接口定义

```http
POST /ppt/jobs
```

### 6.2 接口说明

用于创建一个新的 PPT 生成任务。

说明：
- `content_markdown` 为主系统提供的全量内容描述
- `theme_id` 为主题标识，服务内部负责映射到具体 CSS
- 文件名由服务内部生成，主系统无需传入
- `content_markdown` 必须遵守项目约定的纯 Markdown 内容协议，详见 `content-protocol.md`
- 服务按 `(tenant_id || "default", idempotency_key)` 做幂等
  - 如果相同幂等键对应的请求摘要一致，则直接返回已有 `job_id`
  - 如果相同幂等键对应的请求摘要不同，则返回 `409`

### 6.3 请求体示例

```json
{
  "content_markdown": "# Deck\n- Title: 示例汇报\n- Theme: heu_academic_elegant\n\n---\n\n## Slide 1\n- Role: cover\n- Title: 示例标题\n\n### Blocks\n- Lead: 示例副标题\n",
  "theme_id": "heu_academic_elegant",
  "metadata": {
    "request_id": "req_20260405_0001",
    "timestamp": "2026-04-05T10:30:00+08:00",
    "idempotency_key": "idem_20260405_0001",
    "user_id": "user_123",
    "tenant_id": "tenant_a"
  }
}
```

### 6.4 请求字段说明

| 字段                       | 类型   | 必填 | 说明                                  |
| -------------------------- | ------ | ---: | ------------------------------------- |
| `content_markdown`         | string |   是 | 主系统提供的 PPT 全量内容描述         |
| `theme_id`                 | string |   是 | 主题 ID，由服务内部映射到 CSS         |
| `metadata`                 | object |   是 | 请求元信息                            |
| `metadata.request_id`      | string |   是 | 主系统请求 ID                         |
| `metadata.timestamp`       | string |   是 | 请求时间                              |
| `metadata.idempotency_key` | string |   是 | 幂等键                                |
| `metadata.user_id`         | string |   是 | 用户 ID                               |
| `metadata.tenant_id`       | string |   否 | 租户 ID；若主系统没有租户概念，可省略 |

### 6.5 成功响应示例

```json
{
  "job_id": "job_20260405_0001",
  "status": "queued"
}
```

### 6.6 响应字段说明

| 字段     | 类型   | 说明                      |
| -------- | ------ | ------------------------- |
| `job_id` | string | 任务 ID                   |
| `status` | string | 初始状态，固定为 `queued` |

---

## 7. 接口二：查询任务状态

### 7.1 接口定义

```http
GET /ppt/jobs/{job_id}
```

### 7.2 接口说明

用于查询 PPT 生成任务的当前状态。

说明：
- `updated_time` 表示该任务最近一次状态变化时间
- `message` 是给前端或用户展示的简短提示信息

### 7.3 成功响应示例

```json
{
  "job_id": "job_20260405_0001",
  "status": "running",
  "phase": "generating_slides",
  "progress": 40,
  "message": "正在生成 slides",
  "create_time": "2026-04-05T10:30:00+08:00",
  "updated_time": "2026-04-05T10:31:15+08:00",
  "finished_time": null,
  "latest_revision_id": null,
  "error": null
}
```

### 7.4 响应字段说明

| 字段                 | 类型        | 说明                                |
| -------------------- | ----------- | ----------------------------------- |
| `job_id`             | string      | 任务 ID                             |
| `status`             | string      | 任务状态                            |
| `phase`              | string      | 当前执行阶段                        |
| `progress`           | integer     | 任务进度，0 到 100                  |
| `message`            | string      | 展示给用户的提示信息                |
| `create_time`        | string      | 任务创建时间                        |
| `updated_time`       | string      | 最近一次状态更新时间                |
| `finished_time`      | string/null | 完成时间，未完成时为 null           |
| `latest_revision_id` | string/null | 当前最新 revision ID，没有则为 null |
| `error`              | object/null | 错误信息，成功时为 null             |

### 7.5 error 字段示例

```json
{
  "code": "AGENT_GENERATION_FAILED",
  "message": "Agent 生成 slides 失败"
}
```

---

## 8. 接口三：获取任务结果

### 8.1 接口定义

```http
GET /ppt/jobs/{job_id}/results
```

### 8.2 接口说明

默认返回该任务“当前最新成功版本”的结果。

说明：
- 如果后续存在 revision，则返回最新 revision 对应的结果
- `manifest_url` 为内部结构清单，便于后续改单、调试和扩展
- `results` 中的 URL 在 v1 中可以返回服务内相对路径，例如 `/ppt/artifacts/...`
- `html_full_url` 在浏览器渲染时，可能还会继续请求：
  - `/ppt/artifacts/{job_id}/{revision_id}/media/...`
  - `/assets/...`
- 如果该任务还没有任何成功版本，接口返回 `409`

### 8.3 成功响应示例

```json
{
  "job_id": "job_20260405_0001",
  "latest_revision_id": "rev_0002",
  "theme_id": "heu_academic_elegant",
  "results": {
    "html_fragment_url": "/ppt/artifacts/job_20260405_0001/rev_0002/deck.fragment.html",
    "html_full_url": "/ppt/artifacts/job_20260405_0001/rev_0002/deck.html",
    "pptx_url": "/ppt/artifacts/job_20260405_0001/rev_0002/deck.pptx",
    "manifest_url": "/ppt/artifacts/job_20260405_0001/rev_0002/manifest.json"
  },
  "slide_count": 19,
  "metadata": {
    "request_id": "req_20260405_0001",
    "timestamp": "2026-04-05T10:30:00+08:00",
    "idempotency_key": "idem_20260405_0001",
    "user_id": "user_123",
    "tenant_id": "tenant_a"
  }
}
```

### 8.4 响应字段说明

| 字段                        | 类型        | 说明                    |
| --------------------------- | ----------- | ----------------------- |
| `job_id`                    | string      | 任务 ID                 |
| `latest_revision_id`        | string/null | 最新 revision ID        |
| `theme_id`                  | string      | 当前版本使用的主题 ID   |
| `results.html_fragment_url` | string      | slide fragment 产物地址 |
| `results.html_full_url`     | string      | 完整 HTML 产物地址      |
| `results.pptx_url`          | string      | PPTX 产物地址           |
| `results.manifest_url`      | string      | manifest 产物地址       |
| `slide_count`               | integer     | 当前 deck 总页数        |
| `metadata`                  | object      | 创建任务时的元信息回显  |

---

## 9. 接口四：发起修订任务

### 9.1 接口定义

```http
POST /ppt/jobs/{job_id}/revisions
```

### 9.2 接口说明

用于创建一个 revision 任务。

说明：
- v1 正式支持 `single_slide`
- `target_slides` 统一使用数组表示
- `updated_content` 和 `user_instruction` 可以二选一，也可以同时传，但不能同时为空
- `updated_content` 表示“目标页的完整新内容”，不是 patch
- 如果传入 `updated_content`，它必须遵守与 `content_markdown` 相同的内容协议，但只允许包含单个 `## Slide N` 块

### 9.3 请求体示例

```json
{
  "mode": "single_slide",
  "target_slides": [7],
  "updated_content": "## Slide 7\n- Role: content\n- Title: 视觉离散化：VQ 与密码本机制\n\n### Blocks\n- Bullets:\n  - 连续特征提取后，在 Codebook 中寻找最相似向量\n  - 索引结果即为一个 Visual Token\n",
  "user_instruction": "这页太拥挤了，保留信息但换一种更清晰、更学术的版式"
}
```

### 9.4 请求字段说明

| 字段               | 类型       | 必填 | 说明                                   |
| ------------------ | ---------- | ---: | -------------------------------------- |
| `mode`             | string     |   是 | 修订模式，v1 建议仅支持 `single_slide` |
| `target_slides`    | array<int> |   是 | 目标页码列表                           |
| `updated_content`  | string     |   否 | 目标页的完整新内容                     |
| `user_instruction` | string     |   否 | 用户对表达或版式优化的自然语言要求     |

### 9.5 约束规则

- `mode = single_slide` 时，`target_slides` 长度必须等于 1
- `updated_content` 和 `user_instruction` 不能同时为空

### 9.6 成功响应示例

```json
{
  "revision_id": "rev_0003",
  "status": "queued"
}
```

### 9.7 响应字段说明

| 字段          | 类型   | 说明                      |
| ------------- | ------ | ------------------------- |
| `revision_id` | string | 修订任务 ID               |
| `status`      | string | 初始状态，固定为 `queued` |

---

## 10. 接口五：查询修订任务状态

### 10.1 接口定义

```http
GET /ppt/jobs/{job_id}/revisions/{revision_id}
```

### 10.2 接口说明

用于查询某一次修订任务的执行状态。

说明：
- 字段结构尽量与任务状态接口保持一致，便于前端复用

### 10.3 成功响应示例

```json
{
  "job_id": "job_20260405_0001",
  "revision_id": "rev_0003",
  "status": "running",
  "phase": "building_full_html",
  "progress": 70,
  "message": "正在重建完整 HTML",
  "create_time": "2026-04-05T11:00:00+08:00",
  "updated_time": "2026-04-05T11:01:10+08:00",
  "finished_time": null,
  "error": null
}
```

### 10.4 响应字段说明

| 字段            | 类型        | 说明                      |
| --------------- | ----------- | ------------------------- |
| `job_id`        | string      | 所属任务 ID               |
| `revision_id`   | string      | 修订任务 ID               |
| `status`        | string      | 修订状态                  |
| `phase`         | string      | 当前执行阶段              |
| `progress`      | integer     | 进度，0 到 100            |
| `message`       | string      | 展示给用户的提示信息      |
| `create_time`   | string      | 修订任务创建时间          |
| `updated_time`  | string      | 最近一次状态更新时间      |
| `finished_time` | string/null | 完成时间，未完成时为 null |
| `error`         | object/null | 错误信息，成功时为 null   |

---

## 11. revision 内部处理规则

v1 建议按以下逻辑执行：

1. 读取当前最新成功版本的 deck 产物
2. 定位 `target_slides` 对应页面
3. 把以下内容提供给 LLM：
   - 原页面 fragment
   - 原页面标题与推断出的 layout
   - `updated_content`
   - `user_instruction`
   - `layout-contracts.md`
   - 品牌配置
   - 当前主题信息
   - 上下文页信息（上一页 / 下一页的标题与 layout）
   - 如果存在媒体，则优先使用本地化后的 `Local-Path` / `Local-Poster-Path`
4. 重新生成目标页 fragment
5. 用新 fragment 替换旧 fragment
6. 重新构建新的 `html_fragment`
7. 重新包装新的 `html_full`
8. 重新导出新的 `pptx`
9. 重新生成新的 `manifest`
10. 将这次修订记为新的 revision，并更新 `latest_revision_id`

---

## 12. manifest 的作用说明

manifest 不是用户主产物，但建议始终生成并保存。

manifest 主要用于：
- 记录当前 deck 的页结构
- 标记每页标题和 layout
- 辅助单页修改定位
- 辅助调试与回滚
- 为未来多页修改、缩略图索引等能力做准备

当前实现中，revision 目录还可能包含以下内部调试文件：
- `agent-prompt.txt`
- `content.md`
- `export-debug-dom.html`
- `export-debug-log.json`

说明：
- 这些文件不属于对外 API 产物，但对排查导出失败非常有帮助

### 12.1 manifest 示例

```json
{
  "job_id": "job_20260405_0001",
  "latest_revision_id": "rev_0002",
  "theme_id": "heu_academic_elegant",
  "slide_count": 19,
  "slides": [
    { "slide_index": 1, "title": "封面", "layout": "cover" },
    { "slide_index": 2, "title": "目录", "layout": "toc" },
    { "slide_index": 3, "title": "架构拓扑的演进", "layout": "card-layout" }
  ]
}
```

---

## 13. 常见错误码建议

| 错误码                    | 说明                                                   |
| ------------------------- | ------------------------------------------------------ |
| `INVALID_REQUEST`         | 请求参数不合法                                         |
| `UNSUPPORTED_THEME_ID`    | 不支持的主题 ID                                        |
| `JOB_NOT_FOUND`           | 任务不存在                                             |
| `REVISION_NOT_FOUND`      | revision 不存在                                        |
| `INVALID_REVISION_MODE`   | 不支持的 revision 模式                                 |
| `INVALID_TARGET_SLIDES`   | 目标页码非法                                           |
| `EMPTY_REVISION_INPUT`    | `updated_content` 和 `user_instruction` 同时为空       |
| `INVALID_CONTENT_FORMAT`  | `content_markdown` 或 `updated_content` 不符合内容协议 |
| `UNSUPPORTED_MEDIA_TYPE`  | 不支持的图片或视频格式                                 |
| `MEDIA_DOWNLOAD_FAILED`   | 媒体下载或本地化失败                                   |
| `AGENT_GENERATION_FAILED` | Agent 生成失败                                         |
| `SERVICE_RESTARTED`       | 服务重启导致运行中任务中断                             |

---

## 14. v1 范围边界

### 14.1 v1 明确支持

- 新建 PPT 任务
- 查询任务状态
- 获取最新结果
- 单页修订
- 查询修订状态

### 14.2 v1 暂不支持

- 多页修订的实际执行
- 自动增删页
- 整体重排 deck
- 直接修改已有外部 PPTX
- 用户自定义文件名
- `source_doc_id`
