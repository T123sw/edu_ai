"""Transactional persistence for versioned learning assessments."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4

from .models import (
    AssessmentAnswerRecord,
    AssessmentAssignmentRecord,
    AssessmentAttemptRecord,
    AssessmentItemRecord,
    AssessmentRecord,
    AssessmentReviewRecord,
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
                    submission_idempotency_key TEXT,
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
            attempt_columns = {
                str(row[1])
                for row in self._connection.execute("PRAGMA table_info(assessment_attempts)")
            }
            if "submission_idempotency_key" not in attempt_columns:
                self._connection.execute(
                    "ALTER TABLE assessment_attempts ADD COLUMN submission_idempotency_key TEXT"
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

    def get_or_create_assignment(
        self,
        *,
        task_id: str,
        course_id: str,
        student_id: str,
        assessment_version_id: str,
        max_attempts: int,
    ) -> AssessmentAssignmentRecord:
        if self._postgres:
            return self._repository.get_or_create_assignment(
                task_id=task_id,
                course_id=course_id,
                student_id=student_id,
                assessment_version_id=assessment_version_id,
                max_attempts=max_attempts,
            )
        existing = self.get_assignment(course_id=course_id, task_id=task_id, student_id=student_id)
        if existing is not None:
            return existing
        record = AssessmentAssignmentRecord(
            assessment_assignment_id=f"asa_{uuid4().hex}",
            task_id=task_id,
            course_id=course_id,
            student_id=student_id,
            assessment_version_id=assessment_version_id,
            cycle_number=1,
            max_attempts=max_attempts,
        )
        with self._lock:
            try:
                self._connection.execute(
                    """
                    INSERT INTO assessment_assignments(
                        assessment_assignment_id, task_id, course_id, student_id,
                        assessment_version_id, cycle_number, max_attempts, attempts_used,
                        best_attempt_id, best_final_score, result, answers_revealed_at,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.assessment_assignment_id, record.task_id, record.course_id,
                        record.student_id, record.assessment_version_id, record.cycle_number,
                        record.max_attempts, record.attempts_used, record.best_attempt_id,
                        record.best_final_score, record.result, record.answers_revealed_at,
                        record.created_at, record.updated_at,
                    ),
                )
                self._connection.commit()
            except sqlite3.IntegrityError:
                self._connection.rollback()
                existing = self.get_assignment(
                    course_id=course_id, task_id=task_id, student_id=student_id
                )
                if existing is None:
                    raise
                return existing
        return record

    def get_assignment(
        self, *, course_id: str, task_id: str, student_id: str
    ) -> AssessmentAssignmentRecord | None:
        if self._postgres:
            return self._repository.get_assignment(
                course_id=course_id, task_id=task_id, student_id=student_id
            )
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM assessment_assignments
                WHERE course_id=? AND task_id=? AND student_id=?
                ORDER BY cycle_number DESC LIMIT 1
                """,
                (course_id, task_id, student_id),
            ).fetchone()
        return self._assignment_from_row(row) if row else None

    def list_assignments(
        self, *, course_id: str, task_id: str
    ) -> list[AssessmentAssignmentRecord]:
        if self._postgres:
            return self._repository.list_assignments(course_id=course_id, task_id=task_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM assessment_assignments
                WHERE course_id=? AND task_id=? ORDER BY student_id, cycle_number DESC
                """,
                (course_id, task_id),
            ).fetchall()
        latest = {}
        for row in rows:
            latest.setdefault(str(row["student_id"]), self._assignment_from_row(row))
        return list(latest.values())

    def create_attempt(
        self, assignment: AssessmentAssignmentRecord
    ) -> AssessmentAttemptRecord:
        if self._postgres:
            return self._repository.create_attempt(assignment)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            active = self._connection.execute(
                """
                SELECT * FROM assessment_attempts
                WHERE assessment_assignment_id=? AND status='in_progress'
                ORDER BY attempt_number DESC LIMIT 1
                """,
                (assignment.assessment_assignment_id,),
            ).fetchone()
            if active is not None:
                self._connection.commit()
                return self._attempt_from_row(active)
            row = self._connection.execute(
                "SELECT * FROM assessment_assignments WHERE assessment_assignment_id=?",
                (assignment.assessment_assignment_id,),
            ).fetchone()
            if row is None:
                self._connection.rollback()
                raise AssessmentStoreError("ASSIGNMENT_NOT_FOUND", "Assessment assignment was not found")
            if int(row["attempts_used"]) >= int(row["max_attempts"]):
                self._connection.rollback()
                raise AssessmentStoreError("ATTEMPTS_EXHAUSTED", "No scored attempts remain")
            attempt = AssessmentAttemptRecord.new(
                assignment_id=assignment.assessment_assignment_id,
                assessment_version_id=assignment.assessment_version_id,
                task_id=assignment.task_id,
                course_id=assignment.course_id,
                student_id=assignment.student_id,
                attempt_number=int(row["attempts_used"]) + 1,
            )
            self._connection.execute(
                """
                INSERT INTO assessment_attempts(
                    attempt_id, assessment_assignment_id, assessment_version_id,
                    task_id, course_id, student_id, attempt_number, status,
                    draft_revision, submitted_at, auto_score, final_score, result,
                    submission_idempotency_key,
                    invalidated_at, invalidated_by, invalidation_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.attempt_id, attempt.assignment_id, attempt.assessment_version_id,
                    attempt.task_id, attempt.course_id, attempt.student_id,
                    attempt.attempt_number, attempt.status, attempt.draft_revision,
                    attempt.submitted_at, attempt.auto_score, attempt.final_score,
                    attempt.result, attempt.submission_idempotency_key,
                    attempt.invalidated_at, attempt.invalidated_by,
                    attempt.invalidation_reason, attempt.created_at, attempt.updated_at,
                ),
            )
            self._connection.commit()
        return attempt

    def get_attempt(self, attempt_id: str) -> AssessmentAttemptRecord | None:
        if self._postgres:
            return self._repository.get_attempt(attempt_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM assessment_attempts WHERE attempt_id=?", (attempt_id,)
            ).fetchone()
        return self._attempt_from_row(row) if row else None

    def save_answers(
        self,
        attempt_id: str,
        student_id: str,
        answers: dict[str, dict],
        *,
        expected_revision: int,
    ) -> AssessmentAttemptRecord:
        if self._postgres:
            return self._repository.save_answers(
                attempt_id, student_id, answers, expected_revision=expected_revision
            )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT * FROM assessment_attempts WHERE attempt_id=?", (attempt_id,)
            ).fetchone()
            if row is None or str(row["student_id"]) != student_id:
                self._connection.rollback()
                raise AssessmentStoreError("ATTEMPT_NOT_FOUND", "Assessment attempt was not found")
            if str(row["status"]) != "in_progress":
                self._connection.rollback()
                raise AssessmentStoreError("ATTEMPT_IMMUTABLE", "Submitted attempts cannot be edited")
            if int(row["draft_revision"]) != int(expected_revision):
                self._connection.rollback()
                raise AssessmentStoreError("ATTEMPT_REVISION_CONFLICT", "Assessment attempt has changed")
            now = utc_now()
            for item_id, answer in answers.items():
                self._connection.execute(
                    """
                    INSERT INTO assessment_answers(
                        answer_id, attempt_id, assessment_item_id, answer_json,
                        artifact_refs_json, auto_score, ai_suggestion_json,
                        final_score, review_status, updated_at
                    ) VALUES (?, ?, ?, ?, '[]', NULL, NULL, NULL, 'ungraded', ?)
                    ON CONFLICT(attempt_id, assessment_item_id) DO UPDATE SET
                        answer_json=excluded.answer_json, updated_at=excluded.updated_at
                    """,
                    (f"ans_{uuid4().hex}", attempt_id, item_id, _json(answer), now),
                )
            self._connection.execute(
                "UPDATE assessment_attempts SET draft_revision=draft_revision+1, updated_at=? WHERE attempt_id=?",
                (now, attempt_id),
            )
            self._connection.commit()
        return self.get_attempt(attempt_id)

    def list_answers(self, attempt_id: str) -> list[AssessmentAnswerRecord]:
        if self._postgres:
            return self._repository.list_answers(attempt_id)
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM assessment_answers WHERE attempt_id=? ORDER BY assessment_item_id",
                (attempt_id,),
            ).fetchall()
        return [self._answer_from_row(row) for row in rows]

    def finalize_attempt(
        self,
        attempt_id: str,
        *,
        answer_scores: dict[str, float | None],
        status: str,
        auto_score: float | None,
        final_score: float | None,
        result: str | None,
        idempotency_key: str,
    ) -> AssessmentAttemptRecord:
        if self._postgres:
            return self._repository.finalize_attempt(
                attempt_id, answer_scores=answer_scores, status=status,
                auto_score=auto_score, final_score=final_score, result=result,
                idempotency_key=idempotency_key,
            )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT * FROM assessment_attempts WHERE attempt_id=?", (attempt_id,)
            ).fetchone()
            if row is None:
                self._connection.rollback()
                raise AssessmentStoreError("ATTEMPT_NOT_FOUND", "Assessment attempt was not found")
            if str(row["status"]) != "in_progress":
                self._connection.commit()
                return self._attempt_from_row(row)
            now = utc_now()
            for item_id, score in answer_scores.items():
                self._connection.execute(
                    """
                    UPDATE assessment_answers SET auto_score=?, final_score=?, review_status=?, updated_at=?
                    WHERE attempt_id=? AND assessment_item_id=?
                    """,
                    (score, score, "graded" if score is not None else "pending_review", now, attempt_id, item_id),
                )
            self._connection.execute(
                """
                UPDATE assessment_attempts SET status=?, submitted_at=?, auto_score=?,
                    final_score=?, result=?, submission_idempotency_key=?, updated_at=?
                    WHERE attempt_id=?
                """,
                (status, now, auto_score, final_score, result, idempotency_key, now, attempt_id),
            )
            assignment = self._connection.execute(
                "SELECT * FROM assessment_assignments WHERE assessment_assignment_id=?",
                (str(row["assessment_assignment_id"]),),
            ).fetchone()
            best_score = assignment["best_final_score"]
            best_attempt_id = assignment["best_attempt_id"]
            if final_score is not None and (best_score is None or final_score > float(best_score)):
                best_score = final_score
                best_attempt_id = attempt_id
            assignment_result = str(assignment["result"])
            if result in {"passed", "mastered"}:
                assignment_result = result if assignment_result != "mastered" else assignment_result
            elif result == "pending_review" and assignment_result not in {"passed", "mastered"}:
                assignment_result = "pending_review"
            elif assignment_result == "not_attempted":
                assignment_result = "needs_retry"
            self._connection.execute(
                """
                UPDATE assessment_assignments SET attempts_used=attempts_used+1,
                    best_attempt_id=?, best_final_score=?, result=?, updated_at=?
                WHERE assessment_assignment_id=?
                """,
                (best_attempt_id, best_score, assignment_result, now, str(row["assessment_assignment_id"])),
            )
            self._connection.commit()
        return self.get_attempt(attempt_id)

    def list_attempts(self, assignment_id: str) -> list[AssessmentAttemptRecord]:
        if self._postgres:
            return self._repository.list_attempts(assignment_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM assessment_attempts WHERE assessment_assignment_id=?
                ORDER BY attempt_number
                """,
                (assignment_id,),
            ).fetchall()
        return [self._attempt_from_row(row) for row in rows]

    def reveal_assignment_answers(
        self, assignment_id: str
    ) -> AssessmentAssignmentRecord:
        if self._postgres:
            return self._repository.reveal_assignment_answers(assignment_id)
        with self._lock:
            now = utc_now()
            cursor = self._connection.execute(
                """
                UPDATE assessment_assignments
                SET answers_revealed_at=COALESCE(answers_revealed_at, ?), updated_at=?
                WHERE assessment_assignment_id=?
                """,
                (now, now, assignment_id),
            )
            if cursor.rowcount == 0:
                self._connection.rollback()
                raise AssessmentStoreError(
                    "ASSIGNMENT_NOT_FOUND", "Assessment assignment was not found"
                )
            self._connection.commit()
            row = self._connection.execute(
                "SELECT * FROM assessment_assignments WHERE assessment_assignment_id=?",
                (assignment_id,),
            ).fetchone()
        return self._assignment_from_row(row)

    def apply_review(
        self,
        attempt_id: str,
        reviews: list[AssessmentReviewRecord],
        *,
        final_score: float,
        result: str,
    ) -> AssessmentAttemptRecord:
        if self._postgres:
            return self._repository.apply_review(
                attempt_id, reviews, final_score=final_score, result=result
            )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            attempt = self._connection.execute(
                "SELECT * FROM assessment_attempts WHERE attempt_id=?", (attempt_id,)
            ).fetchone()
            if attempt is None:
                self._connection.rollback()
                raise AssessmentStoreError("ATTEMPT_NOT_FOUND", "Assessment attempt was not found")
            now = utc_now()
            for review in reviews:
                cursor = self._connection.execute(
                    """
                    UPDATE assessment_answers
                    SET final_score=?, review_status='graded', updated_at=?
                    WHERE attempt_id=? AND assessment_item_id=?
                    """,
                    (review.new_score, now, attempt_id, review.assessment_item_id),
                )
                if cursor.rowcount == 0:
                    self._connection.rollback()
                    raise AssessmentStoreError("INVALID_REVIEW_ITEM", "Review item was not found")
                self._connection.execute(
                    """
                    INSERT INTO assessment_reviews(
                        review_id, attempt_id, assessment_item_id, reviewer_id,
                        previous_score, new_score, reason_code, comment_private,
                        comment_student_visible, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        review.review_id, review.attempt_id, review.assessment_item_id,
                        review.reviewer_id, review.previous_score, review.new_score,
                        review.reason_code, review.comment_private,
                        review.comment_student_visible, review.created_at,
                    ),
                )
            self._connection.execute(
                """
                UPDATE assessment_attempts
                SET status='graded', final_score=?, result=?, updated_at=?
                WHERE attempt_id=?
                """,
                (final_score, result, now, attempt_id),
            )
            assignment_id = str(attempt["assessment_assignment_id"])
            best = self._connection.execute(
                """
                SELECT attempt_id, final_score, result FROM assessment_attempts
                WHERE assessment_assignment_id=? AND status='graded'
                    AND final_score IS NOT NULL AND invalidated_at IS NULL
                ORDER BY final_score DESC, attempt_number ASC LIMIT 1
                """,
                (assignment_id,),
            ).fetchone()
            if best is not None:
                self._connection.execute(
                    """
                    UPDATE assessment_assignments
                    SET best_attempt_id=?, best_final_score=?, result=?, updated_at=?
                    WHERE assessment_assignment_id=?
                    """,
                    (best["attempt_id"], best["final_score"], best["result"], now, assignment_id),
                )
            self._connection.commit()
        return self.get_attempt(attempt_id)

    def list_reviews(self, attempt_id: str) -> list[AssessmentReviewRecord]:
        if self._postgres:
            return self._repository.list_reviews(attempt_id)
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM assessment_reviews WHERE attempt_id=? ORDER BY created_at, review_id",
                (attempt_id,),
            ).fetchall()
        return [self._review_from_row(row) for row in rows]

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

    @staticmethod
    def _assignment_from_row(row: sqlite3.Row) -> AssessmentAssignmentRecord:
        return AssessmentAssignmentRecord(
            assessment_assignment_id=str(row["assessment_assignment_id"]),
            task_id=str(row["task_id"]), course_id=str(row["course_id"]),
            student_id=str(row["student_id"]),
            assessment_version_id=str(row["assessment_version_id"]),
            cycle_number=int(row["cycle_number"]), max_attempts=int(row["max_attempts"]),
            attempts_used=int(row["attempts_used"]),
            best_attempt_id=str(row["best_attempt_id"]) if row["best_attempt_id"] else None,
            best_final_score=float(row["best_final_score"]) if row["best_final_score"] is not None else None,
            result=str(row["result"]),
            answers_revealed_at=str(row["answers_revealed_at"]) if row["answers_revealed_at"] else None,
            created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _review_from_row(row: sqlite3.Row) -> AssessmentReviewRecord:
        return AssessmentReviewRecord(
            review_id=str(row["review_id"]),
            attempt_id=str(row["attempt_id"]),
            assessment_item_id=str(row["assessment_item_id"]) if row["assessment_item_id"] else None,
            reviewer_id=str(row["reviewer_id"]),
            previous_score=float(row["previous_score"]) if row["previous_score"] is not None else None,
            new_score=float(row["new_score"]) if row["new_score"] is not None else None,
            reason_code=str(row["reason_code"]),
            comment_private=str(row["comment_private"]),
            comment_student_visible=str(row["comment_student_visible"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _attempt_from_row(row: sqlite3.Row) -> AssessmentAttemptRecord:
        return AssessmentAttemptRecord(
            attempt_id=str(row["attempt_id"]), assignment_id=str(row["assessment_assignment_id"]),
            assessment_version_id=str(row["assessment_version_id"]), task_id=str(row["task_id"]),
            course_id=str(row["course_id"]), student_id=str(row["student_id"]),
            attempt_number=int(row["attempt_number"]), status=str(row["status"]),
            draft_revision=int(row["draft_revision"]),
            submitted_at=str(row["submitted_at"]) if row["submitted_at"] else None,
            auto_score=float(row["auto_score"]) if row["auto_score"] is not None else None,
            final_score=float(row["final_score"]) if row["final_score"] is not None else None,
            result=str(row["result"]) if row["result"] else None,
            submission_idempotency_key=(
                str(row["submission_idempotency_key"])
                if row["submission_idempotency_key"] else None
            ),
            invalidated_at=str(row["invalidated_at"]) if row["invalidated_at"] else None,
            invalidated_by=str(row["invalidated_by"]) if row["invalidated_by"] else None,
            invalidation_reason=str(row["invalidation_reason"]) if row["invalidation_reason"] else None,
            created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _answer_from_row(row: sqlite3.Row) -> AssessmentAnswerRecord:
        return AssessmentAnswerRecord(
            answer_id=str(row["answer_id"]), attempt_id=str(row["attempt_id"]),
            assessment_item_id=str(row["assessment_item_id"]),
            answer=dict(json.loads(row["answer_json"])),
            artifact_refs=list(json.loads(row["artifact_refs_json"])),
            auto_score=float(row["auto_score"]) if row["auto_score"] is not None else None,
            ai_suggestion=dict(json.loads(row["ai_suggestion_json"])) if row["ai_suggestion_json"] else None,
            final_score=float(row["final_score"]) if row["final_score"] is not None else None,
            review_status=str(row["review_status"]), updated_at=str(row["updated_at"]),
        )

    def close(self) -> None:
        if self._postgres:
            return
        with self._lock:
            self._connection.close()
