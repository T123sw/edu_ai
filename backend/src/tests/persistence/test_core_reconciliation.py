from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session

from app.database import Base, User
from app.database.legacy_importer import (
    apply_legacy_core_snapshot,
    build_legacy_core_snapshot,
)


def _reconcile(session: Session, snapshot):
    try:
        from app.persistence.reconciliation import reconcile_core_snapshot
    except ModuleNotFoundError:
        pytest.fail("core persistence reconciliation is not implemented")
    return reconcile_core_snapshot(session, snapshot)


def _snapshot(tmp_path: Path):
    users_path = tmp_path / "users.json"
    users_path.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "teacher-one",
                        "password_hash": "hash",
                        "role": "teacher",
                        "created_at": "2026-08-10T09:00:00+00:00",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    courses_root = tmp_path / "courses"
    course_root = courses_root / "algorithms"
    course_root.mkdir(parents=True)
    (course_root / "course_info.json").write_text(
        json.dumps(
            {
                "id": "algorithms",
                "title": "算法设计",
                "description": "课程",
                "created_by": "teacher-one",
                "objectives": ["掌握算法"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (course_root / "metadata.json").write_text(
        json.dumps(
            {
                "created_at": "2026-08-10T09:00:00+00:00",
                "updated_at": "2026-08-10T09:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    memberships_path = tmp_path / "memberships.json"
    memberships_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "memberships": [
                    {
                        "course_id": "algorithms",
                        "user_id": "teacher-one",
                        "role": "owner",
                        "joined_at": "2026-08-10T09:00:00+00:00",
                        "added_by": "teacher-one",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return build_legacy_core_snapshot(
        users_path=users_path,
        courses_root=courses_root,
        memberships_path=memberships_path,
    )


def test_reconciliation_reports_matching_core_snapshot(tmp_path: Path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    snapshot = _snapshot(tmp_path)
    with Session(engine) as session:
        apply_legacy_core_snapshot(session, snapshot)
        session.commit()
        report = _reconcile(session, snapshot)

    assert report.as_dict() == {
        "ok": True,
        "domains": {
            "users": {
                "source_count": 1,
                "target_count": 1,
                "missing_in_database": [],
                "extra_in_database": [],
                "mismatched": [],
            },
            "courses": {
                "source_count": 1,
                "target_count": 1,
                "missing_in_database": [],
                "extra_in_database": [],
                "mismatched": [],
            },
            "objectives": {
                "source_count": 1,
                "target_count": 1,
                "missing_in_database": [],
                "extra_in_database": [],
                "mismatched": [],
            },
            "memberships": {
                "source_count": 1,
                "target_count": 1,
                "missing_in_database": [],
                "extra_in_database": [],
                "mismatched": [],
            },
        },
    }


def test_reconciliation_identifies_mismatched_user_without_exposing_fields(
    tmp_path: Path,
):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    snapshot = _snapshot(tmp_path)
    with Session(engine) as session:
        apply_legacy_core_snapshot(session, snapshot)
        session.execute(
            update(User)
            .where(User.user_id == "teacher-one")
            .values(role="admin")
        )
        session.commit()
        report = _reconcile(session, snapshot)

    payload = report.as_dict()
    assert payload["ok"] is False
    assert payload["domains"]["users"]["mismatched"] == ["teacher-one"]
    assert "hash" not in json.dumps(payload)


def test_reconciliation_cli_returns_success_for_matching_data(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'parity.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    snapshot = _snapshot(tmp_path)
    with Session(engine) as session:
        apply_legacy_core_snapshot(session, snapshot)
        session.commit()
    try:
        from app.persistence.reconcile_cli import main
    except ModuleNotFoundError:
        pytest.fail("core reconciliation CLI is not implemented")

    exit_code = main(
        [
            "--database-url",
            database_url,
            "--users-json",
            str(tmp_path / "users.json"),
            "--courses-root",
            str(tmp_path / "courses"),
            "--memberships-json",
            str(tmp_path / "memberships.json"),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["ok"] is True
