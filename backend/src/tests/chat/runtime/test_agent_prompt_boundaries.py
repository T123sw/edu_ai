from app.chat.runtime.nodes.prompts import build_system_content


def test_agent_prompt_defines_qa_resource_tool_and_truth_boundaries():
    prompt = build_system_content(None, actor_role="teacher")

    assert "【普通问答模式】" in prompt
    assert "RAG 或 Web 结果只是回答依据，不代表用户要求生成资源" in prompt
    assert "不得评价回答是否缺少图片、图表或教学环节" in prompt
    assert "【资源任务模式】" in prompt
    assert "只有当前轮 generate_* 工具成功返回非空 task_id" in prompt
    assert "不得声称任务已提交、已启动或正在后台生成" in prompt


def test_teacher_prompt_uses_collaborative_adaptive_answer_style():
    prompt = build_system_content(None, actor_role="teacher")

    assert "教研协作伙伴" in prompt
    assert "专业、清晰、自然、完整" in prompt
    assert "根据问题本身和上下文自行决定回答的详略" in prompt
    assert "不设置固定字数、段落数量或回答模板" in prompt
    assert "不刻意压缩必要的解释" in prompt
    assert "使用简洁、行动导向的表达" not in prompt


def test_student_prompt_keeps_guided_learning_persona():
    prompt = build_system_content(None, actor_role="student")

    assert "学生的引导式教学助手" in prompt
    assert "教研协作伙伴" not in prompt
