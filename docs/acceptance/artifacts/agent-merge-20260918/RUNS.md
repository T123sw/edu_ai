# 合并验证记录

- `backend.log`：首次收集暴露课程通知依赖另一套学习模型，后续改为准备模块独立通知。
- `backend-2.log`：首轮未配置 PostgreSQL；317 passed / 165 skipped，不能作为并发验证。
- `backend-final.log`：配置隔离 PostgreSQL 的完整回归；在任务归属边界修复前启动，边界修复随后由 `boundaries-final.log` 补验。
- `integration*.log`：两种数据库验证已交付课程进入原学习 Agent，以及偏好删除失效；第二轮增加原 P5 真实存储制作、可选资料进度交接。
- `boundaries.log`：路径拼写错误，未执行测试；`boundaries-final.log` 为纠正路径后的有效结果，同时覆盖最终任务归属边界。
- `browser.log`：第一次浏览器启动缺少显式测试数据库环境变量；`browser-2.log` 为有效重跑。
- `preparation-browser.log`：课程准备页面请求幂等、状态恢复及上传等待，接口采用浏览器测试替身。
- `browser-2.log`、`handoff-browser.log`：原学习 Agent 的真实接口和隔离 PostgreSQL 浏览器回归，模型为确定性测试替身。
- `migrations.log`：临时 PostgreSQL 数据库从原分支 0029 升级到合并后 0036，保留原表和哨兵记录。
- `frontend-unit.log`、`types-2.log`、`build.log`：前端测试、类型检查与构建。
- `shared-regression.log`：应用启动、资源生成及课堂服务回归。

没有加载原工作区的私有配置，也没有在本次合并中调用付费模型。原始真实任务日志保留在历史阶段验收目录中。

- `memory-pg.log`：完整回归跳过的共享记忆 PostgreSQL 写入/跨会话召回，在临时 schema 中单独补验，结束后清理。
