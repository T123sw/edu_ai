# 本地到服务器迁移文档

本文档用于指导将当前 `html2ppt-service` 从本地 macOS 开发环境迁移到 Linux 服务器环境。

目标是保证以下能力在服务器上可用：
- PPT 服务 API 正常启动
- Claude Code 可被服务调用
- Chrome / Chromium 可完成 HTML -> PPTX 导出
- 图片、视频、品牌 logo 等静态资源可正常访问
- `job / revision / artifact / manifest` 能落盘

如果你是第一次接触这个项目，建议按下面顺序阅读：

1. 先看本文档，完成环境准备与部署
2. 再看接口文档：[ppt-service-api-draft.md](ppt-service-api-draft.md)
3. 再看内容协议：[content-protocol.md](../content-protocol.md)
4. 如果需要理解版式选择，再看：[layout-contracts.md](../layout-contracts.md)

---

## 1. 当前项目运行方式概览

项目当前的核心运行链路是：

`主系统 -> PPT 服务 API -> 任务队列 -> Claude Code -> HTML 构建 -> PPTX 导出 -> 本地产物存储`

关键模块：
- 服务入口：[src/server.js](../src/server.js)
- 配置加载：[src/config.js](../src/config.js)
- 任务编排：[src/services/ppt-service.js](../src/services/ppt-service.js)
- Agent Runner：[src/agents/claude-code-runner.js](../src/agents/claude-code-runner.js)
- HTML 构建：[src/lib/build-standalone-html.js](../src/lib/build-standalone-html.js)
- PPTX 导出：[src/lib/export-html-to-pptx.js](../src/lib/export-html-to-pptx.js)
- 内容协议：[content-protocol.md](../content-protocol.md)

### 1.1 对外如何“使用”这个项目

这个项目本质上是一个本机 HTTP 服务。  
它启动后，主系统或运维人员主要通过以下 5 类接口和它交互：

- `POST /ppt/jobs`
  创建一个新的 PPT 生成任务

- `GET /ppt/jobs/{job_id}`
  查询任务状态

- `GET /ppt/jobs/{job_id}/results`
  获取最新成功版本的结果

- `POST /ppt/jobs/{job_id}/revisions`
  发起单页修订任务

- `GET /ppt/jobs/{job_id}/revisions/{revision_id}`
  查询某次修订任务状态

完整字段、示例和错误码，见：
- [ppt-service-api-draft.md](ppt-service-api-draft.md)

---

## 2. 迁移前要明确的差异

从 macOS 迁移到 Linux，最重要的差异主要有 5 类：

### 2.1 Chrome 路径不同

macOS 默认值是：

