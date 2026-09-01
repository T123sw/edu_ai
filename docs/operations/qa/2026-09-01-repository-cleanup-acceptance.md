# 2026-09-01 仓库清理与目录迁移验收

## 结论

`codex/repository-cleanup` 已完成计划内的仓库清理、目录迁移和 Linux 部署配置统一，可以进入分支审阅与合并阶段。清理引入的定向回归未发现失败；后端全量套件和 OpenMAIC 套件仍有已知历史/外部依赖失败，本轮按约定只记录、不扩展修复范围。

本次仅修改本地 Git 仓库，没有登录或更改 Linux 服务器，没有安装软件、启用服务、修改防火墙或迁移生产数据。

## 版本与回滚点

- 清理前 `main`：`95bc7d19e639fcf751a3dabcf8217f61054b5710`
- 清理前标签：`backup/pre-repository-cleanup-20260901`
- 工作分支：`codex/repository-cleanup`
- 阶段提交：
  - `d57fbfc`：文档归并
  - `11bea00`：清理计划
  - `762e60d`：删除旧前端与旧数据管道
  - `5dd4c90`：仅保留 OpenMAIC PPTX 导出
  - `269098b`：清理生成残留并隔离运行数据
  - `72d916d`：迁移为标准前后端目录
  - `91852c1`：统一 Linux 环境和服务配置
- 清理验收标签：`cleanup/repository-layout-accepted-20260901`（指向本验收记录所在提交）
- Git 外备份：`D:\Edu_AI_cleanup-backup-20260901`

单阶段回滚使用 `git revert <阶段提交>`；放弃整轮清理时，可从 `backup/pre-repository-cleanup-20260901` 创建恢复分支。不要改写 `main` 历史。

## 已完成范围

- 删除旧 `src/pages`、旧数据采集管道和 EduAgent 的受版本控制内容。
- 删除普通 PPT/HTML2PPT 接口、适配器和部署依赖；PPTX 只保留 OpenMAIC 课堂导出链路。
- 将项目收敛为 `frontend/`、`backend/`、`openmaic-sidecar/`、`deploy/`、`scripts/`、`docs/` 六个主要边界。
- 将运行数据、上传内容、模型、构建产物、依赖目录、缓存和真实环境文件排除出 Git。
- 统一为根目录一个 `environment.yml` 和一个 `.env.example`。
- 统一 Linux 基线：Python 3.12、Node.js 22、pnpm 10.28、FFmpeg 6+。
- 统一服务端口：FastAPI `127.0.0.1:8001`、OpenMAIC `127.0.0.1:3000`、PostgreSQL `127.0.0.1:5432`，Nginx 提供公开入口。
- 统一服务器项目目录 `/home/zxqs_ep/Edu_AI` 和外部运行数据目录 `/data/edu_ai`。
- 提供统一安装、构建、部署一致性检查、systemd、Nginx 和 PostgreSQL 说明。

## 验证结果

| 检查项 | 结果 |
|---|---|
| 前端测试 | 436 通过，0 失败 |
| 前端生产构建 | 通过；仅有大分块提示，不阻断部署 |
| 后端清理定向回归 | 117 通过 |
| 后端模块编译与应用导入 | 通过；存在第三方弃用提示和未配置 MinerU 的运行提示 |
| 后端全量测试 | 1805 通过，24 失败，2 跳过；历史失败见下节 |
| OpenMAIC 生产构建 | 通过；Next.js 提示 middleware 约定将弃用，不阻断构建 |
| OpenMAIC 全量测试 | 1765 通过，1 失败；远程图片测试超时见下节 |
| 部署一致性检查 | 通过 |
| Linux Shell 语法 | Git Bash 检查通过 |
| PowerShell 安装脚本语法 | 通过 |
| 旧 `Edu_AI/` 受控路径 | 0 |
| 受控真实 `.env` 文件 | 0 |
| 受控依赖/构建/缓存目录 | 0 |
| 非语料 Markdown 相对链接 | 检查 196 个，0 个断链 |
| 疑似密钥模式复核 | 无真实密钥；4 个文件名/网址中的 `task-`、`musk-` 误命中 |
| `git diff --check` | 通过 |

课程语料 Markdown 中保留了抓取源站的 HTML、CSV、TSV 等相对链接。这些是原始语料内容，不是仓库文档导航，因此不纳入项目断链判定。

## 暂不修复的已知测试债务

后端 24 项失败分布：

- P4A AgentMemoryContext 模拟对象校验：3 项
- 博客生成适配器 `blog_llm_unavailable`：2 项
- 报告服务装配：1 项
- 报告图片下载器：9 项
- 报告图片本地化集成：4 项
- Alembic 修订链：1 项
- 结构化分块器：1 项
- 课堂媒体：1 项
- 课程 CRUD 权限：1 项
- durable task：1 项

OpenMAIC 的 1 项失败位于 `tests/edit/round-trip/insert.test.ts`，远程图片请求在 5 秒内未完成。它依赖外部网络时延，生产构建与其余 1765 项测试均通过。

## 合并前仍需人工确认

1. 审阅 `codex/repository-cleanup` 相对 `main` 的删除和目录迁移范围。
2. 确认另一个工作窗口不再依赖当前物理目录后，再把 Windows 文件夹 `D:\Edu_AI_1` 改名为 `D:\Edu_AI`。Git 内部结构和 Linux 路径已使用标准名称，本次不强行移动活跃工作区。
3. 合并后再按 `docs/deployment/README.md` 在服务器执行安装；本地验收没有对服务器做任何变更。
