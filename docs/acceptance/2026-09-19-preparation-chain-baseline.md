# G0 共同基线

共同基线：`18080783b7aa9b50f23e688a57a7944df90e258a`；父提交：`67fc18b8`。
集成分支：`integration/preparation-chain-20260919`。

从父提交仅纳入上一轮研究 coverage、blocker、来源有限重试、终端回执精简、相关测试、审查证据和本轮计划。新模块 `research_coverage.py`、`source_errors.py` 均已纳入。使用独立 Git index 和 commit-tree 快照，原分支、原 index、未提交文件全部保留。

排除：`.bak*`、前端 dist 目录、音频、忽略的日志、业务数据库、任务库、上传原件、凭据以及其他窗口此时正在编写的领域实现。完整内容可用 `git diff 67fc18b8 18080783` 审计。起始状态和补丁另存本地 `/tmp/edu-preparation-g0-20260919`。

各窗口在自己的 worktree 记录实际起点；已有分支无需重置。交付时由 G 按 A → B → C → D → E → F 检查并集成，依赖公共接口 SHA 必须明确。不要在其他窗口工作区执行 reset/stash。

基线针对研究健壮性/Harness/来源适配器的测试：40 passed、2 skipped（未设置隔离 PostgreSQL）。这不是全链路验收。

历史比较值：完整课程 295.36 秒、34 次模型调用；联网路径 229.86 秒、27 次。后者没有完成交付，不能与完整课程直接比较。缩小场景的成绩不能用于宣布同条件性能提高。
