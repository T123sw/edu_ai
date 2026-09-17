# P4 开发与验证日志

- 基线检查点：`dce6c013`（P0—P3 学习模块）。工作区中课程准备侧仍有独立未提交实现和迁移依赖；未将这些修改打包到学习提交。完整集成版本在 P5/P6 验证。
- `checks-red.log`、`memory-red.log`、`summary-red.log`：新增服务之前的缺模块红灯。
- `checks-first.log`：首轮 5 failed / 3 passed。SQLite 检查鉴权读取了事实服务，嵌套写事务导致锁冲突；改为不读取进度的授权课程投影。另一个断言使用了 fixture 未设置的仓储别名，改为实际 ProgressService.repository。
- `checks-memory.log`：修复后 14 passed。
- `summary-first.log`：摘要原始历史保留、来源校验、CAS 及删除 epoch 防复活，4 passed。
- 当前阶段仍在实施；以上局部通过不表示 P4 完成。
- `integration-first.log`：47 passed（P3 与 P4 初步集成）。
- `enrichment-second.log`：24 passed（包括真实最后提交窗口的 epoch 检查和旧记忆入口防复活）。
- `browser-first.log`：1 passed / 1 failed，结果状态与解释共享父文本节点，精确定位器未匹配；分开状态文本后 `browser-second.log` 2 passed。随后修正账号切换测试初始化，确保实际测试 bob。
- `full-first.log`：154 passed / 2 failed / 1 skipped；旧资料版本不在 JSON 历史中时应保留已保存题目/作答，不能用新资料重新评价；该分支已修复并显示来源不可用。
- `memory-recovery.log`：16 passed，覆盖偏好写入后、检查点落盘前崩溃的回执对账。
- `full-second.log`：160 passed / 1 skipped；跳过只针对 SQLite 跨进程旧用例。
- 随后增补和相关回归：`memory-final.log` 30 passed，`summary-final.log` 6 passed，`checks-manifest-final.log` 30 passed，`partial-success.log` 2 passed；这些结果有重复覆盖，不能简单求和。
- `browser-third.log` 3 passed，包含真实个人中心入口。`frontend-unit.log` 9 passed，`types-final.log`、`lint-final.log` 均退出 0、无错误输出。
- 默认开关关闭，未迁移业务数据库；临时 PostgreSQL 保留运行供 P5/P6 使用。
