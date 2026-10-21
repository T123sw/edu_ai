# PBL 重启后端到端复验（2026-10-17）

本轮使用 08:23:02 UTC 重启后的同一份源代码、线上已发布前端、隔离 PostgreSQL 和持久任务工作器，重新调用真实模型生成项目，再用 Chromium 实际操作工作区。生产服务仅做只读版本/健康核验，测试请求转发到隔离后端 8027，未写生产用户数据。不是直接在生产数据库上完成的写入测试。

## 已确认的版本

生产进程 PID 1160014；18 个相关源文件哈希匹配上次修复，所有修改时间早于重启。线上前端 481 个文件哈希匹配，后端 OpenAPI 返回 200。见 [restart-verification.json](restart-verification.json)。

## 发现：排队期间仍显示旧失败任务

已修复的 URL 路由问题没有复现，但繁忙队列下出现另一处状态关联问题：点击“重试生成”成功创建新任务，新任务处于 pending/queued；项目的 current_job_id 仍指向旧失败任务。页面每两秒按项目 ID 轮询，覆盖刚收到的新任务状态，恢复显示“生成暂未完成 / 重试生成”，取消按钮消失。刷新也返回旧失败状态。

真实页面断言等待“取消生成”60秒失败。数据库和 API 同时确认新任务待领取、旧任务失败，见 [queued-retry-stale-state.json](queued-retry-stale-state.json) 和原始浏览器日志。不是模型输出问题。

定位：`job_retry_service.retry_durable_job` 只创建并入队新任务；`PblRepository.claim_generation` 在工作器领取之后才更新 current_job_id，而 PBL detail/list 从该字段取任务。需在重试入队与项目任务绑定之间建立一致性，并处理并发重试和入队失败回滚，避免只在前端短暂掩盖旧状态。本轮为验证，未改产品代码。

## 生成、浏览器与独立验收

五次从零生成均成功（5/5），包括同一购物清单需求的两次独立生成。共 17 步、57 项最终累计检查，主矩阵共 43 次真实模型调用。时长包含并发排队。

| 项目 | 步骤 | 最终累计检查 | 模型调用 | 总时长（含排队） |
| --- | ---: | ---: | ---: | ---: |
| 购物清单 A | 5 | 15 | 11 | 393 秒 |
| 相同需求购物清单 B | 4 | 17 | 9 | 192 秒 |
| 报名表 | 1 | 6 | 3 | 38 秒 |
| 作品展示页 | 1 | 6 | 5 | 258 秒 |
| 双人记分牌 | 6 | 13 | 15 | 188 秒 |

3 个项目无需修复；记分牌最终验收出现 JSON 解析错误，追加 repair_step + repair_checks 两次调用后成功；作品页第一次验收误把作品区写成位于简介上方，也通过本步修复纠正。保留这些实际问题，不把“自动恢复后成功”写成“首次候选全部正确”。见 [生成结果](generation-summary.json)、[调用记录](model-calls.json) 与 [验收上下文](acceptance-contexts.json)。所有验收设计调用都看到了当前代码，有前序检查的阶段同时带着前序代码、检查和浏览器运行结果。

5/5 个项目的 17 步页面流程全部通过；5 个项目均在外宽 390/320px、预览实际宽 349/279px 下正常显示，没有横向溢出，浏览器运行异常为 0。见 [browser-summary.json](browser-summary.json) 与 [verification.json](verification.json)。

页面流程覆盖空工程失败、逐步在 CodeMirror 写代码、累计检查、下一步保留工程、代码修改撤销当前通过状态、刷新恢复代码与步骤、退回未完成代码判失败、恢复代码再次通过、桌面和 390/320px 手机预览，以及公开接口不泄漏参考答案。

独立业务验证共 19 组（记分牌 5、报名表 4、购物清单 7、作品页 3），不以“参考实现通过自己的检查”代替需求验证；全部通过。见 [independent-preview.json](independent-preview.json)。

对本轮新生成的正确实现注入 8 个定向错误，独立断言先确认正确基线通过、错误实现确实违背需求，再运行原样的模型验收。8/8 均被识别，未人工补充模型验收。见 [表单](fresh-mutation-audit.json)、[记分牌](score-mutation-audit.json)、[购物清单](shopping-mutation-audit.json)。这是定向样本结论，不保证未来所有项目都不会漏检。

## 恢复、任务时限和接口

- 代码已保存、验收尚未完成时真实取消；取消后没有发布产物。重试只追加一次 build_checks，代码完全复用，项目最终成功。取消前计划因需求关联遗漏自行修复过一次，所以总阶段为 plan → plan → build_step → build_checks（取消）→ build_checks。见 [real-cancel-retry.json](real-cancel-retry.json)。
- 注入旧任务修复预算耗尽的检查点，经实际页面重试后最终成功，新增 repair_step + repair_checks 两次调用，无重新规划、无错误项目 URL / 404；前 3 步代码完全相同、10 项旧检查经当前 schema 归一化后相同。旧检查仅序列化补齐空 within/index 字段。排队状态问题仍未修复。见 [最终恢复](retry-eventual-recovery.json) 与 [检查点比对](retry-checkpoint-evidence.json)。
- 实际数据库确认所有领取后的 PBL 任务执行窗口均为 1800 秒，排队没有消耗执行窗口。见 [task-deadlines.json](task-deadlines.json)。本轮未等待 30 分钟人为制造实际超时。
- 匿名 401、跨用户 detail/workspace/runs/check 404、检查 runId 幂等与冲突 409、非法文件 422、同版本并发保存只有一个成功（200/409），均通过。见 [api-contracts.json](api-contracts.json)。

## 测试边界和复现

本轮仅新增验收材料，不修改或发布产品逻辑。原始浏览器断言失败日志保留为 [ui-retry.log](ui-retry.log)。取消恢复脚本最初错误假设取消前只有一次 plan，因此报过测试断言失败；复核同一任务的真实接口与阶段轨迹后改为核对重试之后只调用 build_checks，见 [原始脚本结果](recovery-harness-initial.json) 与更正后的恢复证据。另一次截图在页面未稳定时出现 captureScreenshot 工具错误，等待 main 后正常抓取，没有把它归因于产品功能失败。

测试里有 Sandpack 重载导致的 ERR_ABORTED，以及后台遥测请求超时，页面运行和检查未受影响；详细请求记录保留在各项目 browser.json 中。

`reproduction/fresh/` 保存本轮用于反例实验的模型产物；以下命令无需模型或数据库，复放 8 个反例并另写 *-mutation-replay.json，不覆盖首次证据：

```sh
node docs/acceptance/2026-10-17-pbl-restart-e2e/reproduction/audit.mjs
node docs/acceptance/2026-10-17-pbl-restart-e2e/reproduction/audit-score.mjs
node docs/acceptance/2026-10-17-pbl-restart-e2e/reproduction/audit-shop.mjs
```

`reproduction/scripts/` 保存本轮实际使用的实时生成、浏览器、恢复和 API 脚本；其隔离数据库、临时路径和端口按本机配置，不可直接指向生产数据库。测试授权 token 不复制进验收目录。

