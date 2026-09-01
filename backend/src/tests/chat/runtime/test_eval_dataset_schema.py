from pathlib import Path

from app.chat.evals.dataset import load_eval_dataset


DATASET = Path(__file__).parents[3] / "evals" / "teacher_agent" / "cases.yaml"


def test_teacher_agent_dataset_expands_to_at_least_eighty_stable_cases():
    dataset = load_eval_dataset(DATASET)
    cases = dataset.expand_cases()

    assert dataset.schema_version == "2026-08-09.v2"
    assert len(cases) >= 80
    assert len({case.case_id for case in cases}) == len(cases)
    assert all(case.case_id and case.question for case in cases)


def test_every_eval_case_declares_capability_and_structural_expectations():
    cases = load_eval_dataset(DATASET).expand_cases()

    for case in cases:
        assert case.capability.source_mode in {
            "none", "course_auto", "selected_documents"
        }
        assert case.expected.intent
        assert case.expected.plan_actions
        if case.capability.source_mode == "selected_documents":
            assert case.capability.selected_doc_ids


def test_dataset_contains_all_required_intelligence_dimensions():
    dataset = load_eval_dataset(DATASET)
    dimensions = {dimension for case in dataset.expand_cases() for dimension in case.dimensions}

    assert {
        "intent",
        "source_authority",
        "planning",
        "tool_policy",
        "long_dialogue",
        "clarification",
        "persona",
        "failure_recovery",
    }.issubset(dimensions)
