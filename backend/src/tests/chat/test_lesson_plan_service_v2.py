from types import SimpleNamespace

from app.chat.application.lesson_plan_service_v2 import (
    LessonPlanGenerationEngine,
    build_default_lesson_plan_engine,
)
from app.chat.legacy.legacy_chat_runtime import LegacyChatRuntime


class _StubResponse:
    def __init__(self, content):
        self.content = content


class _StubLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if not self._responses:
            raise AssertionError("No stub response left")
        return _StubResponse(self._responses.pop(0))


def test_lesson_plan_engine_returns_outline_when_generation_ready_without_existing_outline():
    llm = _StubLLM(
        [
            """
            ```json
            {
              "basic_info": {
                "topic": "分数的意义",
                "audience": "七年级",
                "duration": "45分钟",
                "lesson_type": "新授课"
              },
              "teaching_objectives": ["理解分数的意义", "会结合图示解释分数"],
              "key_and_hard_points": {
                "key_points": ["分数的意义"],
                "hard_points": ["单位“1”的理解"],
                "breakthrough_strategy": "通过图示和生活实例突破抽象概念"
              },
              "lesson_flow": [
                {
                  "step": "导入",
                  "goal": "建立生活情境",
                  "duration": "5分钟",
                  "teacher_activities": ["展示分蛋糕图片"],
                  "student_activities": ["观察并回答分配方式"],
                  "assessment": "口头提问"
                }
              ],
              "teaching_support": {
                "teaching_methods": ["情境导入", "启发式提问"],
                "teaching_aids": ["课件", "板书"],
                "board_plan": ["分数", "单位1"],
                "assessment_method": "课堂追问",
                "homework_preview": "完成课后练习"
              }
            }
            ```
            """
        ]
    )
    engine = LessonPlanGenerationEngine(llm=llm)

    result = engine.invoke(
        {
            "conversation_id": "conv-lesson-engine-1",
            "generation_ready": True,
            "soft_confirmed": True,
            "lesson_plan_slots": {
                "topic": "分数的意义",
                "audience": "七年级",
                "duration": "45分钟",
                "objective": "帮助学生理解分数的意义",
                "lesson_type": "新授课",
            },
            "lesson_plan_preparation_result": {
                "topic": "分数的意义",
                "audience": "七年级",
                "duration": "45分钟",
                "objective": "帮助学生理解分数的意义",
                "lesson_type": "新授课",
                "knowledge_points": ["分数的意义"],
                "key_points": ["分数的意义"],
                "hard_points": ["单位“1”的理解"],
                "class_profile": ["学生已有平均分配经验"],
            },
            "gathered_context": {
                "summary": "老师希望为七年级设计一节分数新授课",
                "confirmed_facts": ["学生能处理简单平均分配情境"],
                "teaching_issues": ["抽象概念不易建立"],
            },
            "readiness_decision": {"action": "strong_soft_confirm", "missing_critical_fields": []},
        }
    )

    assert result["status"] == "awaiting_human"
    assert result["phase"] == "outlining"
    assert result["lesson_plan_outline"]["basic_info"]["topic"] == "分数的意义"
    assert result["artifacts"][0]["artifact_type"] == "lesson_plan_outline"
    assert result["artifacts"][0]["title"] == "分数的意义-教案大纲.json"


