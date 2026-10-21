# MAIC-UI 页面适配约定

生成完整 HTML，保留原生绘图和视觉；只负责中间实验展示和学科特有操作。宿主提供三阶段导航、下一步/回看、通用动作参数、提交、重试、反馈与操作记录，页面不要再造教学目录或 AI 发言。

宿主在页面脚本之前提供 window.EduExperiment。DOM 就绪后调用一次：

```js
EduExperiment.register({
  apply(state, command) {
    // state 是隔离副本；根据 command.action 和 command.input 返回新的完整可序列化状态。
    // 可以异步，但必须完成后 resolve。禁止后台循环修改状态。
    return state;
  },
  render(state, policy) {
    // 只绘图，不改变状态，不 dispatch；resize 使用最近的 state 重绘。
    // policy.phase、policy.allowed_actions、policy.busy 决定学科自定义交互是否开放。
  }
});
```

需要点击数组或连接器时调用 EduExperiment.dispatch(actionId, input)，不要直接改模型。等待动作结束；反馈由宿主显示，页面不自行推进教学任务。未开放动作由运行库拒绝。可用动作来自规格；数组、连接和参数计算由 apply 实现，不能只更新计数或颜色。物理模型明确单位、初始条件与公式，随机生成把实际样本和种子放进 state。

禁止修改宿主记录、引用外部脚本/资源或发起网络请求。运行库自动串行执行动作、限制输入、检查任务条件、上报前后快照。state 所有值必须是有限 JSON 数据，不能包含 DOM、函数、NaN 或 Infinity。绘图 canvas 按 DPR，使用 ResizeObserver；正文与标签清晰，手机无横向溢出。

原生科学模型与规格冲突时不可静默改规则；返回可诊断失败让生成服务修复。美化阶段必须保留 register/apply/render/dispatch 和所有状态语义。生成页面没有教学模型权限。