```text
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

Linux 上常见路径可能是：

```text
/usr/bin/google-chrome
/usr/bin/chromium
/usr/bin/chromium-browser
```

所以 Linux 上必须明确设置：
- `PPT_CHROME_PATH`

如果服务器环境比较严格，还可能需要额外参数：
- `--no-sandbox`
- `--disable-dev-shm-usage`

所以迁移时建议同时设置：
- `PPT_CHROME_ARGS`

### 2.2 Claude Code 路径不同

本地之前常用的是类似：

```text
/Users/xxx/.local/bin/claude
```

Linux 上通常会变成：

```text
/usr/local/bin/claude
```

或者可以直接放到 `PATH` 里，用：

```text
claude
```

所以 Linux 上要明确设置：
- `PPT_CLAUDE_CMD`
- `PPT_CLAUDE_ARGS`

### 2.3 数据目录不应继续放在代码仓库里

当前默认数据目录是：

```text
<repo>/data
```

Linux 服务器上建议显式指定独立数据目录，例如：

```text
/data/html2ppt
/var/lib/html2ppt
```

所以建议设置：
- `PPT_DATA_DIR`

### 2.4 服务默认监听 `127.0.0.1`

当前服务启动时监听：

```text
127.0.0.1
```

这意味着：
- 只能本机访问
- 不直接暴露到外部网络

### 2.5 静态资源和媒体依赖本地文件系统

项目会依赖：
- 仓库中的 `assets/`
- `style/theme-brand-config.json`
- revision 目录下的 `media/`
- `test-harness/runner.js`
- `test-harness/dom-to-pptx.bundle.js`

所以迁移时必须保证：
- 项目目录结构完整
- 运行用户对数据目录可读写
- 代码仓库不要缺少 `assets/` 和 `test-harness/`

### 2.6 项目是“有状态服务”，不是单纯脚本

这点很重要。

服务运行时会持续写入：
- `request.json`
- `job.json`
- `revision.json`
- `deck.fragment.html`
- `deck.html`
- `deck.pptx`
- `manifest.json`
- `media/`
- 导出调试文件

因此迁移时必须把它当成一个**长期运行的有状态服务**来部署，而不是只把某个脚本拷上去执行一下。

---

## 3. 迁移前代码侧已完成的适配

目前代码里已经做了这些适配，迁移时可以直接使用：

### 3.1 入口 prompt 已改为运行时占位符

[html-generation-entry-prompt.md](../html-generation-entry-prompt.md) 现在使用的是：
- `{{CONTENT_PATH}}`
- `{{FORMAT_DIR}}`
- `{{THEME_CSS_PATH}}`
- `{{LAYOUT_CONTRACTS_PATH}}`

服务启动任务时会把这些占位符替换为当前 revision 的真实路径；旧版 prompt 中的 macOS 绝对路径仍会被兼容替换。

### 3.2 增加了 `.env` 自动加载

[src/config.js](../src/config.js) 现在会在服务启动时自动读取项目根目录下的 `.env`。

优先级规则：
- 如果某个环境变量已经在 shell 中设置，优先使用 shell 值
- 否则从 `.env` 中读取

### 3.3 增加了 `PPT_CHROME_ARGS`

[src/lib/export-html-to-pptx.js](../src/lib/export-html-to-pptx.js) 已经支持额外传入 Chrome 参数。

这对 Linux / Docker 环境非常重要。

### 3.4 提供了 `.env.example`

模板文件：
- [\.env.example](../.env.example)

建议迁移时先复制：

```bash
cp .env.example .env
```

然后按服务器环境修改。

### 3.5 Prompt 不再依赖 macOS 绝对路径

入口 prompt：
- [html-generation-entry-prompt.md](../html-generation-entry-prompt.md)

现在已经改成运行时占位符写法，所以 Linux 上不需要手工把 `/Users/...` 替换成别的目录。

---

## 4. 服务器环境准备

以下步骤以常见 Linux 服务器为例。

### 4.1 准备 Node.js

建议安装：
- Node.js 20+

检查版本：

```bash
node -v
npm -v
```

### 4.2 准备 Chrome 或 Chromium

需要安装一个可执行的 headless 浏览器：
- Google Chrome
- Chromium

安装后检查：

```bash
which google-chrome
which chromium
which chromium-browser
```

至少其中一个命令要能找到可执行文件。

### 4.3 准备 Claude Code CLI

服务器上必须已经安装好 Claude Code CLI，并且当前运行用户可以直接执行它。

检查：

```bash
which claude
claude --help
```

如果 `claude` 不在系统 `PATH` 中，则需要记下它的完整路径，后面写入：
- `PPT_CLAUDE_CMD`

建议额外验证一次“服务用户是否真的能调起 Claude”：

```bash
sudo -u <运行用户> which claude
sudo -u <运行用户> claude --help
```

如果这里失败，即使 root 能调用，服务真正启动后也仍然会失败。

### 4.4 创建运行用户

建议为服务创建专门用户，例如：

```bash
sudo useradd -r -s /bin/bash html2ppt
```

也可以使用已有业务用户，只要满足：
- 能执行 Node
- 能执行 Chrome
- 能执行 Claude
- 对数据目录有写权限

### 4.5 规划项目目录与数据目录

建议目录：

```text
/opt/html2ppt         # 代码目录
/data/html2ppt        # 数据目录
```

创建数据目录：

```bash
sudo mkdir -p /data/html2ppt
sudo chown -R <运行用户>:<运行组> /data/html2ppt
```

### 4.6 部署前自检清单

在开始安装依赖前，建议先把下面这些命令都跑通：

```bash
node -v
npm -v
which claude
which google-chrome || which chromium || which chromium-browser
ls -ld /opt/html2ppt
ls -ld /data/html2ppt
```

你至少要确认：
- Node 可用
- Claude 可用
- Chrome/Chromium 可用
- 代码目录存在
- 数据目录存在并可写

---

## 5. 上传代码并安装依赖

### 5.1 上传代码

把项目代码放到服务器，例如：

```text
/opt/html2ppt
```

进入目录：

```bash
cd /opt/html2ppt
```

### 5.2 安装依赖

```bash
npm install
```

### 5.3 运行单元测试

```bash
npm test
```

如果测试全部通过，说明：
- 基础依赖正常
- 服务层核心逻辑可用
- 本地内容协议和媒体处理逻辑可工作

### 5.4 检查关键目录是否齐全

安装完成后，建议再确认以下目录和文件都在：

```bash
ls assets
ls format
ls style
ls test-harness
ls src
```

重点确认：
- `assets/`
- `format/`
- `style/`
- `test-harness/runner.js`
- `test-harness/dom-to-pptx.bundle.js`

因为导出链路会依赖它们。

---

## 6. 配置环境变量

### 6.1 复制模板

```bash
cp .env.example .env
```

### 6.2 Linux 推荐配置示例

下面是一份更适合 Linux 服务器的 `.env` 示例：

```dotenv
# 服务端口
PPT_SERVICE_PORT=46080