def test_lesson_plan_engine_generates_structured_content_from_confirmed_outline():
    llm = _StubLLM(
        [
            """
            {
              "title": "分数的意义",
              "basicInfo": {
                "audience": "七年级",
                "duration": "45分钟",
                "lessonType": "新授课"
              },
              "objectives": ["理解分数的意义", "能结合图示表达分数"],
              "keyPoints": ["分数的意义"],
              "hardPoints": ["单位“1”的理解"],
              "teachingMethods": ["情境导入", "启发式提问"],
              "teachingAids": ["课件", "板书"],
              "process": [
                {
                  "step": "导入",
                  "goal": "建立生活联系",
                  "teacherActivities": ["展示分蛋糕情境", "追问如何平均分"],
                  "studentActivities": ["观察并口头回答"],
                  "duration": "5分钟",
                  "assessment": "追问学生是否能说出每份含义"
                }
              ],
              "boardPlan": ["分数", "单位1", "分子 分母"],
              "homework": "完成课后分数表示练习",
              "reflectionTips": ["关注学生是否把份数和整体混淆"]
            }
            """
        ]
    )
    engine = LessonPlanGenerationEngine(llm=llm)

    result = engine.invoke(
        {
            "conversation_id": "conv-lesson-engine-2",
            "generation_ready": True,
            "soft_confirmed": True,
            "lesson_plan_slots": {
                "topic": "分数的意义",
                "audience": "七年级",
                "duration": "45分钟",
                "objective": "帮助学生理解分数的意义",
                "lesson_type": "新授课",
            },
            "lesson_plan_preparation_result": {
                "topic": "分数的意义",
                "audience": "七年级",
                "duration": "45分钟",
                "objective": "帮助学生理解分数的意义",
                "lesson_type": "新授课",
            },
            "lesson_plan_outline": {
                "basic_info": {
                    "topic": "分数的意义",
                    "audience": "七年级",
                    "duration": "45分钟",
                    "lesson_type": "新授课",
                },
                "lesson_flow": [
                    {
                        "step": "导入",
                        "goal": "建立生活联系",
                        "duration": "5分钟",
                        "teacher_activities": ["展示分蛋糕情境"],
                        "student_activities": ["观察并回答"],
                        "assessment": "口头提问",
                    }
                ],
            },
            "readiness_decision": {"action": "resume_after_soft_confirm", "missing_critical_fields": []},
        }
    )

    assert result["status"] == "completed"
    assert result["phase"] == "generating"
    assert result["lesson_plan_content"]["title"] == "分数的意义"
    assert result["lesson_plan_content"]["process"][0]["step"] == "导入"
    assert result["artifacts"][0]["artifact_type"] == "lesson_plan"
    assert result["artifacts"][0]["title"] == "分数的意义-教案.json"


def test_lesson_plan_engine_returns_guidance_when_not_generation_ready():
    engine = LessonPlanGenerationEngine(llm=None)

    result = engine.invoke(
        {
            "generation_ready": False,
            "lesson_plan_slots": {"topic": "", "audience": "", "duration": "", "objective": "", "lesson_type": ""},
            "readiness_decision": {
                "action": "ask_objective_or_outline_basis",
                "missing_critical_fields": ["objective_or_outline_basis"],
                "question": "这节课希望学生学会什么，或者你想更偏知识讲解还是活动探究？",
            },
        }
    )

    assert result["status"] == "awaiting_human"
    assert result["phase"] == "asking"
    assert "这节课希望学生学会什么" in result["reply"]


def test_build_default_lesson_plan_engine_can_accept_explicit_llm():
    llm = _StubLLM(["{}"])
    engine = build_default_lesson_plan_engine(llm=llm)

    assert isinstance(engine, LessonPlanGenerationEngine)
    assert engine.llm is llm


