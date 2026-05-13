"""
教案存储模块：使用 JSON 文件保存生成的教案，便于后台管理
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from core.config import Config


def _now_iso() -> str:
  return datetime.now().isoformat()


class LessonPlanStorage:
  def __init__(self, storage_file: Optional[Path] = None):
    self.storage_file = Path(storage_file or Config.LESSON_PLANS_FILE)
    self.storage_file.parent.mkdir(parents=True, exist_ok=True)
    self._lock = RLock()
    self._plans: Dict[str, Dict[str, Any]] = {}
    self._load()

  def _load(self):
    if not self.storage_file.exists():
      return
    try:
      with open(self.storage_file, "r", encoding="utf-8") as f:
        raw = json.load(f)
    except Exception:
      self._plans = {}
      return

    items = raw.get("plans") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
      items = []

    for item in items:
      plan_id = item.get("id")
      if not plan_id:
        continue
      item.setdefault("created_at", _now_iso())
      item.setdefault("updated_at", item["created_at"])
      self._plans[plan_id] = item

  def _save_locked(self):
    payload = {
      "updated_at": _now_iso(),
      "plans": list(self._plans.values()),
    }
    with open(self.storage_file, "w", encoding="utf-8") as f:
      json.dump(payload, f, ensure_ascii=False, indent=2)

  def add_plan(
    self,
    *,
    title: str,
    topic: str,
    difficulty: str,
    knowledge_points: List[str],
    plan: Dict[str, Any],
  ) -> Dict[str, Any]:
    with self._lock:
      plan_id = uuid.uuid4().hex
      now = _now_iso()
      record = {
        "id": plan_id,
        "title": title,
        "topic": topic,
        "difficulty": difficulty,
        "knowledge_points": knowledge_points,
        "plan": plan,
        "created_at": now,
        "updated_at": now,
      }
      self._plans[plan_id] = record
      self._save_locked()
      return record

  def list_plans(self) -> Dict[str, Any]:
    with self._lock:
      items = []
      for plan in self._plans.values():
        items.append(
          {
            "id": plan["id"],
            "title": plan.get("title"),
            "topic": plan.get("topic"),
            "difficulty": plan.get("difficulty"),
            "knowledge_points": plan.get("knowledge_points") or [],
            "created_at": plan.get("created_at"),
            "updated_at": plan.get("updated_at"),
          }
        )
      items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
      return {"plans": items, "count": len(items)}

  def get_plan(self, plan_id: str) -> Dict[str, Any]:
    with self._lock:
      if plan_id not in self._plans:
        raise KeyError(plan_id)
      return self._plans[plan_id]

  def delete_plan(self, plan_id: str):
    with self._lock:
      if plan_id in self._plans:
        del self._plans[plan_id]
        self._save_locked()


lesson_plan_storage = LessonPlanStorage()



