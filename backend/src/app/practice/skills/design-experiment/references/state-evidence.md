# 状态含义与结束依据

适用于三个阶段的 snapshot，复用现有 JSON 传输，不增加模型调用、教学动作或生成审查。实现页面时把关键字段的时间范围、重置时机和实际结束分支保存在 `_teaching` 中。旧页面可以不提供；缺失意味着教学 Agent 不知道，不能为凑字段伪造事实。

```js
snapshot() {
  return {
    // 其余完整可恢复的学科状态……
    changedInCycle, cycle, done,
    _teaching: {
      version: 'edu-state-evidence/1',
      fields: [{
        path: ['changedInCycle'],
        meaning: '当前周期内是否发生变化；周期末复位后的 false 不代表刚结束的周期没有变化',
        scope: '当前周期，不是累计历史',
        reset_when: '周期结束或重新初始化时设为 false'
      }],
      transition: lastTransition, // 没有则 null
      completion: completionEvidence // 没有则 null
    }
  };
}
```

`fields` 解释容易混淆的关键量：局部标记、从 0 开始的索引/从 1 开始的显示轮次、累计计数、测量值有效范围等。按真实语义填写，不仅复述变量名。路径按快照对象取值；`scope` 说明时间或过程范围，`reset_when` 说明实际重置时机，永不重置也明确写出。这些是页面实现声明，不是科学认证。

每次实际操作更新 `lastTransition`；轮末/阶段末重置时先保存事件事实和重置前值，再修改变量。例如：

```js
const changedBeforeReset = changedInCycle;
const remainingBefore = remaining;
remaining -= 1;
cycle += 1;
changedInCycle = false;
lastTransition = {
  id: String(++transitionSequence), // 状态内的序号；restore 一并恢复
  kind: 'cycle_end',
  observations: {completedCycle:cycle, changedBeforeReset, remainingBefore, remainingAfter:remaining},
  resets: [{path:['changedInCycle'], before:changedBeforeReset, after:false, reason:'新周期局部标记复位'}]
};
const finished = !changedBeforeReset || remaining <= 1;
completionEvidence = {
  status: finished ? 'complete' : 'in_progress',
  code: !changedBeforeReset ? 'no_change' : remaining <= 1 ? 'remaining_region_complete' : 'continue',
  reason: !changedBeforeReset ? '刚结束的完整周期没有变化' : remaining <= 1 ? '剩余区间无需继续处理' : '继续处理剩余区间',
  basis: {changedBeforeReset, remainingAfter:remaining, completedCycle:cycle}
};
```

这是表达方式示例，不是所有学科的终止算法。采用实际实现的条件、值与分支；多种结束条件记录本次命中的那一种，不统一写成“无变化”。零数值不能自动视作未测量；如需区分测量与初值，明确保存测量有效标记和发生时点。

初始化、重置、更换输入时清空上一运行的 transition/completion（或写本次未完成证据），避免携带上次原因。snapshot/restore 保留数据和序号，恢复不新增事件。完成后停止动画仍保留完成依据；新操作后更新依据，不沿用已失效的原因。

探索动画每次有意义的学科状态变化后调用 `EduStage.observe('状态变化')`，轮末更新证据后也调用，确保瞬时事件不只依赖 300ms 采样。绘图/计时器 tick 不算教学动作，不从采样数推算比较/测量次数。transition 是最近上报的事件内容，多次采样携带相同 id 不表示事件再次发生。

状态文案和动作 facts 复用同一次计算的分支与值。不能用轮末复位后的标记生成“这一轮没有发生某事”的解释；显示完成原因引用 completionEvidence.reason，或用中性“已完成”。