def test_lesson_plan_engine_revises_outline_when_human_feedback_requests_changes():
    llm = _StubLLM(
        [
            """
            {
              "basic_info": {
                "topic": "分数的意义",
                "audience": "七年级",
                "duration": "45分钟",
                "lesson_type": "新授课"
              },
              "teaching_objectives": ["理解分数的意义", "会结合图示解释分数"],
              "key_and_hard_points": {
                "key_points": ["分数的意义"],
                "hard_points": ["单位“1”的理解"],
                "breakthrough_strategy": "先用生活案例导入，再通过小组讨论辨析单位“1”"
              },
              "lesson_flow": [
                {
                  "step": "导入",
                  "goal": "建立生活情境",
                  "duration": "5分钟",
                  "teacher_activities": ["展示分蛋糕情境"],
                  "student_activities": ["观察并回答"],
                  "assessment": "口头提问"
                },
                {
                  "step": "小组讨论",
                  "goal": "通过合作交流辨析不同分法",
                  "duration": "8分钟",
                  "teacher_activities": ["发放讨论任务单", "巡视并追问"],
                  "student_activities": ["分组讨论并汇报"],
                  "assessment": "小组汇报"
                }
              ],
              "teaching_support": {
                "teaching_methods": ["情境导入", "小组讨论"],
                "teaching_aids": ["课件", "任务单"],
                "board_plan": ["分数", "单位1", "不同分法"],
                "assessment_method": "课堂观察与汇报",
                "homework_preview": "完成分数情境练习"
              }
            }
            """
        ]
    )
    engine = LessonPlanGenerationEngine(llm=llm)

    result = engine.invoke(
        {
            "conversation_id": "conv-lesson-engine-4",
            "generation_ready": True,
            "soft_confirmed": True,
            "human_feedback": "增加一个小组讨论环节",
            "lesson_plan_slots": {
                "topic": "分数的意义",
                "audience": "七年级",
                "duration": "45分钟",
                "objective": "帮助学生理解分数的意义",
                "lesson_type": "新授课",
            },
            "lesson_plan_preparation_result": {
                "topic": "分数的意义",
                "audience": "七年级",
                "duration": "45分钟",
                "objective": "帮助学生理解分数的意义",
                "lesson_type": "新授课",
            },
            "lesson_plan_outline": {
                "basic_info": {
                    "topic": "分数的意义",
                    "audience": "七年级",
                    "duration": "45分钟",
                    "lesson_type": "新授课",
                },
                "lesson_flow": [
                    {
                        "step": "导入",
                        "goal": "建立生活联系",
                        "duration": "5分钟",
                        "teacher_activities": ["展示分蛋糕情境"],
                        "student_activities": ["观察并回答"],
                        "assessment": "口头提问",
                    }
                ],
            },
            "readiness_decision": {"action": "resume_after_soft_confirm", "missing_critical_fields": []},
        }
    )

    assert result["status"] == "awaiting_human"
    assert result["phase"] == "outlining"
    assert result["lesson_plan_outline"]["lesson_flow"][1]["step"] == "小组讨论"
    assert result["artifacts"][0]["artifact_type"] == "lesson_plan_outline"
    assert result.get("lesson_plan_content") is None


def test_lesson_plan_engine_fallback_content_preserves_list_shaped_outline_steps():
    engine = LessonPlanGenerationEngine(llm=None)

    result = engine.invoke(
        {
            "conversation_id": "conv-lesson-engine-3",
            "generation_ready": True,
            "soft_confirmed": True,
            "lesson_plan_slots": {
                "topic": "分数的意义",
                "audience": "七年级",
                "duration": "45分钟",
                "objective": "帮助学生理解分数的意义",
                "lesson_type": "新授课",
            },
            "lesson_plan_preparation_result": {
                "topic": "分数的意义",
                "audience": "七年级",
                "duration": "45分钟",
                "objective": "帮助学生理解分数的意义",
                "lesson_type": "新授课",
            },
            "lesson_plan_outline": [
                {
                    "title": "导入",
                    "summary": "联系生活经验引入分数",
                    "minutes": "5分钟",
                }
            ],
            "readiness_decision": {"action": "resume_after_soft_confirm", "missing_critical_fields": []},
        }
    )

    assert result["status"] == "completed"
    assert result["lesson_plan_content"]["title"] == "分数的意义"
    assert result["lesson_plan_content"]["process"][0]["step"] == "导入"
    assert result["lesson_plan_content"]["process"][0]["goal"] == "联系生活经验引入分数"
    assert result["lesson_plan_content"]["process"][0]["duration"] == "5分钟"


