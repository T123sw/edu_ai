from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine

from app.chat.memory.eval import evaluate_candidate_extractor, evaluate_retrieval
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.rule_extractor import RuleMemoryExtractor
from app.database import Base


def main() -> None:
    tests_root = Path(__file__).resolve().parents[3] / "tests"
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    report = {
        "candidate_extraction": evaluate_candidate_extractor(
            tests_root / "fixtures" / "memory" / "memory_candidate_cases.jsonl",
            RuleMemoryExtractor(),
        ).model_dump(),
        "retrieval": evaluate_retrieval(
            tests_root / "fixtures" / "memory" / "memory_retrieval_cases.jsonl",
            SqlAlchemyMemoryRepository(engine),
        ).model_dump(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
