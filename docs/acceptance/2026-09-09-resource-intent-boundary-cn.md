# 新建资源与旧文档修改的意图边界

截图显示旧报告编辑状态把新建请求当成了报告内容修改。本次在前一轮交接修复上补齐目标类型和历史边界，覆盖“当前要求报告，但历史在处理教案”的情况。

- 本轮 current_question 与 previous_edit_request 分开传递；旧修改稿、旧任务和右侧预览不构成本轮编辑授权。
- 模型的新建决定必须明确 resource_type 和 subject，由代码校验结构并传给 Harness。新报告不能沿用旧教案类型，同主题同类型也不代表修改。
- 明确局部增删、补例子、重新生成某一段属于修改原文；新建资源或跨类型转换进入独立目标资源流程，保留源文件。真正有歧义才澄清，不依赖关键词分类。
- 新建报告走报告大纲与后续确认；新建教案走教学方案；编辑原文保留修改稿预览、确认保存的边界。

验证：相关后端 247 项通过；最终类型传递/历史分离边界补验 16 项通过（与前者重叠）。真实模型 7/7 场景通过，包括新建同类型报告、旧教案修改任务后新报告、旧报告编辑后新教案、从教案新建报告、补例子、重写局部、只读问答。真实 HTTP SSE 用旧报告引用发起新报告请求，实际调用 organize_report_content / draft_report_outline，返回 report 大纲并等待确认，原文不变，未自动提交正文或保存旧修改稿。本轮验证范围到正确大纲交付，未将其记为报告正文生成完成。

证据在 evidence/2026-09-09-resource-intent-boundary/。模型边界实测可用 scripts/verify-resource-intents.py --output <隔离目录>；真实报告规划可用 scripts/verify-harness-resources.py --kinds report --plan-only --reference-material <报告JSON> --output <隔离目录> --port <空闲端口>。
