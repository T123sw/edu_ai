"""Dry-run/apply migration for development course memberships."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from app.services.course_membership_bootstrap import (
    CourseMembershipBootstrap,
    _default_course_ids,
    _default_users,
    get_course_membership_bootstrap,
)
from app.services.course_membership_store import CourseMembershipStore


@dataclass(frozen=True)
class MembershipMigrationReport:
    created: int
    updated: int
    unchanged: int
    applied: bool


def migrate_memberships(
    *,
    store: CourseMembershipStore,
    users: Iterable[Mapping[str, Any]],
    course_ids: Iterable[str],
    apply: bool,
) -> MembershipMigrationReport:
    resolved_users = list(users)
    resolved_course_ids = list(dict.fromkeys(str(item).strip() for item in course_ids if str(item).strip()))
    created = updated = unchanged = 0
    for course_id in resolved_course_ids:
        for user in resolved_users:
            user_id = str(user.get("username") or "").strip()
            if not user_id:
                unchanged += 1
                continue
            desired = CourseMembershipBootstrap._development_role(
                str(user.get("role") or "")
            )
            current = store.get(course_id, user_id)
            if current is None:
                created += 1
            elif current.role == "owner" or current.role == desired:
                unchanged += 1
            else:
                updated += 1

    if apply:
        summary = CourseMembershipBootstrap(
            store=store,
            enabled=True,
        ).sync_existing(users=resolved_users, course_ids=resolved_course_ids)
        created, updated, unchanged = (
            summary.created,
            summary.updated,
            summary.unchanged,
        )
    return MembershipMigrationReport(
        created=created,
        updated=updated,
        unchanged=unchanged,
        applied=apply,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    bootstrap = get_course_membership_bootstrap()
    report = migrate_memberships(
        store=bootstrap.store,
        users=_default_users(),
        course_ids=_default_course_ids(),
        apply=bool(args.apply),
    )
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
