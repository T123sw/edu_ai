# G 阶段交接

G0 共同基线 `18080783`，集成工作树 `.worktrees/preparation-integration-20260919`，分支 `integration/preparation-chain-20260919`。

已集成 A `e3d3ce6b` / `d7d26fc8` / `c264070f`；C `868320bb` / `f115f629` / `8864ee7c` / `73d6eed3` / `1ad95410`；D `ee818810` / `3157cb4f`；E `cc234811` / `21195202` / `21cdfea0`；F `debc7960` / `7da7b9b8`。各窗口工作区未覆盖，重复临时基线未重复挑入。

G 已交付真实 HTTP + 实际 worker 的隔离启动/验收脚本、参数与场景账本、真实学习资源版本/正文回读检查、三类 handler 接线门禁、桌面与窄屏 Playwright 用例。正式前端构建通过。历史共享报告三个失败经 D 修复后相关测试全部通过；D/F 相关回归 176 passed / 10 skipped；E/C/G 补充 102 passed（有重叠，不合计）。

B 仍无可引用提交，G 未擅自打包其在途代码。B 主 handler 必须接通 A payload、F ResourceCheckpointPort、分类恢复及原生 Harness。G 的 handler 门禁分别拦截 report/quiz/classroom，检查实际 payload 和授权 checkpoint 可保存/读取；当前六个数据库参数场景都因 B 尚缺而跳过。

E03 真实模型/MinerU/HTTP/worker 诊断得到 RESEARCH_INSUFFICIENT，无课程；7 次模型 completion、1 次来源动作、45692 tokens、58.22 秒。因 B 回执 phase 尚缺，严格验收仍失败。初次测试模型配置错误另行保留，不计成产品稳定性成绩。

G1–G4 未完成：E01 连续三轮、E02/E10、E04–E09 专项驱动与运行、真实参数语义对照、生产浏览器/音频和最终同 SHA 全量验收仍待继续。六个专项驱动未实现属于 G 待办，不仅仅是 B 依赖。

完整记录位于集成分支 `docs/acceptance/2026-09-19-preparation-chain-integration/README.md` 与 `ledger.json`。私有测试库/配置/原始证据保留在 `/tmp/preparation-validation-g-20260919*`，服务在本阶段交接时停止；未操作业务数据库或部署业务服务。
