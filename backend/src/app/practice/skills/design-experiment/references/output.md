# 输出约定

服务附带的 JSON Schema 是字段依据。模型仅填写 ExperimentSpec，平台追加 identity/provenance/verification。三个阶段以 demo_steps、tasks、exploration_prompts 组织；checkpoints 保存完整初始状态，阶段互相独立。任务 checkpoint 为 null 时继承上一任务实际状态，否则显式恢复指定条件。

Condition 的 path/right_path 是属性段数组，根必须是 before、after 或 input。before/after 为本次尝试起终状态，input 为提交动作参数（显式提交使用最近动作参数）。支持 eq/ne/lt/lte/gt/gte/contains/near；near 使用绝对 tolerance。right_path 非空时优先取另一条路径，否则比较 value。没有复杂表达式、代码执行或由模型运行时临时补出的规则。路径缺失得到 unknown，不算答错。

例如检查操作后的比较次数：`{"path":["after","comparisons"],"op":"eq","value":1}`；检查当前数组和操作前相同：`{"path":["after","array"],"op":"eq","right_path":["before","array"]}`。demo_steps.assertions、tasks.checks、validation_cases.assertions 都使用这种完整路径。只有 state_fields.path 是相对状态的字段路径，例如 `["comparisons"]`，不要混用。

演示可先观察初始状态：此步骤 commands 为 `[]`，仍要提供解释和初始状态 assertions。不要为满足格式而重复比较、修改计数或虚构无意义动作；后续操作步骤列出真实 commands，整个演示应展示实际的状态变化。

动作 ID、任务 ID、演示 ID 必须唯一。每个任务 objective 必须引用 objectives 中的原文。每个客观任务都需要通过与失败 validation_cases。用例 assertions 检查本次提交瞬间、回滚或进入下一任务之前的状态。失败回滚另外由运行验收器核对，恢复到本次尝试起点。需要准备动作的任务使用 explicit_submit，避免每个中间动作被错误地判为整个任务。

schema 文件由 experiment/contracts.py 导出到 references/schema.json，不手工维护第二套字段。

教学服务预留期，rubric 只能放在最后一个任务，并提供 expected=awaiting_review 的用例；不能期待 pass/fail。运行首版最多16个演示步骤、8个代表任务、24个验收用例。每轮最多2000条语义事件、约1.5MB记录；达到上限时保存后新开一轮，不丢弃已有历史。

## 提交方式必须二选一

- 选择一次就应得到反馈：`{"submission":"on_action","submit_action":"select","allowed_actions":["select"]}`。submit_action 是已开放的真实动作 ID。
- 需要先比较、交换等多次操作，再由用户确认：`{"submission":"explicit_submit","submit_action":null,"allowed_actions":["compare","swap"]}`。可以省略 submit_action；宿主自动提供「提交这次尝试」按钮，不要再填写自动提交动作，也不要额外生成只为推进任务的 next/submit 动作。

以冒泡排序为例，单次「是否交换」选择适合 on_action；手动完成一个比较交换过程后再确认，适合 explicit_submit。自由探索不靠任务提交推进。不要将两种提交方式同时赋给同一任务。
