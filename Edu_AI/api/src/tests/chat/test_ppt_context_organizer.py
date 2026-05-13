from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.ppt_preparation import PptPreparationResult
from app.chat.orchestrator.ppt_context_organizer import PptContextOrganizer


def test_ppt_context_organizer_builds_core_slots_and_source_basis_from_generation_context():
    context = GenerationContext(
        conversation_id="conv-ppt-1",
        resource_type="ppt",
        summary_text="当前围绕网络安全入门课件展开讨论，希望面向初中学生做一套课堂展示。",
        current_topics=["网络安全入门"],
        user_goals=["生成PPT"],
        confirmed_facts=["受众是八年级学生", "目标是讲清基础防护意识"],
        constraints={
            "audience": "八年级学生",
            "objective": "讲清基础防护意识",
            "style": "简洁清晰",
            "theme": "校园科技风",
            "page_count": 8,
        },
        teaching_issues=["需要更贴近课堂表达"],
        student_signals=["学生对安全话题有兴趣"],
        evidence_points=[{"type": "note", "content": "课堂演示需要控制在 8 页左右"}],
        source_scope={"from_summary": True, "from_memory": True, "from_recent_messages": True},
    )

    result = PptContextOrganizer().organize(
        context=context,
        request_question="帮我做一个网络安全入门PPT",
    )

    assert result.topic == "网络安全入门"
    assert result.audience == "八年级学生"
    assert result.objective == "讲清基础防护意识"
    assert result.key_points[:2] == ["受众是八年级学生", "目标是讲清基础防护意识"]
    assert result.source_basis == ["conversation_summary", "conversation_memory", "recent_messages"]
    assert result.style == "简洁清晰"
    assert result.theme == "校园科技风"
    assert result.page_count == 8
    assert result.missing_core_fields == []


class StubStructuredLlm:
    def __init__(self, result: PptPreparationResult):
        self.result = result
        self.prompts: list[str] = []

    def with_structured_output(self, schema, method="function_calling"):
        assert schema is PptPreparationResult
        assert method == "function_calling"
        return self

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return self.result


def test_ppt_context_organizer_summarizes_context_with_llm_before_readiness_judgement():
    context = GenerationContext(
        conversation_id="conv-ppt-2",
        resource_type="ppt",
        summary_text="当前围绕 TCP 三次握手的课堂课件继续讨论。",
        current_topics=["TCP 三次握手"],
        user_goals=["生成PPT"],
        confirmed_facts=["希望讲清三次握手流程", "加入常见误区"],
        constraints={"page_count": 8},
        teaching_issues=[],
        student_signals=[],
        evidence_points=[],
        source_scope={"from_summary": True, "from_recent_messages": True},
    )
    llm = StubStructuredLlm(
        PptPreparationResult(
            topic="TCP 三次握手",
            audience="大一计算机专业学生",
            objective="课堂讲解",
            key_points=["连接建立过程", "常见误区", "抓包观察重点"],
            source_basis=["conversation_summary", "recent_messages"],
            style="讲授型",
            page_count=8,
            preparation_source="llm",
            preparation_model="fallback",
        )
    )

    result = PptContextOrganizer(llm=llm).organize(
        context=context,
        request_question="帮我做一份 TCP 三次握手 PPT",
    )

    assert llm.prompts
    prompt = llm.prompts[0]
    assert "请先基于当前会话总结出可用于生成逐页大纲的 preparation 结果" in prompt
    assert "recent_relevant_messages" in prompt
    assert result.topic == "TCP 三次握手"
    assert result.audience == "大一计算机专业学生"
    assert result.objective == "课堂讲解"
    assert result.key_points == ["连接建立过程", "常见误区", "抓包观察重点"]
    assert result.style == "讲授型"
    assert result.page_count == 8
    assert result.preparation_source == "llm"
    assert result.preparation_model == "fallback"


class StubQwenJsonLlm:
    model = "qwen3.5-plus"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(self, payload: str):
        self.payload = payload
        self.prompts: list[str] = []
        self.structured_calls = 0

    def with_structured_output(self, *_args, **_kwargs):
        self.structured_calls += 1
        raise AssertionError("qwen-compatible llm should not use function_calling structured output")

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return self.payload


def test_ppt_context_organizer_uses_raw_json_directly_for_qwen_compatible_models():
    context = GenerationContext(
        conversation_id="conv-ppt-qwen-1",
        resource_type="ppt",
        summary_text="围绕 Python 变量定义整理 PPT。",
        current_topics=["Python 变量定义"],
        user_goals=["生成 PPT"],
        confirmed_facts=["变量通过赋值定义", "变量名不能以数字开头"],
        constraints={},
        teaching_issues=[],
        student_signals=[],
        evidence_points=[],
        source_scope={"from_summary": True, "from_recent_messages": True},
    )
    llm = StubQwenJsonLlm(
        """```json
{
  "topic": "Python 变量定义",
  "audience": "编程初学者",
  "objective": "帮助学生理解变量定义与命名规则",
  "key_points": ["赋值即定义", "命名规则"],
  "source_basis": ["conversation_summary", "recent_messages"],
  "source_excerpts": ["变量通过赋值定义", "变量名不能以数字开头"],
  "page_count": 10,
  "preparation_source": "llm_raw_json",
  "preparation_model": "qwen3.5-plus"
}
```"""
    )

    result = PptContextOrganizer(llm=llm).organize(
        context=context,
        request_question="根据以上内容整理成 PPT",
    )

    assert llm.structured_calls == 0
    assert llm.prompts
    assert result.topic == "Python 变量定义"
    assert result.audience == "编程初学者"
    assert result.objective == "帮助学生理解变量定义与命名规则"
    assert result.key_points == ["赋值即定义", "命名规则"]
    assert result.preparation_source == "llm_raw_json"
    assert result.preparation_model == "qwen3.5-plus"


def test_ppt_context_organizer_defaults_page_count_to_soft_target_when_missing():
    context = GenerationContext(
        conversation_id="conv-ppt-3",
        resource_type="ppt",
        summary_text="围绕 AI Agent 入门做一份课堂 PPT。",
        current_topics=["AI Agent 入门"],
        user_goals=["生成PPT"],
        confirmed_facts=["面向大一学生", "目标是课堂讲解", "重点包括概念、架构、案例"],
        constraints={
            "audience": "大一学生",
            "objective": "课堂讲解",
        },
        teaching_issues=[],
        student_signals=[],
        evidence_points=[],
        source_scope={"from_summary": True, "from_memory": True},
    )

    result = PptContextOrganizer().organize(
        context=context,
        request_question="帮我生成一份 AI Agent 入门 PPT",
    )

    assert result.page_count == 18