# 数据目录
PPT_DATA_DIR=/data/html2ppt

# 队列并发数
PPT_WORKER_CONCURRENCY=1

# Chrome 路径
PPT_CHROME_PATH=/usr/bin/google-chrome

# Linux / Docker 常见附加参数
PPT_CHROME_ARGS=["--no-sandbox","--disable-dev-shm-usage"]

# Claude Code CLI
PPT_CLAUDE_CMD=/usr/local/bin/claude
PPT_CLAUDE_ARGS=["-p","--output-format","text","--permission-mode","bypassPermissions"]

# 默认主题
PPT_DEFAULT_THEME_ID=heu_academic_elegant
```

如果服务器用的是 Chromium，可改成：

```dotenv
PPT_CHROME_PATH=/usr/bin/chromium
```

### 6.3 环境变量说明

| 变量                     | 作用             | Linux 迁移建议           |
| ------------------------ | ---------------- | ------------------------ |
| `PPT_SERVICE_PORT`       | 服务端口         | 建议显式设置             |
| `PPT_DATA_DIR`           | 任务与产物目录   | 建议改到独立数据盘       |
| `PPT_WORKER_CONCURRENCY` | 队列并发数       | 初期建议仍为 `1`         |
| `PPT_CHROME_PATH`        | 浏览器可执行文件 | 必须按服务器实际路径设置 |
| `PPT_CHROME_ARGS`        | 浏览器附加参数   | Linux 上建议设置         |
| `PPT_CLAUDE_CMD`         | Claude Code 命令 | 必须按服务器实际路径设置 |
| `PPT_CLAUDE_ARGS`        | Claude Code 参数 | 建议沿用当前默认值       |
| `PPT_DEFAULT_THEME_ID`   | 默认主题         | 通常不用改               |

### 6.4 `.env` 与 shell 环境变量的优先级

当前项目的优先级是：

1. 如果某个变量已经在 shell 中设置，优先使用 shell 值
2. 否则读取项目根目录的 `.env`
3. 如果两者都没有，则使用代码默认值

所以推荐做法是：
- 服务器部署时，把常驻配置放进 `.env`
- 临时调试时，再用 shell 覆盖某个变量

---

## 7. 启动服务

### 7.1 前台启动

如果只是先验证：

```bash
cd /opt/html2ppt
npm start
```

或者：

```bash
cd /opt/html2ppt
node src/server.js
```

### 7.2 启动后预期输出

启动成功后应看到：

```text
PPT service listening on http://127.0.0.1:46080
```

说明：
- 当前服务只监听 `127.0.0.1`
- 如果你们使用 Nginx 或其他反向代理，这是正常的

### 7.3 如何确认服务真的在运行

启动后，建议立刻做两步检查：

1. 看进程：

```bash
ps aux | grep 'node src/server.js' | grep -v grep
```

2. 看接口：

```bash
curl -s http://127.0.0.1:46080/ppt/jobs/nonexistent
```

如果接口能返回 JSON 错误而不是连接失败，说明服务已经监听成功。

---

## 8. 基础联调检查

### 8.1 检查服务存活

```bash
curl -s http://127.0.0.1:46080/ppt/jobs/nonexistent
```

如果服务正常，应返回一个 JSON 错误，而不是连接失败。

### 8.2 检查静态资源

品牌 logo 路由：

```bash
curl -I http://127.0.0.1:46080/assets/HEU/heu-logo.png
```

如果返回 `200`，说明：
- 仓库 `assets/` 可访问
- 品牌资源路由正常

### 8.3 检查内容协议联调

可以直接使用仓库里的 `content.md` 发一个任务。

示例：

```bash
CONTENT_JSON=$(node -e "const fs=require('fs'); process.stdout.write(JSON.stringify({content_markdown:fs.readFileSync('content.md','utf8'),theme_id:'heu_academic_elegant',metadata:{request_id:'req-linux-001',timestamp:new Date().toISOString(),idempotency_key:'idem-linux-001',user_id:'user-linux-test'}}))")

curl -s -X POST http://127.0.0.1:46080/ppt/jobs \
  -H 'Content-Type: application/json' \
  -d \"$CONTENT_JSON\"
