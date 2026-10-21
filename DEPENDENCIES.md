# Edu-AI 依赖与运行基线

更新日期：2026-10-17

本文记录项目重构和 Linux 部署采用的唯一环境基线。具体服务器事实与上线待办见 [`docs/deployment/`](docs/deployment/README.md)。

## 支持的运行组件

- React/Vite 前端；
- FastAPI 后端；
- PostgreSQL；
- HyperFrames 0.8.168 原生 CLI/player（无需常驻 sidecar）；
- 固定版本的 MAIC-UI 原生生成仓库（模拟实验）；
- Playwright Chromium 与 FFmpeg 视频导出。

不安装 EduAgent、旧数据采集管道、SearXNG、HTML2PPT、普通 PPT 服务、数字人或 WebRTC 组件。

## 版本基线

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| Miniforge/Conda | 当前稳定版 | Python 与系统库环境管理 |
| Python | 3.12 | FastAPI、RAG、媒体处理 |
| Node.js | 22 | 前端、HyperFrames 和视频脚本 |
| bubblewrap | Linux 系统包 | 渲染任务的网络、文件系统与进程隔离 |
| pnpm | 10.28 | 前端包管理器 |
| FFmpeg/ffprobe | 6+ | MP4、音频、字幕和媒体探测 |
| PostgreSQL | 14+ | 生产数据库 |
| Chromium | 与 Playwright 匹配 | 课堂渲染、视频导出、PBL 生成验证 |
| @codesandbox/sandpack-react | 2.20.0（精确锁定，Apache-2.0） | 编程练习原生编辑器与预览 |
| acorn | 8.15.0（精确锁定，MIT） | 纯 JavaScript 练习源码静态检查 |
| MAIC-UI | aad58ddcc2103058b4c2deffc48a3c13e2c64dd6 | 原生科学建模、HeavyGenerator 两阶段生成、公式后处理 |
| PyPDF2 | 3.0.1 | MAIC-UI 原生模块导入依赖 |
| @tailwindcss/browser | 4.1.18 | 将原生实验页面所需样式运行库内嵌到沙箱 |

## 依赖文件

- 根目录 `environment.yml`：唯一 Conda 环境定义。
- 后端 `requirements.txt`、`requirements-lock.txt`、`requirements-media.txt`：Python 依赖来源。
- 前端 `pnpm-lock.yaml` 与 `hyperframes-runtime/package-lock.json`：分别锁定前端和原生渲染运行时。
- `.env.example`：配置字段模板，不包含真实密钥。

项目不再使用应用目录内重复的 `environment.yml` 或生产 venv 安装说明。

## 统一端口

| 端口 | 服务 | 暴露方式 |
| --- | --- | --- |
| 5432 | PostgreSQL | 仅内部访问 |
| 8001 | FastAPI | 由 Nginx 代理 |
| 5173 | Vite 开发服务器 | 仅本地开发 |

## 包管理规则

```bash
bash scripts/install-all.sh
conda activate edu-ai
```

前端使用 pnpm；独立 HyperFrames 运行时使用 npm ci 和精确锁文件。上游完整源码、文档、skills、Studio 和 SDK 保留在 vendor/hyperframes，平台适配放在上游目录之外。Linux 生成 worker 需要 bubblewrap、Chromium 和 FFmpeg；Windows 前端开发可用，原生生成应连接 Linux worker。

## 运行数据

代码与运行数据必须分离。Linux 目标数据根目录为 `/data/edu_ai/`，用于保存课程、上传、模型、缓存、日志和备份。以下内容不得提交：

- `.env` 和密钥；
- Conda 环境、虚拟环境和 `node_modules/`；
- `dist/`、`.next/`、测试输出和缓存；
- 用户数据、课程生成物、向量库、模型和日志。

## Sandpack 编程练习

首版为 JavaScript 快速排序。浏览器需要访问固定运行域名 `https://2-19-8-sandpack.codesandbox.io`；其 client 版本为 2.19.8，与 React 包 2.20.0 不同。业务服务需要在 PATH 中找到 Node 22，并能从 `frontend` 运行 `node --import tsx scripts/validate-pbl.mjs`，且已安装 Playwright Chromium。后端只用隔离浏览器执行模型源码。生产 PBL 数据与 durable task 必须使用同一 PostgreSQL 数据库。迁移 head 为 `20261013_0038`。详见[实现验收与部署交接](docs/acceptance/2026-10-13-sandpack-algorithm-practice/README.md)。

### PBL 多步骤页面检查（2026-10-14）

前端工具依赖 `esbuild` 固定为 `0.25.0`，用于把限定的 React 工程编译为内存中的浏览器资源；学生代码只在无登录信息、禁止外网请求的 Playwright Chromium 中运行，不在 Node/Python 宿主执行。Sandpack 工程固定 React / React DOM `18.3.1`。检查服务要求后端 PATH 包含 Node，并已安装 Playwright Chromium；工作进程以进程组超时终止，单进程最多同时执行两个浏览器检查。

### MAIC-UI 原生模拟实验（2026-10-14）

`python scripts/install-maic-ui.py` 克隆完整上游仓库到 `.runtime/maic-ui-native` 并固定提交；统一安装脚本已包含此步骤。仓库保留原样，平台通过 `app/practice/native.py` 调用实际原生类，适配当前用户的模型配置、取消状态和进度。页面保留原生 HTML、交互脚本与绘图，接入左步骤、中实验/观察、右问答的三栏工作区；可识别的原生重复步骤说明收进可展开区域，手机使用面板切换。Tailwind、KaTeX 及公式字体从 `frontend/node_modules` 内嵌，不依赖浏览器访问 CDN。生产环境须保留前端完整依赖，不能仅复制 `dist` 或使用 `pnpm install --prod`。

浏览器检查要求后端 PATH 包含 Node、已安装 Playwright Chromium；新增 DPR=2、最小画布字体、缩放稳定性和暂停检查。生成失败或上游降级占位页面不会交付。没有新增数据库迁移；启用需要发布前端并重启后端。旧实验保存的是旧 HTML，需重新生成才使用原生链路，历史记录不自动覆盖。实现及验收范围见[原生实验验收](docs/acceptance/2026-10-14-maic-ui-native/README.md)。
