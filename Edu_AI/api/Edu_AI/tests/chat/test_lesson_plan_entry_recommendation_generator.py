import json
from types import SimpleNamespace

from app.chat.application.lesson_plan_entry_recommendation_generator import LessonPlanEntryRecommendationGenerator


class PlainJsonOnlyLlm:
    def __init__(self):
        self.invoke_calls = []
        self.structured_call_count = 0

    def with_structured_output(self, *_args, **_kwargs):
        self.structured_call_count += 1
        raise AssertionError("function calling should not be used for lesson plan entry recommendations")

    def invoke(self, prompt):
        self.invoke_calls.append(prompt)
        return SimpleNamespace(
            content=json.dumps(
                {
                    "cards": [
                        {
                            "recommendation_type": "knowledge_building",
                            "topic": "Stochastic process definitions and examples",
                            "title": "Process concept lesson",
                            "description": "Builds concepts from the selected materials.",
                            "prompt_draft": "Create a lesson plan about stochastic process basics.",
                            "fit_score": "high",
                            "lesson_type": "New lesson",
                            "objective": "Help students understand stochastic process definitions.",
                            "key_points": ["Random variables indexed by time", "State space examples"],
                            "difficult_points": ["Distinguishing sample paths from distributions"],
                            "after_class_task": "Compare two stochastic-process examples from the materials.",
                            "style_hint": "Use concept scaffolding and examples.",
                        }
                    ]
                }
            )
        )


def test_lesson_plan_entry_recommendation_generator_uses_plain_json_invoke():
    llm = PlainJsonOnlyLlm()
    generator = LessonPlanEntryRecommendationGenerator(llm=llm)

    cards = generator.generate_recommendations(
        documents=[
            {
                "doc_id": "doc-1",
                "title": "Stochastic processes",
                "summary": "Introduces probability spaces and stochastic process definitions.",
            }
        ],
        recommendation_types=["knowledge_building"],
    )

    assert llm.structured_call_count == 0
    assert len(llm.invoke_calls) == 1
    assert cards == [
        {
            "recommendation_type": "knowledge_building",
            "topic": "Stochastic process definitions and examples",
            "title": "Process concept lesson",
            "description": "Builds concepts from the selected materials.",
            "prompt_draft": "Create a lesson plan about stochastic process basics.",
            "fit_score": "high",
            "lesson_type": "New lesson",
            "objective": "Help students understand stochastic process definitions.",
            "key_points": ["Random variables indexed by time", "State space examples"],
            "difficult_points": ["Distinguishing sample paths from distributions"],
            "after_class_task": "Compare two stochastic-process examples from the materials.",
            "style_hint": "Use concept scaffolding and examples.",
        }
    ]
