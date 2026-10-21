# Sandpack 快速排序练习验收

2026-10-13。实现范围：**JavaScript 快速排序，一个完整任务**。源码已接入，真实模型和浏览器完整流程通过；未部署到业务站点、未修改生产数据库。最终测试明细见 [verification.json](verification.json)。

用户在“互动实验 → 编程练习”输入快速排序需求，系统生成任务、教程、提示、骨架及用例。模型参考实现经隔离浏览器检查后，才发布公开练习。用户在左侧目录旁的 Sandpack 原生编辑器完成算法，显式运行、检查，并查看真实输入输出。

最终结果：后端 **63 项**、前端单元 **18 项**、最终业务浏览器 **10 项（含真实模型完整链路）**通过；共享浏览器验证器 **3 项**通过。最终真实生成包含 **16 个用例**。构建成功，复审通过；详细命令及各批测试范围见 `verification.json`，不同批次不累加为唯一测试总数。

## 已验证效果

- 真实模型 → durable 后台任务 → 独立 PostgreSQL → 官方 Sandpack → 运行检查 → 保存/刷新恢复，全链路有实际执行证据，见 [真实流程](real-flow.json) 和 [公开生成材料](real-model-artifact.json)。
- 故意丢失重复值的代码检查失败；修正后全部通过；再次修改立即使旧报告失效，刷新恢复后可重新检查。
- Worker 死循环可停止/超时，之后能重新运行；错误返回、原数组修改、稀疏数组、伪造完成消息均有回归检查。
- 代码和报告分别保存；延迟响应不覆盖新编辑；断网草稿保留；多标签冲突可选版本、恢复备份。
- PostgreSQL 并发更新同一 revision 只允许一个成功；旧 worker/旧任务不能发布；取消、重试和恢复有实际队列测试。
- 原模拟实验桌面/手机回归通过；原课堂任务结果跳转单元测试通过。

页面：[桌面](fixture-1440.png) · [中等屏幕](fixture-1024.png) · [手机](fixture-390.png)。真实模型页面见 [桌面](real-1440.png) 和 [错误实现反馈](real-wrong-code.png)。

## 执行边界

首版不包含复杂项目拆步、Python、Agent 辅导或考试级防作弊。检查结果标记为 `browser_reported`；通过用例不等于证明一定使用快速排序或已经掌握知识。源码静态限制也不是完整的恶意代码安全证明。

真实托管运行依赖外网；运行环境断开时保留编辑和草稿，可重新连接。浏览器验证任务取消后不发布结果，其子进程仍受 75 秒终止上限约束。自动材料修复最多两次，计数随恢复保留。

现有仓库全量 TypeScript 检查有既存错误；本轮记录基线并比较，未增加诊断。构建、全量 lint（有既存警告）和功能测试分别报告，不将它们表述为全仓类型检查通过。

## 复验方式

以下只用于独立测试数据库。`scripts/pbl/isolated.py` 先禁用生产 `.env` 的存储覆盖，防止测试误用业务数据。

```sh
export PATH=/home/zxqs_ep/miniforge3/envs/edu-ai/bin:$PATH
export PBL_TEST_DATABASE_URL=postgresql+psycopg://zxqs_ep@127.0.0.1:55439/edu_pbl_acceptance_20261013
python scripts/pbl/isolated.py pytest backend/src/tests/pbl backend/src/tests/test_durable_task_executor.py backend/src/tests/test_job_retry_service.py -q
# frontend 目录
pnpm exec playwright test -c playwright.pbl.config.ts pbl-runtime.spec.ts pbl.spec.ts
```

真实服务启动脚本为 `scripts/pbl/acceptance_server.py`，端口 8017，要求显式带 `pbl_acceptance` 的数据库名称。完整真实浏览器测试：先用 `VITE_API_BASE_URL=http://127.0.0.1:8017` 构建 `dist-pbl`，在 5208 预览，再以 `PBL_LIVE=1 PBL_FRONTEND_URL=http://127.0.0.1:5208` 运行 `pbl-live.spec.ts`。这会调用实际模型并生成新练习，不是固定 fixture。

## 部署交接

- 前端依赖：`@codesandbox/sandpack-react@2.20.0`、`acorn@8.15.0`，使用工作区中的 pnpm lockfile。托管 bundler/client 固定域名：`https://2-19-8-sandpack.codesandbox.io`。
- 后端依赖：Node 22、tsx、Playwright Chromium；源码与 `frontend/src/pbl/runtime/`、`frontend/scripts/validate-pbl.mjs` 同版本部署。
- 数据库：Alembic 唯一 head `20261013_0038`。先备份并迁移，再更新服务；PBL 和 durable task 必须在同一 PostgreSQL。测试仅在独立 schema 演练新增迁移 upgrade/downgrade/re-upgrade。
- 正式前端构建应继续使用既有 `/backend` 代理，**不要发布验收用的 `dist-pbl`，它指向本机 8017**。
- 回退：恢复上一版前端和后端，保留三张 PBL 表及用户数据；不要为回退页面删除用户工程。
- 本轮保留当前功能分支和原有未提交改动，没有提交、合并、推送或生产重启。