```

如果主系统还没接入，这就是最推荐的最小自测方式。

### 8.3.1 为什么这里直接用 `content.md`

因为当前项目要求 `content_markdown` 必须符合：
- [content-protocol.md](../content-protocol.md)

所以直接拿仓库里当前可用的 `content.md` 来发请求，是最快的服务器自测方法。

### 8.4 轮询状态

```bash
curl -s http://127.0.0.1:46080/ppt/jobs/<job_id>
```

### 8.5 获取结果

```bash
curl -s http://127.0.0.1:46080/ppt/jobs/<job_id>/results
```

### 8.6 检查产物

本地结果文件会落到：

```text
/data/html2ppt/jobs/<job_id>/revisions/rev_0000/
```

通常应包含：
- `content.md`
- `agent-prompt.txt`
- `deck.fragment.html`
- `deck.html`
- `deck.pptx`
- `manifest.json`
- `revision.json`
- `media/`

### 8.7 如何在浏览器里预览 HTML

如果服务已经正常返回结果，你可以直接打开：

```text
http://127.0.0.1:46080/ppt/artifacts/<job_id>/<revision_id>/deck.html
```

这个页面会继续请求：
- `/ppt/artifacts/<job_id>/<revision_id>/media/...`
- `/assets/...`

所以它也能顺便验证：
- logo 是否能显示
- 图片/视频是否能加载

### 8.8 如何理解结果接口返回的几个 URL

`GET /ppt/jobs/{job_id}/results` 返回的几个主要结果：

- `html_fragment_url`
  只包含 slide fragment，不是完整 HTML 页面

- `html_full_url`
  已经嵌好 CSS、可直接预览和导出的完整 HTML

- `pptx_url`
  最终导出的 PPT 文件

- `manifest_url`
  当前 deck 的结构清单，便于调试和单页 revision

如果你不确定怎么用它们，优先看：
- [ppt-service-api-draft.md](ppt-service-api-draft.md)

---

## 9. 生产部署建议

推荐方式：
- 服务继续监听 `127.0.0.1`
- 使用 `systemd` 保活
- 外部通过 Nginx 反向代理访问

### 9.1 使用 systemd

示例 service 文件：

```ini
[Unit]
Description=html2ppt service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/html2ppt
ExecStart=/usr/bin/node /opt/html2ppt/src/server.js
Restart=always
RestartSec=5
User=html2ppt
Group=html2ppt
Environment=PPT_SERVICE_PORT=46080
Environment=PPT_DATA_DIR=/data/html2ppt
Environment=PPT_WORKER_CONCURRENCY=1
Environment=PPT_CHROME_PATH=/usr/bin/google-chrome
Environment=PPT_CHROME_ARGS=["--no-sandbox","--disable-dev-shm-usage"]
Environment=PPT_CLAUDE_CMD=/usr/local/bin/claude
Environment=PPT_CLAUDE_ARGS=["-p","--output-format","text","--permission-mode","bypassPermissions"]
Environment=PPT_DEFAULT_THEME_ID=heu_academic_elegant

[Install]
WantedBy=multi-user.target
```

然后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl enable html2ppt
sudo systemctl start html2ppt
sudo systemctl status html2ppt
```

### 9.2 使用 Nginx 反向代理

如果主系统需要通过 HTTP 访问，可以让 Nginx 转发到本机服务：

```nginx
server {
    listen 80;
    server_name your-server-domain;

    location / {
        proxy_pass http://127.0.0.1:46080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

这样服务本身仍然只监听本机，不直接暴露。

### 9.3 当前阶段到底需不需要 Nginx

结合当前项目实际情况：

- 如果主系统与 PPT 服务在同一台机器上
- 而且只是本机内部通过 HTTP 调用

那么当前阶段**可以完全不加 Nginx**。

只有在下面这些场景，才更建议挂 Nginx：
- 需要对外提供域名
- 需要 HTTPS
- 需要统一入口
- 需要更强的日志、限流、鉴权、转发能力

所以，是否需要 Nginx，不是这个项目本身决定的，而是你们的部署拓扑决定的。

---

## 10. 导出相关的 Linux 注意事项

Linux 上最容易出问题的是 Chrome 导出链路。

### 10.1 常见现象

如果 revision 卡在：
- `phase = exporting_pptx`

或者 `revision.json` 中出现类似：

```text
Timed out waiting for PPTX output
```

通常优先检查：

1. Chrome 路径是否正确
2. Chrome 是否能被当前用户执行
3. 是否需要 `--no-sandbox`
4. 是否需要 `--disable-dev-shm-usage`
5. 服务器字体、系统资源是否不足

### 10.2 调试文件

导出阶段会写调试文件到 revision 目录：
- `export-debug-dom.html`
- `export-debug-log.json`

先看：

```bash
cat /data/html2ppt/jobs/<job_id>/revisions/<revision_id>/export-debug-log.json
```

### 10.3 单独验证同一份 HTML 能否导出

如果你想排除“服务问题”和“HTML 本身问题”的差异，可以直接用独立脚本：

```bash
node scripts/export-html-to-pptx.js \
  /data/html2ppt/jobs/<job_id>/revisions/<revision_id>/deck.html \
  /tmp/manual-check.pptx
