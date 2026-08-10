"""Transactional SQLite persistence for course learning interactions."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

from .models import (
    EventWriteResult,
    LearningEventRecord,
    LearningTaskRecord,
    TaskProgressRecord,
    utc_now,
)


class LearningStore:
    def __init__(self, database_path: str | Path):
        self._path = Path(database_path)
        self._lock = threading.RLock()
        self._postgres = (
            str(os.getenv("LEARNING_PERSISTENCE_MODE", "sqlite")).strip().lower()
            == "postgres"
        )
        if self._postgres:
            from app.persistence.dependencies import get_postgres_learning_repository

            self._repository = get_postgres_learning_repository()
            self._connection = None
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
            timeout=5,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS learning_tasks (
                    task_id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    instructions TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    resource_refs_json TEXT NOT NULL,
                    knowledge_point_ids_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    published_by TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_learning_tasks_course_status
                ON learning_tasks(course_id, status, created_at DESC);

                CREATE TABLE IF NOT EXISTS learning_events (
                    event_id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    progress_percent INTEGER NOT NULL,
                    resource_ref_json TEXT,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES learning_tasks(task_id)
                );
                CREATE INDEX IF NOT EXISTS idx_learning_events_student_course
                ON learning_events(student_id, course_id, occurred_at DESC);

                CREATE TABLE IF NOT EXISTS task_progress (
                    task_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_percent INTEGER NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, student_id),
                    FOREIGN KEY(task_id) REFERENCES learning_tasks(task_id)
                );
                CREATE INDEX IF NOT EXISTS idx_task_progress_course_student
                ON task_progress(course_id, student_id, updated_at DESC);
                """
            )
            self._connection.commit()

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> LearningTaskRecord:
        return LearningTaskRecord(
            task_id=str(row["task_id"]),
            course_id=str(row["course_id"]),
            title=str(row["title"]),
            instructions=str(row["instructions"]),
            created_by=str(row["created_by"]),
            resource_refs=list(json.loads(row["resource_refs_json"] or "[]")),
            knowledge_point_ids=list(json.loads(row["knowledge_point_ids_json"] or "[]")),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            published_at=str(row["published_at"]) if row["published_at"] else None,
            published_by=str(row["published_by"]) if row["published_by"] else None,
        )

    @staticmethod
    def _progress_from_row(row: sqlite3.Row) -> TaskProgressRecord:
        return TaskProgressRecord(
            task_id=str(row["task_id"]),
            course_id=str(row["course_id"]),
            student_id=str(row["student_id"]),
            status=str(row["status"]),
            progress_percent=int(row["progress_percent"]),
            started_at=str(row["started_at"]) if row["started_at"] else None,
            completed_at=str(row["completed_at"]) if row["completed_at"] else None,
            updated_at=str(row["updated_at"]),
        )

    def create_task(self, task: LearningTaskRecord) -> LearningTaskRecord:
        if self._postgres:
            return self._repository.create_task(task)
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO learning_tasks(
                    task_id, course_id, title, instructions, created_by,
                    resource_refs_json, knowledge_point_ids_json, status,
                    created_at, published_at, published_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.course_id,
                    task.title,
                    task.instructions,
                    task.created_by,
                    json.dumps(task.resource_refs, ensure_ascii=False, separators=(",", ":")),
                    json.dumps(task.knowledge_point_ids, ensure_ascii=False, separators=(",", ":")),
                    task.status,
                    task.created_at,
                    task.published_at,
                    task.published_by,
                ),
            )
            self._connection.commit()
        return task

    def get_task(self, task_id: str, *, course_id: str) -> LearningTaskRecord | None:
        if self._postgres:
            return self._repository.get_task(str(task_id), str(course_id))
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM learning_tasks WHERE task_id=? AND course_id=?",
                (str(task_id), str(course_id)),
            ).fetchone()
        return self._task_from_row(row) if row else None

    def list_tasks(
        self,
        course_id: str,
        *,
        statuses: set[str] | None = None,
        limit: int | None = None,
    ) -> list[LearningTaskRecord]:
        if self._postgres:
            return self._repository.list_tasks(
                str(course_id), statuses=statuses, limit=limit
            )
        parameters: list[object] = [str(course_id)]
        where = "course_id=?"
        normalized_statuses = sorted(str(item) for item in statuses or set() if str(item))
        if normalized_statuses:
            placeholders = ",".join("?" for _ in normalized_statuses)
            where += f" AND status IN ({placeholders})"
            parameters.extend(normalized_statuses)
        sql = f"SELECT * FROM learning_tasks WHERE {where} ORDER BY created_at DESC, task_id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            parameters.append(max(0, int(limit)))
        with self._lock:
            rows = self._connection.execute(sql, parameters).fetchall()
        return [self._task_from_row(row) for row in rows]

    def publish_task(
        self,
        task_id: str,
        *,
        course_id: str,
        published_by: str,
    ) -> LearningTaskRecord:
        if self._postgres:
            return self._repository.publish_task(
                str(task_id), str(course_id), str(published_by)
            )
        published_at = utc_now()
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE learning_tasks
                SET status='published', published_at=COALESCE(published_at, ?),
                    published_by=COALESCE(published_by, ?)
                WHERE task_id=? AND course_id=? AND status IN ('draft', 'published')
                """,
                (published_at, str(published_by), str(task_id), str(course_id)),
            )
            self._connection.commit()
            if cursor.rowcount == 0:
                raise KeyError(task_id)
            row = self._connection.execute(
                "SELECT * FROM learning_tasks WHERE task_id=? AND course_id=?",
                (str(task_id), str(course_id)),
            ).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self._task_from_row(row)

    def record_event(self, event: LearningEventRecord) -> EventWriteResult:
        if self._postgres:
            return self._repository.record_event(event)
        if not 0 <= event.progress_percent <= 100:
            raise ValueError("progress_percent must be between 0 and 100")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                task = self._connection.execute(
                    "SELECT task_id FROM learning_tasks WHERE task_id=? AND course_id=?",
                    (event.task_id, event.course_id),
                ).fetchone()
                if task is None:
                    raise KeyError(event.task_id)
                cursor = self._connection.execute(
                    """
                    INSERT OR IGNORE INTO learning_events(
                        event_id, course_id, task_id, student_id, event_type,
                        progress_percent, resource_ref_json, occurred_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.course_id,
                        event.task_id,
                        event.student_id,
                        event.event_type,
                        event.progress_percent,
                        (
                            json.dumps(event.resource_ref, ensure_ascii=False, separators=(",", ":"))
                            if event.resource_ref
                            else None
                        ),
                        event.occurred_at,
                    ),
                )
                created = cursor.rowcount == 1
                current_row = self._connection.execute(
                    "SELECT * FROM task_progress WHERE task_id=? AND student_id=?",
                    (event.task_id, event.student_id),
                ).fetchone()
                if created:
                    current_percent = int(current_row["progress_percent"]) if current_row else 0
                    next_percent = max(current_percent, event.progress_percent)
                    current_status = str(current_row["status"]) if current_row else "not_started"
                    completed = current_status == "completed" or event.event_type == "completed"
                    if completed:
                        next_percent = 100
                        next_status = "completed"
                    elif event.event_type in {"started", "resource_opened", "progress_updated"}:
                        next_status = "in_progress"
                    else:
                        next_status = current_status
                    started_at = (
                        str(current_row["started_at"])
                        if current_row and current_row["started_at"]
                        else event.occurred_at
                    )
                    completed_at = (
                        str(current_row["completed_at"])
                        if current_row and current_row["completed_at"]
                        else event.occurred_at if completed else None
                    )
                    self._connection.execute(
                        """
                        INSERT INTO task_progress(
                            task_id, course_id, student_id, status,
                            progress_percent, started_at, completed_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(task_id, student_id) DO UPDATE SET
                            status=excluded.status,
                            progress_percent=excluded.progress_percent,
                            started_at=excluded.started_at,
                            completed_at=excluded.completed_at,
                            updated_at=excluded.updated_at
                        """,
                        (
                            event.task_id,
                            event.course_id,
                            event.student_id,
                            next_status,
                            next_percent,
                            started_at,
                            completed_at,
                            event.occurred_at,
                        ),
                    )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            progress_row = self._connection.execute(
                "SELECT * FROM task_progress WHERE task_id=? AND student_id=?",
                (event.task_id, event.student_id),
            ).fetchone()
        if progress_row is None:
            raise RuntimeError("learning event exists without task progress")
        return EventWriteResult(
            created=created,
            progress=self._progress_from_row(progress_row),
        )

    def get_progress(self, task_id: str, student_id: str) -> TaskProgressRecord | None:
        if self._postgres:
            return self._repository.get_progress(str(task_id), str(student_id))
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM task_progress WHERE task_id=? AND student_id=?",
                (str(task_id), str(student_id)),
            ).fetchone()
        return self._progress_from_row(row) if row else None

    def list_progress(self, *, course_id: str, task_id: str) -> list[TaskProgressRecord]:
        if self._postgres:
            return self._repository.list_progress(str(course_id), str(task_id))
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM task_progress
                WHERE course_id=? AND task_id=?
                ORDER BY student_id
                """,
                (str(course_id), str(task_id)),
            ).fetchall()
        return [self._progress_from_row(row) for row in rows]

    def close(self) -> None:
        if self._postgres:
            return
        with self._lock:
            self._connection.close()

