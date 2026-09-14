# 知识点标准资源安全重生成与 Agent Skills 验收

日期：2026-09-10  
状态：通过（目标范围）

设计：[设计文档](../superpowers/specs/2026-09-10-standard-resource-regeneration-agent-design-cn.md)  
计划：[实施计划](../superpowers/plans/2026-09-10-standard-resource-regeneration-agent-implementation-cn.md)

## 1. 功能门槛

| ID | 场景 | 通过标准 | 状态 |
| --- | --- | --- | --- |
| RG-01 | 部分资源已存在 | 默认预检只生成缺失槽位 | 通过 |
| RG-02 | 已退回资源 | repair 模式携带退回理由创建候选新版 | 通过 |
| RG-03 | 已批准资源 | regenerate 模式保留旧批准版并创建待审新版 | 通过 |
| RG-04 | 待审核/生成中 | 不静默覆盖，预检显示阻断 | 通过 |
| RG-05 | 类型选择 | 只为选中的标准资源类型创建任务 | 通过 |
| RG-06 | 空计划 | 不创建空批次，返回可操作提示 | 通过 |

## 2. 一致性与安全门槛

| ID | 场景 | 通过标准 | 状态 |
| --- | --- | --- | --- |
| SAFE-01 | 重复确认请求 | 同课程同幂等键返回同一批次 | 通过 |
| SAFE-02 | 同槽位并发生成 | 第二个活跃请求被阻断，不产生覆盖竞态 | 通过 |
| SAFE-03 | 审核期间出现新版 | 版本或哈希不一致返回 409，不批准新版 | 通过 |
| SAFE-04 | 批次结果 | 每个成功项记录准确材料版本和哈希 | 通过 |
| SAFE-05 | 图谱变化 | 创建阶段拒绝过期预检 | 通过 |
| SAFE-06 | 学生权限 | 学生不能读取批次控制信息或待审内容 | 通过 |

## 3. Agent/Skill 质量门槛

| ID | 场景 | 通过标准 | 状态 |
| --- | --- | --- | --- |
| SK-01 | 共享蓝图 | 同一知识点三个任务携带一致蓝图和 Skill 版本 | 通过 |
| SK-02 | 退回修订 | 生成上下文包含退回意见和基线版本 | 通过 |
| SK-03 | 独立审阅 | 三类标准资源均启用 required review | 通过 |
| SK-04 | 发布边界 | Agent/Skill 无权批准或切换 approved_version | 通过 |

## 4. 浏览器端到端

1. 构造一个知识点已有学习指南、另外两个槽位缺失；默认预检显示生成 2、保留 1。通过。
2. 切换“重新生成全部”，显示 3 个可执行项并要求明确确认。通过。
3. 模拟审核前版本变化，界面显示版本变化错误且请求携带精确版本/哈希。通过。
4. 刷新页面后恢复最近批次与进度。通过。

## 5. 验证记录

- `pytest -q backend/src/tests/standard_resources`：28 passed；随后增加权限依赖断言，`test_api_wiring.py` 为 3 passed。
- `tsx --test ...standardResources.test.ts ...standardLearningResourcesPresentation.test.ts`：12 passed。
- `playwright test tests/e2e/course-knowledge.spec.ts --project=desktop1366`：8 passed。
- `playwright test tests/e2e/classroom-catalog.spec.ts --project=desktop1366`：3 passed。
- `vite build`：通过，5251 modules transformed；仅有既存 chunk size/source-map 警告。
- `alembic heads`：`20260910_0021 (head)`。
- `quick_validate.py .../edu-standard-resource-bundle`：`Skill is valid!`。
- Python `compileall` 与目标文件 `git diff --check`：通过。

端到端使用确定性 API fixture 验证控制面与浏览器交互，没有调用收费的真实模型生成。真实模型内容质量仍需在部署环境做抽样验收；本轮自动化已验证 required-review 门槛和发布前哈希绑定。

补充说明：仓库全量 TypeScript 类型检查仍存在多个本功能之外的既有错误；本功能涉及代码已通过 Vite 生产构建、定向单元测试和浏览器测试。扩展课堂服务回归曾在既有“知识图谱第三层合并”用例停止（与本改动路径无关），本次改动直接影响的课堂持久化/生成路径测试已通过。