```

如果这个命令能成功，通常说明：
- HTML 本身可导出
- 更可能是服务运行时或当次 Chrome 执行状态的问题

### 10.4 Linux 上最常见的导出参数

很多 Linux 服务器，尤其是容器环境，推荐先尝试：

```dotenv
PPT_CHROME_ARGS=["--no-sandbox","--disable-dev-shm-usage"]
```

如果不加这些参数，Chrome 在 headless 模式下有时会：
- 直接启动失败
- 导出超时
- 卡在浏览器内部状态

---

## 11. 服务器迁移后的常见问题

### 11.1 服务能启动，但生成失败

优先检查：
- `PPT_CLAUDE_CMD` 是否正确
- `claude` 是否可执行
- 当前运行用户是否有 Claude 所需权限

### 11.2 HTML 能生成，但 PPTX 导出失败

优先检查：
- `PPT_CHROME_PATH`
- `PPT_CHROME_ARGS`
- `export-debug-log.json`

### 11.3 logo / 图片 / 视频不显示

优先检查：
- `/assets/...` 是否能访问
- revision 下 `media/` 是否存在对应文件
- `deck.html` 里引用的是不是本地相对路径

### 11.4 服务器上任务目录没有写进去

优先检查：
- `PPT_DATA_DIR` 是否存在
- 运行用户是否有写权限

### 11.5 接口调通了，但不知道下一步怎么用

这时建议按下面顺序看文档：

1. 接口定义：
   - [ppt-service-api-draft.md](ppt-service-api-draft.md)

2. 请求体里的 `content_markdown` 应该怎么写：
   - [content-protocol.md](../content-protocol.md)

3. 如果想理解为什么某页会选某种版式：
   - [layout-contracts.md](../layout-contracts.md)

---

## 12. 建议的最终迁移顺序

推荐按这个顺序执行：

1. 在 Linux 上安装 Node、Chrome、Claude
2. 上传代码到服务器
3. 执行 `npm install`
4. 复制 `.env.example` 为 `.env`
5. 设置 Linux 上真实的 `PPT_CHROME_PATH`、`PPT_CHROME_ARGS`、`PPT_CLAUDE_CMD`
6. 运行 `npm test`
7. 前台启动服务，先本机 `curl` 测接口
8. 用仓库里的 `content.md` 跑一遍真实任务
9. 确认 `deck.html`、`deck.pptx`、`manifest.json` 都能生成
10. 再接入 `systemd`
11. 最后再挂 Nginx 给主系统访问

---

## 13. 当前建议

如果你们下一步真的准备上 Linux，我建议优先这样做：

1. 先在一台 Linux 测试机上前台跑通
2. 先不要急着接 Nginx 和主系统
3. 先验证：
   - Claude 调用
   - HTML 生成
   - PPTX 导出
   - 图片/视频/品牌位资源访问
4. 这些都稳了之后，再上常驻部署

这样排查成本最低。

---

## 14. 给新接手同学的最短路径

如果一个对项目不熟的人第一次拿到仓库，建议直接照下面做：

1. 阅读本文档：[migration_doc.md](migration_doc.md)
2. 复制配置模板：

```bash
cp .env.example .env
```

3. 修改 `.env` 中的：
   - `PPT_CHROME_PATH`
   - `PPT_CHROME_ARGS`
   - `PPT_CLAUDE_CMD`
   - `PPT_DATA_DIR`

4. 安装依赖并跑测试：

```bash
npm install
npm test
```

5. 启动服务：

```bash
npm start
```

6. 阅读接口文档：
   - [ppt-service-api-draft.md](ppt-service-api-draft.md)

7. 阅读内容协议：
   - [content-protocol.md](../content-protocol.md)

8. 用仓库里的 `content.md` 发一个任务，确认：
   - HTML 能生成
   - PPTX 能导出
   - 图片/视频/logo 能显示

只要这 8 步都通了，这个项目基本就已经完成了服务器迁移和最小可用验证。
