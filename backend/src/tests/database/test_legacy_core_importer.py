from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _fixture_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    users_path = tmp_path / "storage" / "users.json"
    memberships_path = tmp_path / "storage" / "course_memberships.json"
    courses_root = tmp_path / "course_data" / "courses"
    _write_json(
        users_path,
        {
            "users": [
                {
                    "username": "teacher",
                    "password_hash": "hash",
                    "role": "teacher",
                    "created_at": "2026-08-01T12:00:00",
                    "display_name": "唐老师",
                }
            ]
        },
    )
    _write_json(
        courses_root / "course-1" / "course_info.json",
        {
            "id": "course-1",
            "title": "计算思维",
            "description": "课程简介",
            "icon": "menu_book",
            "color": "#2563eb",
            "objectives": ["问题分解", "算法表达"],
            "knowledgeGraph": "cover-ref",
            "revision": 2,
            "created_by": "teacher",
        },
    )
    _write_json(
        courses_root / "course-1" / "metadata.json",
        {
            "created_at": "2026-08-02T08:00:00+00:00",
            "updated_at": "2026-08-03T09:30:00+00:00",
        },
    )
    _write_json(
        memberships_path,
        {
            "schema_version": 1,
            "memberships": [
                {
                    "course_id": "course-1",
                    "user_id": "teacher",
                    "role": "owner",
                    "joined_at": "2026-08-02T08:00:00+00:00",
                    "added_by": "development-auto-enroll",
                }
            ],
        },
    )
    return users_path, courses_root, memberships_path


def test_snapshot_preserves_legacy_payload_and_normalizes_relationships(tmp_path: Path) -> None:
    try:
        from app.database.legacy_importer import build_legacy_core_snapshot
    except ModuleNotFoundError as exc:  # RED: importer is not implemented yet.
        pytest.fail(f"legacy importer is missing: {exc}")

    users_path, courses_root, memberships_path = _fixture_paths(tmp_path)
    snapshot = build_legacy_core_snapshot(
        users_path=users_path,
        courses_root=courses_root,
        memberships_path=memberships_path,
    )

    assert snapshot.summary() == {
        "users": 1,
        "courses": 1,
        "objectives": 2,
        "memberships": 1,
        "warnings": [],
    }
    assert snapshot.users[0].user_id == "teacher"
    assert snapshot.users[0].raw_payload["display_name"] == "唐老师"
    assert snapshot.courses[0].course_id == "course-1"
    assert snapshot.courses[0].cover_image_ref == "cover-ref"
    assert snapshot.memberships[0].added_by == "development-auto-enroll"


def test_snapshot_rejects_membership_with_unknown_course(tmp_path: Path) -> None:
    from app.database.legacy_importer import (
        LegacyDataValidationError,
        build_legacy_core_snapshot,
    )

    users_path, courses_root, memberships_path = _fixture_paths(tmp_path)
    payload = json.loads(memberships_path.read_text(encoding="utf-8"))
    payload["memberships"][0]["course_id"] = "missing-course"
    _write_json(memberships_path, payload)

    with pytest.raises(LegacyDataValidationError, match="unknown course missing-course"):
        build_legacy_core_snapshot(
            users_path=users_path,
            courses_root=courses_root,
            memberships_path=memberships_path,
        )


def test_applying_snapshot_twice_is_idempotent(tmp_path: Path) -> None:
    from app.database import Base, Course, CourseMembership, CourseObjective, User
    from app.database.legacy_importer import apply_legacy_core_snapshot, build_legacy_core_snapshot

    users_path, courses_root, memberships_path = _fixture_paths(tmp_path)
    snapshot = build_legacy_core_snapshot(
        users_path=users_path,
        courses_root=courses_root,
        memberships_path=memberships_path,
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        first = apply_legacy_core_snapshot(session, snapshot)
        session.commit()
        second = apply_legacy_core_snapshot(session, snapshot)
        session.commit()

        assert first == snapshot.summary()
        assert second == snapshot.summary()
        assert session.scalar(select(func.count()).select_from(User)) == 1
        assert session.scalar(select(func.count()).select_from(Course)) == 1
        assert session.scalar(select(func.count()).select_from(CourseObjective)) == 2
        assert session.scalar(select(func.count()).select_from(CourseMembership)) == 1
