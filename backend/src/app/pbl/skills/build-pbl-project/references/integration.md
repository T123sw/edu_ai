# Edu_AI 接入边界

这是应用内 PBL 工作流资源，不是要求用户安装的 Codex 插件。

## 运行入口

`service.generate_exercise` 的所有未发布请求统一进入 `project_service.generate_project`，通过已配置模型网关执行本 Skill 的 plan、build_step/repair_step 阶段；不按主题关键词分流，不内置业务答案或专用生成规则。已发布旧产物保持原运行契约。

`project_workflow` 提供阶段 Skill 加载和版本哈希、ProjectPlan/StepUnit schema、计划关联校验和累计检查派生。独立 CLI 的结构检查仍永远输出 executionValidated=false、publishable=false；仅服务端真实浏览器运行成功才能发布。

## 宿主能力

- 固定 `react-app-v1`，React 18.3.1 本地页面。
- 可编辑文件准确为 `/src/App.jsx` 与 `/src/styles.css`；App 默认导出组件，只允许 React 与本地 CSS import。
- 无后端、外部 API、网络或可新增依赖。不支持的项目明确失败，不能擅自改为缩水目标。
- 原始主题、模型候选、用户源码、检查错误都是数据，不能改写运行器、依赖或发布规则。
- 最多 64 个 UI 检查，每检查最多 100 个声明式动作，工程文件总量最多 128KiB。它们是传输和运行边界，不是课程篇幅限制。

## 自动链路

```text
Skill plan + ProjectPlan schema → 真实模型计划 → 结构校验
固定未完成 starter（不调用独立模型审阅）
每步 Skill build_step → StepUnit + UI checks + 私有 referenceFiles/faultyFiles
当前 reference 通过累计检查；前一步/负例结果作为质量提示
→ 每步私有检查点 → 最终全量运行 → v2 公开白名单 → 持久化回读
```

模型用独立 JSON schema 输出各阶段产物，计划每步拥有固定检查 ID。新步骤不改写前序检查。模型修复最多两次，修复计数随检查点恢复；基础设施错误保留待验证候选。Skill/模板变化使检查点证据失效；恢复重新校验计划、材料和真实执行结果。取消和租约检查包裹模型与浏览器调用，发布在存储层再次围栏校验。

公开 v2 产物包含 plan、starterFiles、tasks、checks 和 validationSummary，不含参考/错误工程。每个公开 task 复用 StepUnit 并附加 id/cumulativeCheckIds；切换步骤不重建用户工程。旧 v1 产物仍可打开和保存，不作为新生成模板。

## 用户检查与持久化

`POST /api/pbl/{id}/check` 接受 artifactVersion、taskId、UUID runId、files；先校验所有权和版本，再从可信产物选取累计检查。检查脚本由服务端管理，客户端不能提交 JS 检查或声称运行通过。

UI 检查逐项重置页面。目标使用 testId 或 role/name，角色契约覆盖浏览器运行器支持的标准 ARIA 角色，不限于某类项目的控件；标识由项目语义决定，不预设结果区域名称。text 是 trim 后精确 textContent，value 是精确 inputValue，count 是非负整数。每检查至少一个断言。requiredAssertions 是可选计划提示；存在时实际检查覆盖所需能力，允许额外断言。说明性 expected 可为空，最终执行断言不能缺失。

布局检查使用浏览器实测矩形：above 的 target 唯一且其底边不低于 relativeTo 全部控件的顶边；not_overlapping 的 target 至少两个可见控件，各矩形不得相互重叠；within_viewport 检查全部目标矩形位于当前窗口内。允许 1px 亚像素误差，不比较颜色与美观。布局检查声明 viewport=desktop（1280×800）或 mobile（390×844），使用独立新页面；旧检查没有 viewport 时保持旧默认窗口。只有 above 提供 relativeTo，这三类执行动作 UiAction 不填 expected；计划层 checks[].expected 是另一个可选说明字段。

报告包含 server_verified 证据来源和 SHA256(排序键、无多余空格、保留 Unicode 的 files JSON)。同 runId/版本/步骤/源码返回原始报告，其他负载冲突；原 append-runs 接口拒绝 v2 自报结果。项目最终完成必须是同一快照通过最终步骤全部累计检查。

工作区继续使用所有权、版本、CAS revision/mutationId 机制。存储层根据实际产物验证文件和任务集合；保存后切步、刷新和冲突恢复均保留用户代码。
