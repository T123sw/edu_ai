# Edu-AI 统一启动 OpenMAIC 设计

## 目标

更新 `Edu_AI/api/src/start_api.bat`，让一次启动同时拉起：

1. `openmaic-sidecar`（Next.js，端口 3000）；
2. Edu-AI 前端（Vite，端口 5173）；
3. Edu-AI 后端（FastAPI，端口 8001）。

OpenMAIC 保持位于仓库根目录 `openmaic-sidecar/`，不移动到 `Edu_AI/` 内。

## 运行边界

- OpenMAIC 的 `pnpm dev` 是一个 Next.js 一体化进程，同时提供它自己的页面和
  `/api/*`；不需要再单独启动一个 OpenMAIC 前端进程。
- Edu-AI 只依赖 OpenMAIC 的 HTTP API 和本地 `packages/` 包。
- FastAPI 启动前必须确认 `GET http://127.0.0.1:3000/api/health` 返回 200。

## 启动策略

- 如果 3000 端口上的 OpenMAIC 健康，则复用现有进程。
- 如果 3000 端口空闲，则在独立终端中运行 `pnpm.cmd dev`，并等待健康检查。
- 如果 3000 已被占用但健康检查失败，则停止整个启动流程，不强杀未知进程。
- sidecar 缺少 `.env`/`.env.local`、`package.json`、pnpm 或依赖安装失败时，
  显示明确错误并停止。
- 健康检查超时后停止，不继续启动一个必然无法生成课堂的 FastAPI。

## 验收

- 静态回归测试能证明脚本声明了 sidecar 路径、端口、启动命令和健康检查。
- `start_api.bat --check` 能检查三部分项目入口。
- sidecar 已运行时脚本可复用。
- sidecar 未运行时脚本能启动并等待 `/api/health`。
- 原有退役服务不会重新进入启动脚本。
