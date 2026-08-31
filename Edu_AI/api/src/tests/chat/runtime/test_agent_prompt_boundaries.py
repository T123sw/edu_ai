from app.chat.runtime.nodes.prompts import build_system_content


def test_agent_prompt_scopes_visual_self_check_to_explicit_resource_generation():
    prompt = build_system_content(None, actor_role="teacher")

    assert "普通问答只回答用户当前问题" in prompt
    assert "只有当前任务是用户明确要求的资源生成" in prompt
    assert "不得主动建议生成教案、PPT" in prompt
