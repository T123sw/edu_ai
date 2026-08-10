from __future__ import annotations

import json
from pathlib import Path


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_cli_defaults_to_preview_without_database_connection(tmp_path: Path, capsys) -> None:
    from app.database.migrate_cli import main

    users = tmp_path / "users.json"
    courses = tmp_path / "courses"
    memberships = tmp_path / "memberships.json"
    _write(
        users,
        {
            "users": [
                {
                    "username": "teacher",
                    "password_hash": "hash",
                    "role": "teacher",
                    "created_at": "2026-08-01T00:00:00+00:00",
                }
            ]
        },
    )
    _write(
        courses / "course-1" / "course_info.json",
        {
            "id": "course-1",
            "title": "课程",
            "description": "",
            "icon": "menu_book",
            "color": "#2563eb",
            "objectives": [],
        },
    )
    _write(
        memberships,
        {
            "schema_version": 1,
            "memberships": [
                {
                    "course_id": "course-1",
                    "user_id": "teacher",
                    "role": "owner",
                    "joined_at": "2026-08-01T00:00:00+00:00",
                    "added_by": "teacher",
                }
            ],
        },
    )

    exit_code = main(
        [
            "--users-json",
            str(users),
            "--courses-root",
            str(courses),
            "--memberships-json",
            str(memberships),
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "mode": "preview",
        "users": 1,
        "courses": 1,
        "objectives": 0,
        "memberships": 1,
        "warnings": [],
    }
