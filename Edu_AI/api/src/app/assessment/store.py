"""Transactional persistence for versioned learning assessments."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path

from .models import (
    AssessmentItemRecord,
    AssessmentRecord,
    AssessmentVersionRecord,
    utc_now,
)


class AssessmentStoreError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class AssessmentStore:
    def __init__(self, database_path: str | Path):
        self._path = Path(database_path)
        self._postgres = (
            str(os.getenv("ASSESSMENT_PERSISTENCE_MODE", "sqlite")).strip().lower()
            == "postgres"
        )
        if self._postgres:
            from app.persistence.dependencies import get_postgres_assessment_repository

            self._repository = get_postgres_assessment_repository()
            self._connection = None
            self._lock = threading.RLock()
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(str(self._path), check_same_thread=False, timeout=5)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS assessments (
                    assessment_id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    task_id TEXT NOT NULL UNIQUE,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    current_version_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_assessments_course
                ON assessments(course_id, task_id);

                CREATE TABLE IF NOT EXISTS assessment_versions (
                    assessment_version_id TEXT PRIMARY KEY,
                    assessment_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    source_mode TEXT NOT NULL,
                    assessment_mode TEXT NOT NULL,
                    pass_threshold REAL NOT NULL,
                    mastery_threshold REAL NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    score_policy TEXT NOT NULL,
                    answer_reveal_policy TEXT NOT NULL,
                    shuffle_questions INTEGER NOT NULL,
                    shuffle_options INTEGER NOT NULL,
                    draft_revision INTEGER NOT NULL DEFAULT 0,
                    content_hash TEXT,
                    published_at TEXT,
                    published_by TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(assessment_id, version_number),
                    FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_assessment_versions_assessment
                ON assessment_versions(assessment_id, status, version_number);

                CREATE TABLE IF NOT EXISTS assessment_items (
                    assessment_item_id TEXT PRIMARY KEY,
                    assessment_version_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    item_type TEXT NOT NULL,
                    prompt_json TEXT NOT NULL,
                    scoring_key_json TEXT NOT NULL,
                    rubric_json TEXT NOT NULL,
                    max_score REAL NOT NULL,
                    grading_provider TEXT NOT NULL,
                    knowledge_point_ids_json TEXT NOT NULL,
                    source_refs_json TEXT NOT NULL,
                    source_exposure_state TEXT NOT NULL,
                    created_origin TEXT NOT NULL,
                    UNIQUE(assessment_version_id, position),
                    FOREIGN KEY(assessment_version_id) REFERENCES assessment_versions(assessment_version_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS assessment_assignments (
                    assessment_assignment_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    assessment_version_id TEXT NOT NULL,
                    cycle_number INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    attempts_used INTEGER NOT NULL DEFAULT 0,
                    best_attempt_id TEXT,
                    best_final_score REAL,
                    result TEXT NOT NULL,
                    answers_revealed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(task_id, student_id, cycle_number),
                    FOREIGN KEY(assessment_version_id) REFERENCES assessment_versions(assessment_version_id)
                );
                CREATE INDEX IF NOT EXISTS idx_assessment_assignments_course_student
                ON assessment_assignments(course_id, student_id, task_id);

                CREATE TABLE IF NOT EXISTS assessment_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    assessment_assignment_id TEXT NOT NULL,
                    assessment_version_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    draft_revision INTEGER NOT NULL DEFAULT 0,
                    submitted_at TEXT,
                    auto_score REAL,
                    final_score REAL,
                    result TEXT,
                    invalidated_at TEXT,
                    invalidated_by TEXT,
                    invalidation_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(assessment_assignment_id, attempt_number),
                    FOREIGN KEY(assessment_assignment_id) REFERENCES assessment_assignments(assessment_assignment_id) ON DELETE CASCADE,
                    FOREIGN KEY(assessment_version_id) REFERENCES assessment_versions(assessment_version_id)
                );
                CREATE INDEX IF NOT EXISTS idx_assessment_attempts_student_task
                ON assessment_attempts(student_id, task_id, status);

                CREATE TABLE IF NOT EXISTS assessment_answers (
                    answer_id TEXT PRIMARY KEY,
                    attempt_id TEXT NOT NULL,
                    assessment_item_id TEXT NOT NULL,
                    answer_json TEXT NOT NULL,
                    artifact_refs_json TEXT NOT NULL,
                    auto_score REAL,
                    ai_suggestion_json TEXT,
                    final_score REAL,
                    review_status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(attempt_id, assessment_item_id),
                    FOREIGN KEY(attempt_id) REFERENCES assessment_attempts(attempt_id) ON DELETE CASCADE,
                    FOREIGN KEY(assessment_item_id) REFERENCES assessment_items(assessment_item_id)
                );

                CREATE TABLE IF NOT EXISTS assessment_reviews (
                    review_id TEXT PRIMARY KEY,
                    attempt_id TEXT NOT NULL,
                    assessment_item_id TEXT,
                    reviewer_id TEXT NOT NULL,
                    previous_score REAL,
                    new_score REAL,
                    reason_code TEXT NOT NULL,
                    comment_private TEXT NOT NULL,
                    comment_student_visible TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(attempt_id) REFERENCES assessment_attempts(attempt_id) ON DELETE CASCADE,
                    FOREIGN KEY(assessment_item_id) REFERENCES assessment_items(assessment_item_id)
                );
                """
            )
            self._connection.commit()

    def create_draft(
        self,
        assessment: AssessmentRecord,
        version: AssessmentVersionRecord,
    ) -> AssessmentVersionRecord:
        if self._postgres:
            return self._repository.create_draft(assessment, version)
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute(
                    """
                    INSERT INTO assessments(
                        assessment_id, course_id, task_id, created_by, created_at,
                        current_version_id
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        assessment.assessment_id,
                        assessment.course_id,
                        assessment.task_id,
                        assessment.created_by,
                        assessment.created_at,
                        assessment.current_version_id,
                    ),
                )
                self._insert_version(version)
                self._connection.commit()
            except sqlite3.IntegrityError as exc:
                self._connection.rollback()
                raise AssessmentStoreError(
                    "TASK_ASSESSMENT_EXISTS", "A task can have only one assessment"
                ) from exc
        return version

    def _insert_version(self, version: AssessmentVersionRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO assessment_versions(
                assessment_version_id, assessment_id, version_number, status,
                source_mode, assessment_mode, pass_threshold, mastery_threshold,
                max_attempts, score_policy, answer_reveal_policy,
                shuffle_questions, shuffle_options, draft_revision, content_hash,
                published_at, published_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version.assessment_version_id,
                version.assessment_id,
                version.version_number,
                version.status,
                version.source_mode,
                version.assessment_mode,
                version.pass_threshold,
                version.mastery_threshold,
                version.max_attempts,
                version.score_policy,
                version.answer_reveal_policy,
                int(version.shuffle_questions),
                int(version.shuffle_options),
                version.draft_revision,
                version.content_hash,
                version.published_at,
                version.published_by,
                version.created_at,
            ),
        )

    def replace_draft_items(
        self,
        assessment_version_id: str,
        items: list[AssessmentItemRecord],
        *,
        expected_revision: int,
    ) -> AssessmentVersionRecord:
        if self._postgres:
            return self._repository.replace_draft_items(
                assessment_version_id,
                items,
                expected_revision=expected_revision,
            )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT * FROM assessment_versions WHERE assessment_version_id=?",
                (assessment_version_id,),
            ).fetchone()
            if row is None:
                self._connection.rollback()
                raise AssessmentStoreError("VERSION_NOT_FOUND", "Assessment version was not found")
            if str(row["status"]) != "draft":
                self._connection.rollback()
                raise AssessmentStoreError("VERSION_IMMUTABLE", "Published versions cannot be edited")
            if int(row["draft_revision"]) != int(expected_revision):
                self._connection.rollback()
                raise AssessmentStoreError(
                    "DRAFT_REVISION_CONFLICT", "Assessment draft has changed"
                )
            try:
                self._connection.execute(
                    "DELETE FROM assessment_items WHERE assessment_version_id=?",
                    (assessment_version_id,),
                )
                for item in items:
                    self._insert_item(item)
                self._connection.execute(
                    """
                    UPDATE assessment_versions
                    SET draft_revision=draft_revision + 1
                    WHERE assessment_version_id=?
                    """,
                    (assessment_version_id,),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        version = self.get_version(assessment_version_id)
        if version is None:
            raise AssessmentStoreError("VERSION_NOT_FOUND", "Assessment version was not found")
        return version

    def update_draft(
        self,
        version: AssessmentVersionRecord,
        items: list[AssessmentItemRecord],
        *,
        expected_revision: int,
    ) -> AssessmentVersionRecord:
        if self._postgres:
            return self._repository.update_draft(
                version, items, expected_revision=expected_revision
            )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT * FROM assessment_versions WHERE assessment_version_id=?",
                (version.assessment_version_id,),
            ).fetchone()
            if row is None:
                self._connection.rollback()
                raise AssessmentStoreError("VERSION_NOT_FOUND", "Assessment version was not found")
            if str(row["status"]) != "draft":
                self._connection.rollback()
                raise AssessmentStoreError("VERSION_IMMUTABLE", "Published versions cannot be edited")
            if int(row["draft_revision"]) != int(expected_revision):
                self._connection.rollback()
                raise AssessmentStoreError("DRAFT_REVISION_CONFLICT", "Assessment draft has changed")
            try:
                self._connection.execute(
                    """
                    UPDATE assessment_versions SET
                        source_mode=?, assessment_mode=?, pass_threshold=?, mastery_threshold=?,
                        max_attempts=?, answer_reveal_policy=?, shuffle_questions=?,
                        shuffle_options=?, draft_revision=draft_revision + 1
                    WHERE assessment_version_id=?
                    """,
                    (
                        version.source_mode,
                        version.assessment_mode,
                        version.pass_threshold,
                        version.mastery_threshold,
                        version.max_attempts,
                        version.answer_reveal_policy,
                        int(version.shuffle_questions),
                        int(version.shuffle_options),
                        version.assessment_version_id,
                    ),
                )
                self._connection.execute(
                    "DELETE FROM assessment_items WHERE assessment_version_id=?",
                    (version.assessment_version_id,),
                )
                for item in items:
                    self._insert_item(item)
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        updated = self.get_version(version.assessment_version_id)
        if updated is None:
            raise AssessmentStoreError("VERSION_NOT_FOUND", "Assessment version was not found")
        return updated

    def _insert_item(self, item: AssessmentItemRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO assessment_items(
                assessment_item_id, assessment_version_id, position, item_type,
                prompt_json, scoring_key_json, rubric_json, max_score,
                grading_provider, knowledge_point_ids_json, source_refs_json,
                source_exposure_state, created_origin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.assessment_item_id,
                item.assessment_version_id,
                item.position,
                item.item_type,
                _json(item.prompt),
                _json(item.scoring_key),
                _json(item.rubric),
                item.max_score,
                item.grading_provider,
                _json(item.knowledge_point_ids),
                _json(item.source_refs),
                item.source_exposure_state,
                item.created_origin,
            ),
        )

    def publish_version(
        self,
        assessment_version_id: str,
        *,
        published_by: str,
    ) -> AssessmentVersionRecord:
        if self._postgres:
            return self._repository.publish_version(
                assessment_version_id,
                published_by=published_by,
            )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT * FROM assessment_versions WHERE assessment_version_id=?",
                (assessment_version_id,),
            ).fetchone()
            if row is None:
                self._connection.rollback()
                raise AssessmentStoreError("VERSION_NOT_FOUND", "Assessment version was not found")
            if str(row["status"]) == "published":
                self._connection.commit()
                return self._version_from_row(row)
            items = self._connection.execute(
                """
                SELECT * FROM assessment_items
                WHERE assessment_version_id=? ORDER BY position, assessment_item_id
                """,
                (assessment_version_id,),
            ).fetchall()
            if not items:
                self._connection.rollback()
                raise AssessmentStoreError("ASSESSMENT_EMPTY", "Assessment requires at least one item")
            content_hash = self._content_hash(row, items)
            published_at = utc_now()
            self._connection.execute(
                """
                UPDATE assessment_versions
                SET status='published', content_hash=?, published_at=?, published_by=?
                WHERE assessment_version_id=? AND status='draft'
                """,
                (content_hash, published_at, published_by, assessment_version_id),
            )
            self._connection.execute(
                """
                UPDATE assessments SET current_version_id=? WHERE assessment_id=?
                """,
                (assessment_version_id, str(row["assessment_id"])),
            )
            self._connection.commit()
        version = self.get_version(assessment_version_id)
        if version is None:
            raise AssessmentStoreError("VERSION_NOT_FOUND", "Assessment version was not found")
        return version

    @staticmethod
    def _content_hash(version_row: sqlite3.Row, item_rows: list[sqlite3.Row]) -> str:
        payload = {
            "settings": {
                key: version_row[key]
                for key in (
                    "assessment_mode",
                    "pass_threshold",
                    "mastery_threshold",
                    "max_attempts",
                    "score_policy",
                    "answer_reveal_policy",
                    "shuffle_questions",
                    "shuffle_options",
                )
            },
            "items": [
                {
                    key: row[key]
                    for key in (
                        "assessment_item_id",
                        "position",
                        "item_type",
                        "prompt_json",
                        "scoring_key_json",
                        "rubric_json",
                        "max_score",
                        "grading_provider",
                        "knowledge_point_ids_json",
                        "source_refs_json",
                        "source_exposure_state",
                        "created_origin",
                    )
                }
                for row in item_rows
            ],
        }
        return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()

    def get_assessment_for_task(self, course_id: str, task_id: str) -> AssessmentRecord | None:
        if self._postgres:
            return self._repository.get_assessment_for_task(course_id, task_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM assessments WHERE course_id=? AND task_id=?",
                (course_id, task_id),
            ).fetchone()
        return self._assessment_from_row(row) if row else None

    def get_version(self, assessment_version_id: str) -> AssessmentVersionRecord | None:
        if self._postgres:
            return self._repository.get_version(assessment_version_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM assessment_versions WHERE assessment_version_id=?",
                (assessment_version_id,),
            ).fetchone()
        return self._version_from_row(row) if row else None

    def get_latest_version(self, assessment_id: str) -> AssessmentVersionRecord | None:
        if self._postgres:
            return self._repository.get_latest_version(assessment_id)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM assessment_versions
                WHERE assessment_id=? ORDER BY version_number DESC LIMIT 1
                """,
                (assessment_id,),
            ).fetchone()
        return self._version_from_row(row) if row else None

    def list_items(self, assessment_version_id: str) -> list[AssessmentItemRecord]:
        if self._postgres:
            return self._repository.list_items(assessment_version_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM assessment_items
                WHERE assessment_version_id=? ORDER BY position, assessment_item_id
                """,
                (assessment_version_id,),
            ).fetchall()
        return [self._item_from_row(row) for row in rows]

    @staticmethod
    def _assessment_from_row(row: sqlite3.Row) -> AssessmentRecord:
        return AssessmentRecord(
            assessment_id=str(row["assessment_id"]),
            course_id=str(row["course_id"]),
            task_id=str(row["task_id"]),
            created_by=str(row["created_by"]),
            created_at=str(row["created_at"]),
            current_version_id=(str(row["current_version_id"]) if row["current_version_id"] else None),
        )

    @staticmethod
    def _version_from_row(row: sqlite3.Row) -> AssessmentVersionRecord:
        return AssessmentVersionRecord(
            assessment_version_id=str(row["assessment_version_id"]),
            assessment_id=str(row["assessment_id"]),
            version_number=int(row["version_number"]),
            status=str(row["status"]),
            source_mode=str(row["source_mode"]),
            assessment_mode=str(row["assessment_mode"]),
            pass_threshold=float(row["pass_threshold"]),
            mastery_threshold=float(row["mastery_threshold"]),
            max_attempts=int(row["max_attempts"]),
            score_policy=str(row["score_policy"]),
            answer_reveal_policy=str(row["answer_reveal_policy"]),
            shuffle_questions=bool(row["shuffle_questions"]),
            shuffle_options=bool(row["shuffle_options"]),
            draft_revision=int(row["draft_revision"]),
            content_hash=str(row["content_hash"]) if row["content_hash"] else None,
            published_at=str(row["published_at"]) if row["published_at"] else None,
            published_by=str(row["published_by"]) if row["published_by"] else None,
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _item_from_row(row: sqlite3.Row) -> AssessmentItemRecord:
        return AssessmentItemRecord(
            assessment_item_id=str(row["assessment_item_id"]),
            assessment_version_id=str(row["assessment_version_id"]),
            position=int(row["position"]),
            item_type=str(row["item_type"]),
            prompt=dict(json.loads(row["prompt_json"])),
            scoring_key=dict(json.loads(row["scoring_key_json"])),
            rubric=dict(json.loads(row["rubric_json"])),
            max_score=float(row["max_score"]),
            grading_provider=str(row["grading_provider"]),
            knowledge_point_ids=list(json.loads(row["knowledge_point_ids_json"])),
            source_refs=list(json.loads(row["source_refs_json"])),
            source_exposure_state=str(row["source_exposure_state"]),
            created_origin=str(row["created_origin"]),
        )

    def close(self) -> None:
        if self._postgres:
            return
        with self._lock:
            self._connection.close()
