import json
from types import SimpleNamespace

from app.chat.application.report_entry_recommendation_generator import ReportEntryRecommendationGenerator


class PlainJsonOnlyLlm:
    def __init__(self):
        self.invoke_calls = []
        self.structured_call_count = 0

    def with_structured_output(self, *_args, **_kwargs):
        self.structured_call_count += 1
        raise AssertionError("function calling should not be used for report entry recommendations")

    def invoke(self, prompt):
        self.invoke_calls.append(prompt)
        return SimpleNamespace(
            content=json.dumps(
                {
                    "cards": [
                        {
                            "recommendation_type": "summary",
                            "title": "Process overview",
                            "description": "Summarizes the selected materials.",
                            "prompt_draft": "Write a report about stochastic processes.",
                            "fit_score": "high",
                        }
                    ]
                }
            )
        )


def test_report_entry_recommendation_generator_uses_plain_json_invoke():
    llm = PlainJsonOnlyLlm()
    generator = ReportEntryRecommendationGenerator(llm=llm)

    cards = generator.generate_recommendations(
        documents=[
            {
                "doc_id": "doc-1",
                "title": "Stochastic processes",
                "summary": "Introduces probability spaces and stochastic process definitions.",
            }
        ],
        recommendation_types=["summary"],
    )

    assert llm.structured_call_count == 0
    assert len(llm.invoke_calls) == 1
    assert cards == [
        {
            "recommendation_type": "summary",
            "title": "Process overview",
            "description": "Summarizes the selected materials.",
            "prompt_draft": "Write a report about stochastic processes.",
            "fit_score": "high",
        }
    ]
