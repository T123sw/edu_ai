from app.chat.workflows.lesson_plan.edit_runtime import LessonPlanEditRuntime


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def invoke(self, prompt):
        self.calls.append(prompt)
        return FakeResponse(self.content)


def test_lesson_plan_edit_runtime_rewrites_only_the_target_field():
    runtime = LessonPlanEditRuntime(llm=FakeLLM('["能说出分数的意义"]'))
    result = runtime.run(
        question="重写教学目标",
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan", "version_id": "v1"},
        source_artifact={
            "artifact_id": "lp-1",
            "artifact_type": "lesson_plan",
            "title": "分数的意义教案.json",
            "content": {
                "title": "分数的意义",
                "objectives": ["理解分数的意义"],
                "process": [{"step": "导入", "goal": "联系生活经验"}],
            },
        },
    )

    lesson_plan_artifact = result["artifacts"][0]
    assert lesson_plan_artifact["content"]["objectives"] == ["能说出分数的意义"]
    assert lesson_plan_artifact["content"]["process"][0]["goal"] == "联系生活经验"


def test_lesson_plan_edit_runtime_rewrites_generic_plan_field():
    runtime = LessonPlanEditRuntime(llm=FakeLLM('["掌握分数大小比较的判断方法"]'))
    result = runtime.run(
        question="重写教学重点",
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan", "version_id": "v1"},
        source_artifact={
            "artifact_id": "lp-1",
            "artifact_type": "lesson_plan",
            "title": "分数的意义教案.json",
            "content": {
                "title": "分数的意义",
                "keyPoints": ["理解分数的意义和比较"],
                "process": [{"step": "导入", "goal": "联系生活经验"}],
            },
        },
    )

    lesson_plan_artifact = result["artifacts"][0]
    assert lesson_plan_artifact["content"]["keyPoints"] == ["掌握分数大小比较的判断方法"]
    assert lesson_plan_artifact["content"]["process"][0]["goal"] == "联系生活经验"


def test_lesson_plan_edit_runtime_returns_candidate_confirmation_before_edit():
    runtime = LessonPlanEditRuntime(llm=FakeLLM('{"unexpected": true}'))
    result = runtime.run(
        question="把活动部分改一下",
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan", "version_id": "v1"},
        source_artifact={
            "artifact_id": "lp-1",
            "artifact_type": "lesson_plan",
            "title": "分数的意义教案.json",
            "content": {
                "title": "分数的意义",
                "process": [
                    {"step": "小组活动", "goal": "合作探究"},
                    {"step": "活动总结", "goal": "归纳方法"},
                ],
            },
        },
    )

    assert result["workflow"]["status"] == "awaiting_input"
    assert "我还没有开始修改" in result["message"]["content"]
    assert "小组活动" in result["message"]["content"]
    assert "活动总结" in result["message"]["content"]


def test_lesson_plan_edit_runtime_returns_clarification_for_unclear_target():
    runtime = LessonPlanEditRuntime(llm=FakeLLM('{"unexpected": true}'))
    result = runtime.run(
        question="优化一下这个教案",
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan", "version_id": "v1"},
        source_artifact={
            "artifact_id": "lp-1",
            "artifact_type": "lesson_plan",
            "title": "分数的意义教案.json",
            "content": {
                "title": "分数的意义",
                "objectives": ["理解分数的意义"],
                "process": [{"step": "导入", "goal": "联系生活经验"}],
            },
        },
    )

    assert result["workflow"]["status"] == "awaiting_input"
    assert "请告诉我你想修改哪一部分" in result["message"]["content"]


def test_lesson_plan_edit_runtime_returns_artifact_question_fallback():
    runtime = LessonPlanEditRuntime(llm=FakeLLM('{"unexpected": true}'))
    result = runtime.run(
        question="这份教案的教学重点是什么？",
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan", "version_id": "v1"},
        source_artifact={
            "artifact_id": "lp-1",
            "artifact_type": "lesson_plan",
            "title": "分数的意义教案.json",
            "content": {
                "title": "分数的意义",
                "keyPoints": ["理解分数的意义"],
            },
        },
    )

    assert result["workflow"]["status"] == "awaiting_input"
    assert "当前引用的是教案内容" in result["message"]["content"]


def test_lesson_plan_edit_runtime_rewrites_only_the_target_outline_step():
    runtime = LessonPlanEditRuntime(llm=FakeLLM('{"step": "合作探究", "goal": "强化分数比较"}'))
    result = runtime.run(
        question="修改第2个环节",
        artifact_reference={"artifact_id": "outline-1", "artifact_type": "lesson_plan_outline", "version_id": "v1"},
        source_artifact={
            "artifact_id": "outline-1",
            "artifact_type": "lesson_plan_outline",
            "title": "分数的意义教案大纲.json",
            "content": {
                "basic_info": {"topic": "分数的意义"},
                "lesson_flow": [
                    {"step": "导入", "goal": "联系旧知"},
                    {"step": "合作探究", "goal": "比较分数大小"},
                ],
            },
        },
    )

    outline_artifact = result["artifacts"][0]
    assert outline_artifact["content"]["lesson_flow"][0]["goal"] == "联系旧知"
    assert outline_artifact["content"]["lesson_flow"][1]["goal"] == "强化分数比较"


def test_lesson_plan_edit_runtime_rewrites_outline_basic_info_field():
    runtime = LessonPlanEditRuntime(llm=FakeLLM('"40分钟"'))
    result = runtime.run(
        question="修改duration",
        artifact_reference={"artifact_id": "outline-1", "artifact_type": "lesson_plan_outline", "version_id": "v1"},
        source_artifact={
            "artifact_id": "outline-1",
            "artifact_type": "lesson_plan_outline",
            "title": "分数的意义教案大纲.json",
            "content": {
                "basic_info": {"topic": "分数的意义", "duration": "35分钟"},
                "lesson_flow": [
                    {"step": "导入", "goal": "联系旧知"},
                    {"step": "合作探究", "goal": "比较分数大小"},
                ],
            },
        },
    )

    outline_artifact = result["artifacts"][0]
    assert outline_artifact["content"]["basic_info"]["duration"] == "40分钟"
    assert outline_artifact["content"]["lesson_flow"][1]["goal"] == "比较分数大小"