def test_lesson_plan_content_prompt_requires_concrete_classroom_actions():
    engine = LessonPlanGenerationEngine(llm=None)

    prompt = engine._build_content_prompt(
        outline={
            "basic_info": {"topic": "关羽的战绩与历史评价", "audience": "初中历史", "duration": "45分钟", "lesson_type": "新授课"},
            "lesson_flow": [
                {
                    "step": "新授/探究",
                    "goal": "基于史料梳理关羽主要战绩并分析其历史评价",
                    "duration": "25分钟",
                }
            ],
        },
        slots={"topic": "关羽的战绩与历史评价"},
        preparation={"class_profile": ["学生容易把演义形象当作史实"], "resource_constraints": ["课件", "史料节选"]},
    )

    assert "不要写假大空的套话" in prompt
    assert "可观察的学生产出" in prompt
    assert "问题链" in prompt
    assert "板书落点" in prompt
    assert "必做" in prompt and "选做" in prompt


def test_lesson_plan_outline_prompt_requires_activity_skeleton_protocol():
    engine = LessonPlanGenerationEngine(llm=None)

    prompt = engine._build_outline_prompt(
        slots={"topic": "用移项法解一元一次方程", "audience": "七年级", "duration": "45分钟", "lesson_type": "新授课"},
        preparation={"objective": "帮助学生理解移项变号的依据", "class_profile": ["学生容易把移项理解为随便搬项"]},
        gathered_context={"summary": "需要一节可直接上课的数学教案"},
    )

    assert "student_analysis" in prompt
    assert "已有基础" in prompt
    assert "认知困难" in prompt
    assert "常见误区" in prompt
    assert "key_questions" in prompt
    assert "expected_answers" in prompt
    assert "teacher_followups" in prompt
    assert "outputs" in prompt


def test_lesson_plan_engine_fallback_outline_contains_activity_skeleton_fields():
    engine = LessonPlanGenerationEngine(llm=None)

    result = engine.invoke(
        {
            "conversation_id": "conv-lesson-engine-6",
            "generation_ready": True,
            "soft_confirmed": True,
            "lesson_plan_slots": {
                "topic": "用移项法解一元一次方程",
                "audience": "七年级",
                "duration": "45分钟",
                "objective": "帮助学生理解移项变号的依据",
                "lesson_type": "新授课",
            },
            "lesson_plan_preparation_result": {
                "topic": "用移项法解一元一次方程",
                "audience": "七年级",
                "duration": "45分钟",
                "objective": "帮助学生理解移项变号的依据",
                "lesson_type": "新授课",
                "class_profile": ["学生已经会解 x+a=b 型方程", "容易把移项理解成简单搬项"],
                "key_points": ["掌握移项法的步骤"],
                "hard_points": ["解释移项变号的依据"],
            },
            "gathered_context": {"summary": "需要一节可直接上课的数学新授课教案"},
            "readiness_decision": {"action": "strong_soft_confirm", "missing_critical_fields": []},
        }
    )

    outline = result["lesson_plan_outline"]
    assert outline["student_analysis"]["已有基础"]
    assert outline["student_analysis"]["认知困难"]
    assert outline["student_analysis"]["常见误区"]
    assert outline["lesson_flow"][0]["key_questions"]
    assert outline["lesson_flow"][0]["expected_answers"]
    assert outline["lesson_flow"][0]["teacher_followups"]
    assert outline["lesson_flow"][0]["outputs"]


