# Windows 本地启动器验收记录（2026-09-01）

## 验收结论

Windows 本地启动器已在规范根目录 `D:\Edu_AI` 完成真实整栈验收。OpenMAIC、FastAPI 和前端均成功启动并通过健康检查；Playwright 浏览器冒烟测试通过；`stop.bat` 能按 PID 清单关闭全部受管进程并释放端口。

## 验收环境

- 规范仓库根目录：`D:\Edu_AI`
- 分支：`codex/repository-cleanup`
- Python：3.12.9
- Node.js：24.11.1
- pnpm：10.28.0
- 服务端口：OpenMAIC `3000`、FastAPI `8001`、前端 `5173`

本地 `.env` 与 `deploy/postgres/.env.postgres` 由清理前的本机配置迁移而来，均受 `.gitignore` 保护；验收过程中未输出或提交密钥值。

## 执行结果

1. `start.bat --check --no-browser`：通过，确认目录、依赖、运行时版本和端口可用。
2. `start.bat --no-browser`：通过，三个服务按 OpenMAIC → FastAPI → 前端的顺序启动。
3. HTTP 健康检查：
   - `http://127.0.0.1:3000/api/health` → 200
   - `http://127.0.0.1:8001/health` → 200
   - `http://127.0.0.1:5173/` → 200
4. `frontend/tests/e2e/local-launcher-smoke.spec.ts`：1 项通过。测试确认首页根节点完成渲染，并从浏览器上下文访问 FastAPI 与 OpenMAIC。
5. `stop.bat`：通过，三个受管窗口及其子进程均已停止。
6. 停止后复核：端口 `3000`、`8001`、`5173` 均空闲，`.runtime/dev-processes.json` 与临时 `.cmd` 文件均不存在。
7. 启动器契约测试：9 项通过；两个 PowerShell 控制器解析错误数为 0。

## 验收中修复的问题

- 将 `.env` 的解析改为按第一个等号切分，兼容值中包含等号的场景，并避免 PowerShell 重载解析错误。
- 移除 pnpm 10 会原样传给开发服务器的多余 `--` 参数。
- Windows 下 OpenMAIC 使用 Next.js webpack 开发服务器，规避本机 Turbopack 的 `os error 5` 访问拒绝。
- 按锁文件重建迁移后不完整的 OpenMAIC 与前端 `node_modules`；未修改锁文件。

## 目录迁移与回滚信息

- 原物理根目录 `D:\Edu_AI_1` 的仓库内容已迁移到 `D:\Edu_AI`。
- 17 个已登记 Git worktree 的管理路径已修复，迁移前已有的未提交改动数量保持不变。
- 未登记的旧 worktree 目录与旧本地运行数据未删除，保存在 `D:\Edu_AI_cleanup-backup-20260901\phase6-root-residue`，可用于人工恢复。
- 当前 Codex 任务仍以旧路径作为宿主工作目录，因此任务运行期间可能自动重建空的 `D:\Edu_AI_1`；其中不包含规范仓库内容，关闭本任务后可再清理。
