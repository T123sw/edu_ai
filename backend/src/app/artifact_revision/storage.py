"""CAS writes into the existing material store; history is immutable.

JSON mode embeds pre-revision snapshots in the same atomic manifest. PostgreSQL
uses the existing MaterialVersion table and a conditional UPDATE transaction.
"""
from __future__ import annotations
from copy import deepcopy
from contextlib import contextmanager
import os
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import select, update
from app.database import Material, MaterialVersion, database_session


class RevisionConflict(ValueError):
    pass


class RevisionStorage:
    def __init__(self, manager):
        self.manager = manager

    @staticmethod
    def check_owner(material, owner):
        if not owner or not material or material.get("owner_user_id") != owner or material.get("visibility") != "private" or material.get("published_from_material_id"):
            raise ValueError("资料不存在或无修改权限")

    def get(self, course, kind, artifact_id, owner):
        if not isinstance(course, str) or not course or course in {".", ".."} or "/" in course or "\\" in course:
            raise ValueError("资料所属课程无效")
        material = self.manager.get_generated_material(course, kind, artifact_id, owner_user_id=owner)
        self.check_owner(material, owner)
        return material

    def version(self, course, kind, artifact_id, owner, version):
        current = self.get(course, kind, artifact_id, owner)
        if current["version"] == version:
            return current
        if self.manager._material_uses_postgres():
            result = self.manager._material_repository().get_version(course, kind, artifact_id, version)
        else:
            result = current.get("revision_history", {}).get(str(version))
        if not result:
            raise ValueError("指定版本原文不存在")
        self.check_owner(result, owner)
        return deepcopy(result)

    @contextmanager
    def _exclusive(self):
        with self.manager._storage_lock():
            if self.manager._material_uses_postgres():
                yield
                return
            path = self.manager.root_path / ".artifact-revision.lock"
            with path.open("a+b") as handle:
                if os.name == "nt":
                    import msvcrt
                    handle.write(b"0")
                    handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if os.name == "nt":
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def retry(current, operation_id, fingerprint):
        receipt = current.get("revision_operations", {}).get(operation_id)
        if receipt and receipt["fingerprint"] != fingerprint:
            raise RevisionConflict("操作编号已用于不同修改，请创建新的操作")
        return receipt

    def save(self, source, updates, *, owner, operation_id, fingerprint, summary, changes):
        key = (source["course_id"], source["material_type"], source["material_id"])
        with self._exclusive():
            current = self.get(*key, owner)
            receipt = self.retry(current, operation_id, fingerprint)
            if receipt:
                return self.version(*key, owner, receipt["version"])
            if current["version"] != source["version"] or current.get("content_hash") != source.get("content_hash") or current.get("updated_at") != source.get("updated_at"):
                raise RevisionConflict("资料已有新版本，请查看变化后使用最新版重试")
            payload = deepcopy(current)
            payload.update(updates)
            payload.update(version=current["version"] + 1, updated_at=datetime.now(timezone.utc).isoformat())
            if payload.get("origin_type") == "standard":
                payload["current_review_status"] = "pending"
            # Export files remain attached to history, never advertised as the new version.
            for field in ("file_path", "html_url", "video_url", "pptx_url", "sidecar_url"):
                payload[field] = None
            payload["artifact_paths"] = []
            payload["video_status"] = "not_generated"
            payload["revision"] = {"base_version": source["version"], "summary": summary, "changes": changes, "operation_id": operation_id}
            payload.setdefault("revision_operations", {})[operation_id] = {"fingerprint": fingerprint, "version": payload["version"]}
            payload["content_hash"] = hashlib.sha256(json.dumps(updates, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if self.manager._material_uses_postgres():
                try:
                    self._save_database(current, payload)
                except RevisionConflict:
                    winner = self.get(*key, owner)
                    receipt = self.retry(winner, operation_id, fingerprint)
                    if receipt:
                        return self.version(*key, owner, receipt["version"])
                    raise
            else:
                history = payload.setdefault("revision_history", {})
                snapshot = {k: deepcopy(v) for k, v in current.items() if k not in {"revision_history", "revision_operations"}}
                history[str(current["version"])] = snapshot
                self.manager._persist_material_manifest(payload)
            return payload

    def save_copy(self, source, updates, *, owner, operation_id, fingerprint, summary, changes):
        """Publish a draft as an independent private document, leaving its source intact."""
        self.check_owner(source, owner)
        key = (source["course_id"], source["material_type"], source["material_id"])
        identity = json.dumps([owner, *key, operation_id], ensure_ascii=False)
        material_id = "revision_" + hashlib.sha256(identity.encode()).hexdigest()[:32]
        with self._exclusive():
            existing = self.manager.get_generated_material(*key[:2], material_id, owner_user_id=owner)
            if existing:
                self.check_owner(existing, owner)
                if not self.retry(existing, operation_id, fingerprint):
                    raise RevisionConflict("修改稿标识已被使用，请重新修改")
                return existing
            current = self.get(*key, owner)
            if any(current.get(field) != source.get(field) for field in ("version", "content_hash", "updated_at")):
                raise RevisionConflict("资料已有新版本，请查看变化后使用最新版重试")
            payload = deepcopy(source)
            payload.update(updates)
            now = datetime.now(timezone.utc).isoformat()
            title = str(source.get("title") or source.get("topic") or "文档")
            payload.update(material_id=material_id, version=1, created_at=now, updated_at=now,
                           title=title + "（修改稿）", is_pinned=False, pinned_at=None,
                           origin_type="personal", standard_kind=None, current_review_status="not_required",
                           approved_version=None, source_job_id=None)
            for field in ("revision_history", "revision_operations", "published_material_id", "published_version",
                          "published_at", "published_by", "publication_status"):
                payload.pop(field, None)
            for field in ("file_path", "html_url", "video_url", "pptx_url", "sidecar_url"):
                payload[field] = None
            payload["artifact_paths"] = []
            payload["video_status"] = "not_generated"
            payload["revision"] = {"source_material_id": source["material_id"], "base_version": source["version"],
                                   "source_content_hash": source.get("content_hash"), "summary": summary,
                                   "changes": changes, "operation_id": operation_id}
            payload["revision_operations"] = {operation_id: {"fingerprint": fingerprint, "version": 1}}
            payload["content_hash"] = hashlib.sha256(json.dumps(updates, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            self.manager._persist_material_manifest(payload)
            return payload

    def _save_database(self, current, payload):
        repository = self.manager._material_repository()
        conditions = (
            Material.course_id == current["course_id"],
            Material.material_type == current["material_type"],
            Material.material_id == current["material_id"],
            Material.version == current["version"],
            Material.owner_user_id == current["owner_user_id"],
            Material.visibility == "private",
            Material.content_hash == current.get("content_hash"),
            Material.updated_at == datetime.fromisoformat(current["updated_at"]),
        )
        with database_session(engine=repository._engine) as session:
            result = session.execute(update(Material).where(*conditions).values(
                version=payload["version"], raw_payload=payload,
                content_hash=payload["content_hash"],
                current_review_status=payload.get("current_review_status", "not_required"),
                updated_at=datetime.fromisoformat(payload["updated_at"]),
            ))
            if result.rowcount != 1:
                raise RevisionConflict("资料已有新版本，请使用最新版重试")
            for snapshot in (current, payload):
                exists = session.scalar(select(MaterialVersion).where(
                    MaterialVersion.course_id == snapshot["course_id"],
                    MaterialVersion.material_type == snapshot["material_type"],
                    MaterialVersion.material_id == snapshot["material_id"],
                    MaterialVersion.version == snapshot["version"],
                ))
                if exists is None:
                    session.add(MaterialVersion(
                        course_id=snapshot["course_id"], material_type=snapshot["material_type"],
                        material_id=snapshot["material_id"], version=snapshot["version"],
                        origin_type=snapshot.get("origin_type", "personal"),
                        standard_kind=snapshot.get("standard_kind"),
                        review_status=snapshot.get("current_review_status", "not_required"),
                        created_at=datetime.fromisoformat(snapshot["updated_at"]), payload=snapshot,
                    ))
