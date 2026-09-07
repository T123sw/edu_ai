# 资料修改 Skill 接入验证

日期：2026-09-07。用户截图显示已引用《链表的实现》，问“这个文档写的什么”却得到占位回复“具体追问”。当前服务只有追问／修改补丁输出，缺少只读输出；本次补齐该分支并将修改规则固化为应用运行时技能。

交付：[edu-artifact-revision/SKILL.md](../../../../backend/skills/edu-artifact-revision/SKILL.md)。由 ArtifactRevisionService 从 backend/skills 加载 SYSTEM_PROMPT，不使用截断后的通用技能拼接。权限、版本与写入由代码守门；技能缺失时不调用模型、不写入。

流程：定位→鉴权和版本→读原文→只读／澄清／修改→精确补丁与类型校验→保存新版本→回执。只读 answered 不写版本；多动作混合、空文本、占位追问被拒绝并最多修正一次。澄清中插入只读问答保留原待操作及取消绑定。

## 验证结果

- skill-creator quick_validate：通过。
- 隔离后端回归：121 passed。覆盖原修改／版本测试、新只读零写入、读取后修改、澄清期间插问、混合动作拒绝、占位追问拒绝、技能缺失及流式／非流式映射。
- 前端 pnpm build：通过（18.73s），存在大包提示；未据此宣称全量类型检查通过。
- 真实模型：专用临时 JSON 资料，应用已配置的 get_fallback_llm；问“这个文档写的什么”得到与原文结构／头插／遍历一致的回答，版本仍为 v1。随后要求只追加头插复杂度说明，实际保存 v2，并比较确认其他文字不变。[合成资料及结果](evidence/2026-09-07-artifact-revision-skill/live.json)。不触碰截图中的真实资料。

复现：从 backend/src 执行 `PYTHONPATH=. python tests/chat/artifact_revision_skill_live_smoke.py /tmp/revision-skill-evidence`，需要项目模型配置。脚本先读取模型配置，再隔离资料持久化；输出只包含合成资料与结果，不含凭据。

后端回归使用既有隔离 runner 执行 tests/chat/test_artifact_revision.py、test_knowledge_context_clarification.py、test_reply_service_v2.py、test_reply_service_v2_stream.py。

## 边界

本次证明技能实际加载、服务读改流程及共享协议可用。未重新执行浏览器点击到真实后端的全链路，未部署或重启用户正在使用的服务；截图界面的实际运行版本仍需部署后验证。没有新增通用多工具 Agent 图或宣称八类资料的播放、评分、导出、发布全部通过。C 先前记录的长内容分章加载、混合进程写入和各类型使用验收缺口仍然存在。
