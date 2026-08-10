"""简单的文件持久化任务存储。生产可换成 Redis 等。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import Task, TaskType, TaskStatus, CrawlTask, ParseTask, ChunkTask


class TaskStorage:
    def __init__(self, base_dir: str = "storage/tasks"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: Dict[str, Task] = {}
        self._load_from_disk()

    # -----------------------------------------------------
    def _path(self, task_id: str) -> Path:
        return self.base_dir / f"{task_id}.json"

    def _serialize(self, task: Task) -> dict:
        data = task.model_dump(mode="json")
        # datetime 转字符串，保持可 JSON 序列化
        if isinstance(data.get("start_time"), datetime):
            data["start_time"] = data["start_time"].isoformat()
        if isinstance(data.get("end_time"), datetime):
            data["end_time"] = data["end_time"].isoformat()
        return data

    def _deserialize(self, data: dict) -> Task:
        ttype = TaskType(data["task_type"])
        if ttype == TaskType.CRAWL:
            return CrawlTask(**data)
        if ttype == TaskType.PARSE:
            return ParseTask(**data)
        return ChunkTask(**data)

    # -----------------------------------------------------
    def _load_from_disk(self):
        if self._uses_postgres():
            for data in self._repository().list("pipeline_tasks"):
                try:
                    task = self._deserialize(data)
                    self.tasks[task.task_id] = task
                except Exception:
                    pass
            return
        for file in self.base_dir.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                task = self._deserialize(data)
                self.tasks[task.task_id] = task
            except Exception:
                # ignore
                pass

    def _write(self, task: Task):
        if self._uses_postgres():
            self._repository().put("pipeline_tasks", task.task_id, self._serialize(task))
            return
        self._path(task.task_id).write_text(
            json.dumps(self._serialize(task), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # -----------------------------------------------------
    def save(self, task: Task):
        self.tasks[task.task_id] = task
        self._write(task)

    def get(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def list(self, limit: int | None = None) -> List[Task]:
        tasks = sorted(self.tasks.values(), key=lambda t: t.start_time, reverse=True)
        return tasks if limit is None else tasks[:limit]

    def update(
        self,
        task_id: str,
        *,
        status: TaskStatus | None = None,
        progress: int | None = None,
        details: dict | None = None,
        error: str | None = None,
    ) -> Task | None:
        task = self.get(task_id)
        if not task:
            return None
        if status:
            task.status = status
            if status in (TaskStatus.SUCCESS, TaskStatus.FAILED):
                task.end_time = datetime.utcnow()
        if progress is not None:
            task.progress = progress
        if details:
            task.details.update(details)
        if error is not None:
            task.error = error
        self.save(task)
        return task

    @staticmethod
    def _uses_postgres() -> bool:
        import os
        return str(os.getenv("APP_STATE_PERSISTENCE_MODE", "json")).strip().lower() == "postgres"

    @staticmethod
    def _repository():
        from app.persistence.dependencies import get_postgres_app_state_repository
        return get_postgres_app_state_repository()


# 全局实例
store = TaskStorage()
