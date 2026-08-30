from pathlib import Path

from sqlalchemy import create_engine

from app.chat.memory.eval import evaluate_candidate_extractor, evaluate_retrieval
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.rule_extractor import RuleMemoryExtractor
from app.database import Base


def test_candidate_eval_meets_offline_quality_gate() -> None:
    dataset = (
        Path(__file__).parents[2]
        / "fixtures"
        / "memory"
        / "memory_candidate_cases.jsonl"
    )
    report = evaluate_candidate_extractor(dataset, RuleMemoryExtractor())

    assert report.case_count >= 12
    assert report.recall >= 0.85
    assert report.precision >= 0.85
    assert report.protected_fact_rejection_rate == 1.0
    assert report.false_write_rate <= 0.1


def test_retrieval_eval_meets_quality_and_isolation_gates() -> None:
    dataset = (
        Path(__file__).parents[2]
        / "fixtures"
        / "memory"
        / "memory_retrieval_cases.jsonl"
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    report = evaluate_retrieval(dataset, SqlAlchemyMemoryRepository(engine))

    assert report.case_count == 10
    assert report.recall_at_1 >= 0.9
    assert report.recall_at_3 == 1.0
    assert report.mean_reciprocal_rank >= 0.9
    assert report.isolation_violation_rate == 0.0
