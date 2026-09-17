# 学习 Agent P4：理解检查、偏好与摘要

日期：2026-09-17。代码及隔离环境验收完成，尚未启用业务环境。基线检查点 `dce6c013`；所有开发测试日志保留在 [P4 日志目录](artifacts/learning-agent-p4)。

## 实现

- 检查优先读取题库并保存独立题目快照；不能确定旧格式答案时不猜选项。生成检查使用无工具模型与严格结构校验。前端只收到题干/选项，答案与评价标准保存在服务端。
- 作答 ID 幂等、不同载荷冲突、非法选项/版本拒绝；保存作答后才评价。客观题按稳定 option ID 集合批改；主观题评价失败保留答案，可刷新或重试评价。跳过没有理解证据，答错不改变完成标记、不锁导航。
- 原题快照及历史作答不随资料更新重新批改。原资料版本缺失时仍可查看本人已保存的题目/作答，并显示来源不可用；不能使用新版正文替代旧来源来提交新评价。撤权仍拒绝访问。
- 检查提交/评价更新事实修订与 outbox。目标判断只使用当前适用资料版本、目标映射和可解释评价；正向充分性还需要显式版本化检查规则。重复同一道题不能累计为不同检查。无规则的旧课程保留本题反馈，不自动得出整个节点已掌握。
- `read_learning_preferences`、`update_learning_preference`、`offer_understanding_check` 按 P4 开关挂载。写工具有稳定操作 ID 与持久化回执；恢复时先对账已提交偏好的回执，再核对 epoch，不重复写入。模型失败不抹掉已经保存的检查或偏好。
- 长期偏好复用 `AgentMemoryItem`、`UserProfileFact` 与审计表；显式全局/课程作用域、字段修订与 CAS。当前原话必须包含长期设置/删除意图，值直接来自原话；一次性、否定、假设及引用式表述不能触发隐含全局写入。表单为直接授权。
- 删除/更正与来源抑制、memory_epoch、摘要失效及 memory outbox 同事务。上下文、跨节点历史检索、旧摘要提交、最后回答提交均检查来源/epoch。旧后台抽取不能复活或覆盖学习偏好；已有记忆删除入口同步参与失效处理。
- 近期上下文只选完整成功轮次，最多 8 轮；当前/先修/最多两个问题相关节点使用事实摘要，不拼其他节点聊天。中文检索使用词项与连续二字片段，稳定排序。P4 全模型输入以 UTF-8 字节保守限制在 16,000（包含挂载 schema）；超过工具上下文预算时收束为最终回答，仍超限则明确失败，不能裁掉用户问题或伪装完整上下文。
- 长对话摘要使用无工具模型，保留近期四轮和全部数据库原文；逐项来源 ID 校验、memory_epoch/facts_revision/CAS 拒绝旧结果。摘要失败继续用近期消息，独立后台 worker 消费答疑 outbox，不阻塞答疑队列。
- 教学观察仅作为带当前消息来源的 `hypothesis` 保存，不修改自评或成绩；用户可以标记已解决或不准确。界面提供检查、作答恢复、偏好查看/修改/删除；真实个人中心也接入全局及课程偏好。

## 验证记录

局部测试：检查与偏好 14 passed，摘要 4 passed；扩展迁移/并发失效测试 24 passed；新增真实工具回执与恢复测试纳入最终回归。首次完整回归为 154 passed、2 failed、1 skipped；失败来自旧题来源版本不可读取时阻断历史作答查看，已修复为读取保存快照并标注来源状态，保留原失败日志。

浏览器前两项通过（可跳过检查、作答恢复、偏好删除/账号隔离）；另追加实际个人中心入口验证。首轮浏览器定位器将结果与解释文本合并匹配而失败，已拆分状态文本节点，并保留失败日志。

最终验证：`full-second.log` **160 passed、1 skipped**（SQLite 不适用的跨进程旧用例）；随后边界修正与增补测试分别为 `memory-final.log` **30 passed**、`summary-final.log` **6 passed**、`checks-manifest-final.log` **30 passed**、`partial-success.log` **2 passed**。包含题目更新历史恢复、manifest 检查目标/必需活动映射、同消息不同偏好字段的独立删除、原始历史保留、无工具模型摘要、写操作成功但回答失败的可见回执。以上数量有重复覆盖，不相加冒充唯一测试数。

`browser-third.log` **3 passed**；前端单测 **9 passed**；局部 TypeScript、修改范围 ESLint、Python 编译与 `git diff --check` 通过。整体旧播放器链的历史类型问题沿用 P3 范围说明；未声称全仓类型检查通过。

关键命令：

```bash
# 仓库根，显式隔离 PostgreSQL URL；完整输出写入上述日志
PYTHONPATH=backend/src python -m pytest backend/src/tests/self_learning backend/src/tests/test_self_learning.py backend/src/tests/database/test_alembic_revision_chain.py backend/src/tests/chat/memory/test_memory_repository.py backend/src/tests/chat/memory/test_memory_api_e2e.py backend/src/tests/chat/memory/test_memory_e2e.py -q
# frontend
pnpm exec playwright test -c playwright.learning-enrichment.config.ts
pnpm exec tsc -p tsconfig.self-learning.json
pnpm exec eslint src/liveLearning src/selfLearning
```


## 默认关闭与后续

新增迁移 `20260917_0027`，开关 `LEARNING_ENRICHMENT_V1_ENABLED=false`，要求 P1—P3 持久化能力。未迁移业务库、未启用开关。

摘要只覆盖保存的来源区间；超过输入预算的更老区间未被宣称已压缩。memory outbox 保留失效事件，当前无外部向量索引，安全性来自同步状态/来源检查。准备任务提交及资源修订在 P5 实现；真实任务的完整对话—教学—生成—修改路径在 P6 验证。
