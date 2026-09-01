# Windows 本地一键启动与目录改名设计

> 状态：用户于 2026-09-01 确认设计，等待书面规格复核后实施。

## 目标

为清理后的标准仓库提供 Windows 本地开发入口。用户双击根目录 `start.bat` 后，分别在三个可见终端中启动 FastAPI、OpenMAIC 和 Vite；`stop.bat` 只停止本次由项目启动的进程。完成实现后，将当前物理目录 `D:\Edu_AI_1` 改名为 `D:\Edu_AI`，修复现有 Git worktree 路径，并通过真实服务与浏览器端到端测试验收。

## 非目标

- 不恢复旧 `Edu_AI/` 嵌套目录、Docker PostgreSQL、HTML2PPT 或普通 PPT 服务。
- 不自动安装或升级依赖；缺少依赖时提示运行 `scripts/install-all.ps1`。
- 不强制结束占用端口的未知进程。
- 不修改 Linux systemd/Nginx 的生产启动方式。
- 不合并、删除或改写已有 worktree 分支。

## 入口与组件

### 根目录入口

- `start.bat`：用户入口，仅负责调用 `scripts/start-dev.ps1` 并传递参数。
- `stop.bat`：停止入口，仅负责调用 `scripts/stop-dev.ps1`。

### PowerShell 控制器

- `scripts/start-dev.ps1`：完成环境检查、端口检查、环境变量加载、三个可见终端启动、PID 记录、健康等待和浏览器打开。
- `scripts/stop-dev.ps1`：读取 PID 清单，验证进程仍存在后按进程树停止，并删除清单。
- 运行状态写入根目录 `.runtime/dev-processes.json`；`.runtime/` 必须被 Git 忽略。

批处理文件保持简单，使路径中包含空格时仍可工作，也避免在 Batch 中实现复杂 JSON、HTTP 和进程逻辑。

## 运行契约

### 服务与端口

| 服务 | 工作目录 | 命令边界 | 地址 |
|---|---|---|---|
| FastAPI | `backend/src` | Python 3.12 执行 `uvicorn app.main:app` | `http://127.0.0.1:8001` |
| OpenMAIC | `openmaic-sidecar` | pnpm 10.28 执行 `dev` | `http://127.0.0.1:3000` |
| Vite | `frontend` | pnpm 10.28 执行 `dev` | `http://127.0.0.1:5173` |

前端子进程注入 `VITE_API_BASE_URL=http://127.0.0.1:8001`。三个子进程继承根目录 `.env` 中的配置；真实密钥不写入命令行、日志或 PID 清单。

### 启动前检查

1. 校验根目录和三个应用入口存在。
2. 校验 `.env` 存在；缺失时提示从 `.env.example` 创建。
3. 定位 Python 3.12：优先使用已激活的 `edu-ai` 环境，其次使用可执行且依赖完整的 Python 3.12。
4. 校验 Node.js 22、pnpm 10.28、前端与 OpenMAIC 的 `node_modules`。
5. 校验 8001、3000、5173 均未被占用。任何端口被占用时停止启动并报告，不结束未知进程。
6. `start.bat --check` 只执行上述检查，不创建进程。

### 启动和健康检查

控制器按 OpenMAIC、后端、前端的顺序打开三个可见终端。每启动一个服务即记录终端进程 PID，并等待对应地址：

- OpenMAIC：`GET /api/health` 返回 2xx。
- FastAPI：`GET /health` 返回 2xx。
- 前端：`GET /` 返回小于 500 的状态。

默认等待上限为每个服务 120 秒。任何服务超时，控制器报告失败并调用停止逻辑清理由本次启动的进程；不遗留半启动状态。三个服务全部健康后才打开 `http://127.0.0.1:5173`。

### 停止行为

`stop.bat` 读取 `.runtime/dev-processes.json`，只处理其中记录的 PID。停止前验证 PID 对应进程仍然存在；使用 Windows 进程树停止方式关闭终端及其子进程。清单缺失时返回成功并提示当前没有受管服务。

## 目录改名和 worktree 安全

改名前执行以下只读检查：

1. 当前主工作区无未提交修改。
2. `D:\Edu_AI` 不存在。
3. 记录 `git worktree list --porcelain` 的所有 worktree 和分支。
4. 确认 3000、5173、8001 无监听进程。

从 `D:\` 将完整目录 `D:\Edu_AI_1` 移动为 `D:\Edu_AI`。由于现有 worktree 位于 `.worktrees/` 且 Git 元数据包含绝对路径，改名后执行 Git worktree repair，并逐项验证新路径、分支和 HEAD 与改名前记录一致。不得删除或重新创建 worktree。

如果 Windows 因当前应用持有目录句柄而拒绝改名，应停止后续启动，保留现状并报告；不得复制后删除原目录作为替代方案。

## 测试策略

实现遵循测试先行：

1. 先添加启动器契约测试，验证标准目录、端口、命令、PID 清单、禁止强杀未知端口和 `--check` 行为；确认测试因文件尚不存在而失败。
2. 实现最小启动器，使契约测试通过。
3. 执行 `start.bat --check`。
4. 完成目录改名和 worktree repair，重新执行契约测试。
5. 实际执行 `start.bat`，确认三个健康端点。
6. 运行 Playwright 浏览器冒烟测试，至少验证前端可打开、应用主壳渲染、前端能够访问后端健康接口、OpenMAIC 健康接口可访问。
7. 执行 `stop.bat`，确认三个端口释放且 PID 清单删除。

端到端测试只使用本地服务，不调用真实收费模型，不修改生产服务器或生产数据库。

## 版本控制

- 规格文档单独提交。
- 启动器测试与实现作为独立功能提交。
- 目录物理改名不改变 Git 文件历史；改名后提交路径保持标准仓库根目录相对路径。
- 验收结果记录到 `docs/operations/qa/`，再创建启动器验收标签，便于回滚到实现前或清理验收状态。