def test_lesson_plan_engine_fallback_content_adds_concrete_actions_and_tiered_homework():
    engine = LessonPlanGenerationEngine(llm=None)

    result = engine.invoke(
        {
            "conversation_id": "conv-lesson-engine-5",
            "generation_ready": True,
            "soft_confirmed": True,
            "lesson_plan_slots": {
                "topic": "关羽的战绩与历史评价",
                "audience": "初中历史",
                "duration": "45分钟",
                "objective": "帮助学生基于史料辨析关羽战绩与历史评价",
                "lesson_type": "新授课",
            },
            "lesson_plan_preparation_result": {
                "topic": "关羽的战绩与历史评价",
                "audience": "初中历史",
                "duration": "45分钟",
                "objective": "帮助学生基于史料辨析关羽战绩与历史评价",
                "lesson_type": "新授课",
                "key_points": ["梳理关羽主要战绩", "辨析历史评价与文学形象"],
                "hard_points": ["避免把《三国演义》情节直接当作史实"],
                "teaching_methods": ["史料研习", "对比分析", "小组讨论"],
                "assessment_method": "课堂追问与史料批注",
                "homework_preference": "分层作业",
            },
            "lesson_plan_outline": {
                "basic_info": {
                    "topic": "关羽的战绩与历史评价",
                    "audience": "初中历史",
                    "duration": "45分钟",
                    "lesson_type": "新授课",
                },
                "lesson_flow": [
                    {
                        "step": "新授/探究",
                        "goal": "基于史料梳理关羽主要战绩并分析其历史评价",
                        "duration": "25分钟",
                    }
                ],
                "teaching_support": {
                    "teaching_methods": ["史料研习", "对比分析", "小组讨论"],
                    "teaching_aids": ["课件", "史料节选"],
                    "board_plan": ["主要战绩", "史实评价", "文学形象"],
                    "assessment_method": "课堂追问与史料批注",
                    "homework_preview": "分层作业",
                },
                "key_and_hard_points": {
                    "key_points": ["梳理关羽主要战绩", "辨析历史评价与文学形象"],
                    "hard_points": ["避免把《三国演义》情节直接当作史实"],
                    "breakthrough_strategy": "借助史料对读，引导学生用证据支撑评价",
                },
            },
            "readiness_decision": {"action": "resume_after_soft_confirm", "missing_critical_fields": []},
        }
    )

    process_item = result["lesson_plan_content"]["process"][0]
    assert result["status"] == "completed"
    assert process_item["teacherActivities"]
    assert process_item["studentActivities"]
    assert "必做" in result["lesson_plan_content"]["homework"]
    assert "选做" in result["lesson_plan_content"]["homework"]
    assert any("史料" in item or "证据" in item for item in result["lesson_plan_content"]["reflectionTips"])


def test_lesson_plan_engine_content_normalization_ignores_instruction_like_title():
    llm = _StubLLM(
        [
            """
            {
              "title": "请基于已选文档《随机过程-概率论基础.pdf》和《随机过程-随机过程的基本概念.pdf》，组织一节单课时教案。首先生成教案大纲，再生成详细正文。课题：随机过程的基本概念。",
              "basicInfo": {
                "audience": "本科高年级",
                "duration": "45分钟",
                "lessonType": "新授课"
              },
              "objectives": ["理解随机过程的基本定义"],
              "process": []
            }
            """
        ]
    )
    engine = LessonPlanGenerationEngine(llm=llm)

    result = engine.invoke(
        {
            "conversation_id": "conv-lesson-engine-7",
            "generation_ready": True,
            "soft_confirmed": True,
            "lesson_plan_slots": {
                "topic": "随机过程的基本概念",
                "audience": "本科高年级",
                "duration": "45分钟",
                "objective": "帮助学生理解随机过程的基本定义和双重性",
                "lesson_type": "新授课",
            },
            "lesson_plan_preparation_result": {
                "topic": "随机过程的基本概念",
                "audience": "本科高年级",
                "duration": "45分钟",
                "objective": "帮助学生理解随机过程的基本定义和双重性",
                "lesson_type": "新授课",
            },
            "lesson_plan_outline": {
                "basic_info": {
                    "topic": "随机过程的基本概念",
                    "audience": "本科高年级",
                    "duration": "45分钟",
                    "lesson_type": "新授课",
                },
                "lesson_flow": [],
            },
            "readiness_decision": {"action": "resume_after_soft_confirm", "missing_critical_fields": []},
        }
    )

    assert result["lesson_plan_content"]["title"] == "随机过程的基本概念"


def test_legacy_runtime_exposes_lesson_plan_engine():
    marker = object()

    class _Backend:
        @staticmethod
        def get_lesson_plan_engine():
            return marker

    runtime = LegacyChatRuntime(backend=_Backend())

    assert runtime.get_lesson_plan_engine() is marker
