"""
Course storage manager.

Handles:
- course metadata and course info
- knowledge base files and index
- generated teaching materials
"""

from __future__ import annotations

import copy
import json
import hashlib
import logging
import os
import re
import shutil
import tempfile
import threading
import uuid
from contextvars import ContextVar, Token
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set

from app.workspace_scope import SCOPE_TYPE_COURSE, normalize_workspace_scope


log = logging.getLogger(__name__)


LIBRARY_TYPE_COURSE = "course"
LIBRARY_TYPE_PERSONAL = "personal"
MaterialSpace = Literal["mine", "course", "all"]


def _default_course_storage_root(module_path: Path) -> Path:
    """Return one runtime course-data root shared by every Git worktree.

    Knowledge metadata can live in PostgreSQL while document bodies live on
    disk.  Using a path relative to ``__file__`` therefore splits a single
    logical library whenever the API is started from a linked Git worktree.
    Resolve linked worktrees through their common Git directory so the main
    checkout and every feature checkout read and write the same bodies.

    Packaged/non-Git deployments retain the historical API-local default.
    ``COURSE_STORAGE_ROOT`` is still handled by ``CourseStorageManager`` and
    takes precedence over this default.
    """

    resolved_module = Path(module_path).resolve()
    local_api_root = resolved_module.parents[2]
    checkout_root: Optional[Path] = None
    git_marker: Optional[Path] = None
    for parent in resolved_module.parents:
        candidate = parent / ".git"
        if candidate.exists():
            checkout_root = parent
            git_marker = candidate
            break
    if checkout_root is None or git_marker is None:
        return local_api_root / "course_data"

    common_git_dir: Optional[Path] = None
    if git_marker.is_dir():
        common_git_dir = git_marker.resolve()
    elif git_marker.is_file():
        try:
            marker = git_marker.read_text(encoding="utf-8").strip()
            prefix, git_dir_value = marker.split(":", 1)
            if prefix.strip().casefold() != "gitdir":
                return local_api_root / "course_data"
            linked_git_dir = (git_marker.parent / git_dir_value.strip()).resolve()
            common_dir_file = linked_git_dir / "commondir"
            common_git_dir = (
                (linked_git_dir / common_dir_file.read_text(encoding="utf-8").strip()).resolve()
                if common_dir_file.is_file()
                else linked_git_dir
            )
        except (OSError, ValueError):
            return local_api_root / "course_data"

    if common_git_dir.name != ".git":
        return local_api_root / "course_data"
    primary_checkout = common_git_dir.parent
    try:
        relative_api_root = local_api_root.relative_to(checkout_root)
    except ValueError:
        return local_api_root / "course_data"
    return primary_checkout / relative_api_root / "course_data"


COURSE_STORAGE_ROOT = _default_course_storage_root(Path(__file__))

TYPE_MAPPING = {
    "audio": "audio",
    "lesson_plan": "lesson_plans",
    "graph": "graphs",
    "report": "reports",
    "video": "videos",
    "ai_lecture_session": "lecture_sessions",
    "blog": "blogs",
    "quiz": "quizzes",
    "game": "games",
    "flashcard": "flashcards",
    "classroom": "classrooms",
}

DIR_TO_TYPE = {value: key for key, value in TYPE_MAPPING.items()}
FORMAL_MATERIAL_TYPES = frozenset(TYPE_MAPPING)
_STORAGE_LOCKS: Dict[str, threading.RLock] = {}
_STORAGE_LOCKS_GUARD = threading.Lock()
_GENERATION_PERSISTENCE_CONTEXT: ContextVar[Dict[str, Optional[str]]] = ContextVar(
    "generation_persistence_context",
    default={},
)


def set_generation_persistence_context(
    *,
    owner_user_id: Optional[str],
    source_job_id: Optional[str],
    config_snapshot_id: Optional[str],
) -> Token:
    return _GENERATION_PERSISTENCE_CONTEXT.set(
        {
            "owner_user_id": str(owner_user_id or "").strip() or None,
            "source_job_id": str(source_job_id or "").strip() or None,
            "config_snapshot_id": str(config_snapshot_id or "").strip() or None,
        }
    )


def reset_generation_persistence_context(token: Token) -> None:
    _GENERATION_PERSISTENCE_CONTEXT.reset(token)


class CourseRevisionConflict(RuntimeError):
    def __init__(self, *, course_id: str, expected: int, actual: int) -> None:
        super().__init__(
            f"course {course_id} revision conflict: expected {expected}, actual {actual}"
        )
        self.course_id = course_id
        self.expected = expected
        self.actual = actual


class CourseStorageManager:
    """Manage persisted course assets on disk."""

    def __init__(self, root_path: Optional[str] = None):
        if root_path:
            self.root_path = Path(root_path)
        else:
            env_path = os.getenv("COURSE_STORAGE_ROOT")
            self.root_path = Path(env_path) if env_path else COURSE_STORAGE_ROOT
        self.courses_dir = self.root_path / "courses"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.courses_dir.mkdir(parents=True, exist_ok=True)

    def _read_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_json(self, file_path: Path, payload: Dict[str, Any]) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=file_path.parent,
                prefix=f".{file_path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, file_path)
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def _storage_lock(self) -> threading.RLock:
        key = str(self.root_path.resolve())
        with _STORAGE_LOCKS_GUARD:
            return _STORAGE_LOCKS.setdefault(key, threading.RLock())

    def _material_dir(self, course_id: str, material_type: str) -> Path:
        return self.get_course_dir(course_id) / "generated_materials" / TYPE_MAPPING.get(material_type, "others")

    def _normalize_material_id(self, material_id: str) -> str:
        normalized = str(material_id or "").strip()
        if not normalized:
            return ""
        normalized = normalized.replace(":", "__")
        normalized = re.sub(r'[<>"/\\\\|?*]', "_", normalized)
        return normalized

    def _material_file(self, course_id: str, material_type: str, material_id: str) -> Path:
        safe_material_id = self._normalize_material_id(material_id)
        return self._material_dir(course_id, material_type) / f"{safe_material_id}.json"

    @staticmethod
    def _material_uses_postgres() -> bool:
        return (
            str(os.getenv("MATERIAL_PERSISTENCE_MODE", "json")).strip().lower()
            == "postgres"
        )

    @staticmethod
    def _material_repository():
        from app.persistence.dependencies import get_postgres_material_repository

        return get_postgres_material_repository()

    def _load_material_manifest(
        self, course_id: str, material_type: str, material_id: str
    ) -> Optional[Dict[str, Any]]:
        if self._material_uses_postgres():
            return self._material_repository().get(
                course_id, material_type, self._normalize_material_id(material_id)
            )
        return self._read_json(self._material_file(course_id, material_type, material_id))

    def _persist_material_manifest(self, payload: Dict[str, Any]) -> None:
        if self._material_uses_postgres():
            self._material_repository().upsert(payload)
            return
        self._write_json(
            self._material_file(
                str(payload["course_id"]),
                str(payload["material_type"]),
                str(payload["material_id"]),
            ),
            payload,
        )

    def _timestamp(self, value: Optional[str]) -> float:
        if not value:
            return 0.0
        try:
            return datetime.fromisoformat(value).timestamp()
        except Exception:
            return 0.0

    @staticmethod
    def _material_name(item: Dict[str, Any]) -> str:
        return str(
            item.get("title")
            or item.get("topic")
            or item.get("material_id")
            or ""
        ).strip()

    @classmethod
    def _natural_name_key(cls, item: Dict[str, Any]) -> tuple[Any, ...]:
        parts = re.split(r"(\d+)", cls._material_name(item).casefold())
        return tuple(
            int(part) if index % 2 else part
            for index, part in enumerate(parts)
        )

    def _sort_generated_materials(
        self,
        materials: List[Dict[str, Any]],
        *,
        sort: str = "pinned",
    ) -> List[Dict[str, Any]]:
        if sort == "pinned":
            return sorted(
                materials,
                key=lambda item: (
                    0 if item.get("is_pinned") else 1,
                    -self._timestamp(item.get("pinned_at")),
                    -self._timestamp(
                        item.get("updated_at") or item.get("created_at")
                    ),
                    str(item.get("material_id") or ""),
                ),
            )
        if sort in {"updated_desc", "updated_asc"}:
            reverse = sort == "updated_desc"
            return sorted(
                materials,
                key=lambda item: (
                    self._timestamp(
                        item.get("updated_at") or item.get("created_at")
                    ),
                    self._timestamp(item.get("created_at")),
                    str(item.get("material_id") or ""),
                ),
                reverse=reverse,
            )
        if sort in {"name_asc", "name_desc"}:
            return sorted(
                materials,
                key=lambda item: (
                    self._natural_name_key(item),
                    str(item.get("material_id") or ""),
                ),
                reverse=sort == "name_desc",
            )
        raise ValueError(f"unsupported material sort: {sort}")

    def _normalize_material_manifest(
        self,
        material_data: Dict[str, Any],
        *,
        course_id: str,
        material_type: str,
        material_id: str,
    ) -> Dict[str, Any]:
        normalized = dict(material_data)
        normalized["schema_version"] = int(normalized.get("schema_version") or 1)
        raw_version = normalized.get("version")
        if isinstance(raw_version, (dict, list)):
            normalized.setdefault("artifact_version", raw_version)
            normalized["version"] = 1
        else:
            try:
                normalized["version"] = int(raw_version or 1)
            except (TypeError, ValueError):
                normalized["version"] = 1
        normalized["material_id"] = self._normalize_material_id(material_id)
        normalized["course_id"] = str(normalized.get("course_id") or course_id)
        normalized["material_type"] = str(
            normalized.get("material_type") or material_type
        )
        normalized["scope_type"] = str(
            normalized.get("scope_type") or SCOPE_TYPE_COURSE
        )
        normalized["scope_id"] = (
            str(normalized.get("scope_id") or "").strip() or None
        )
        normalized["owner_user_id"] = (
            str(normalized.get("owner_user_id") or "").strip() or None
        )
        normalized["created_by"] = (
            str(
                normalized.get("created_by")
                or normalized.get("owner_user_id")
                or ""
            ).strip()
            or None
        )
        visibility = str(normalized.get("visibility") or "course").strip()
        normalized["visibility"] = (
            visibility if visibility in {"course", "private"} else "course"
        )
        normalized["source_job_id"] = (
            str(normalized.get("source_job_id") or "").strip() or None
        )
        normalized["config_snapshot_id"] = (
            str(normalized.get("config_snapshot_id") or "").strip() or None
        )
        normalized["source"] = dict(normalized.get("source") or {})
        normalized["status"] = str(normalized.get("status") or "ready")
        normalized["is_pinned"] = bool(normalized.get("is_pinned", False))
        normalized["artifact_paths"] = list(
            normalized.get("artifact_paths")
            or ([normalized["file_path"]] if normalized.get("file_path") else [])
        )
        return normalized

    @staticmethod
    def _material_owner_matches(
        material_data: Dict[str, Any], owner_user_id: Optional[str]
    ) -> bool:
        visibility = str(material_data.get("visibility") or "course").strip()
        if visibility != "private":
            return True
        if owner_user_id is None:
            return False
        stored_owner = str(
            material_data.get("created_by")
            or material_data.get("owner_user_id")
            or ""
        ).strip()
        requested_owner = str(owner_user_id or "").strip()
        return bool(stored_owner) and bool(requested_owner) and stored_owner == requested_owner

    @staticmethod
    def _matches_material_space(
        material_data: Dict[str, Any], space: MaterialSpace
    ) -> bool:
        visibility = str(material_data.get("visibility") or "course").strip()
        if space == "mine":
            return visibility == "private"
        if space == "course":
            return visibility == "course"
        return True

    def migrate_legacy_generated_materials(
        self,
        course_id: str,
        *,
        owner_user_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Plan or apply the explicit migration of legacy course materials.

        A dry run is side-effect free and is the default. Applying a migration
        never makes an unowned record public: records without an explicit
        ``owner_user_id`` are marked ``pending_owner`` and remain available only
        to internal/admin callers until an owner is assigned.
        """

        generated_root = self.get_course_dir(course_id) / "generated_materials"
        assigned_owner = str(owner_user_id or "").strip() or None
        report: Dict[str, Any] = {
            "course_id": course_id,
            "dry_run": bool(dry_run),
            "owner_user_id": assigned_owner,
            "scanned": 0,
            "would_change": 0,
            "applied": 0,
            "pending_owner": 0,
            "legacy_partial": 0,
            "actions": [],
        }
        if not generated_root.exists():
            return report

        with self._storage_lock():
            for source_path in sorted(generated_root.rglob("*.json")):
                report["scanned"] += 1
                relative_source = source_path.relative_to(
                    self.get_course_dir(course_id)
                ).as_posix()
                payload = self._read_json(source_path)
                if not isinstance(payload, dict):
                    report["legacy_partial"] += 1
                    report["actions"].append(
                        {
                            "source": relative_source,
                            "target": relative_source,
                            "status": "legacy_partial",
                            "reason": "invalid_json",
                            "changes": [],
                        }
                    )
                    continue

                derived_type = DIR_TO_TYPE.get(source_path.parent.name)
                material_type = str(
                    payload.get("material_type") or derived_type or ""
                ).strip()
                raw_material_id = str(
                    payload.get("material_id")
                    or payload.get("id")
                    or source_path.stem
                ).strip()
                material_id = self._normalize_material_id(raw_material_id)

                if material_type not in FORMAL_MATERIAL_TYPES or not material_id:
                    report["legacy_partial"] += 1
                    report["actions"].append(
                        {
                            "source": relative_source,
                            "target": relative_source,
                            "status": "legacy_partial",
                            "reason": "unsupported_material_type_or_id",
                            "changes": [],
                        }
                    )
                    if not dry_run:
                        payload["status"] = "legacy_partial"
                        payload["updated_at"] = datetime.now().isoformat()
                        self._write_json(source_path, payload)
                    continue

                target_path = self._material_file(
                    course_id, material_type, material_id
                )
                changes: List[str] = []
                stored_owner = str(payload.get("owner_user_id") or "").strip()
                if not stored_owner:
                    if assigned_owner:
                        changes.append("assign_owner")
                    else:
                        changes.append("mark_pending_owner")
                        report["pending_owner"] += 1
                if target_path.resolve() != source_path.resolve():
                    changes.append("move_to_formal_type")

                needs_upgrade = (
                    int(payload.get("schema_version") or 1) < 2
                    or not payload.get("material_id")
                    or not payload.get("course_id")
                    or "artifact_paths" not in payload
                    or not payload.get("content_hash")
                )
                if needs_upgrade:
                    changes.append("upgrade_manifest")

                action = {
                    "source": relative_source,
                    "target": target_path.relative_to(
                        self.get_course_dir(course_id)
                    ).as_posix(),
                    "status": "planned" if dry_run else "unchanged",
                    "reason": None,
                    "changes": changes,
                }
                report["actions"].append(action)
                if not changes:
                    continue

                report["would_change"] += 1
                if dry_run:
                    continue
                if target_path.exists() and target_path.resolve() != source_path.resolve():
                    action["status"] = "legacy_partial"
                    action["reason"] = "target_exists"
                    report["legacy_partial"] += 1
                    continue

                now = datetime.now().isoformat()
                upgraded = self._normalize_material_manifest(
                    payload,
                    course_id=course_id,
                    material_type=material_type,
                    material_id=material_id,
                )
                upgraded["schema_version"] = 2
                upgraded["material_type"] = material_type
                upgraded["material_id"] = material_id
                upgraded["course_id"] = course_id
                upgraded["owner_user_id"] = stored_owner or assigned_owner
                upgraded["status"] = (
                    str(payload.get("status") or "ready")
                    if upgraded["owner_user_id"]
                    else "pending_owner"
                )
                upgraded["created_at"] = str(payload.get("created_at") or now)
                upgraded["updated_at"] = now
                if not upgraded.get("content_hash"):
                    hash_payload = {
                        key: value
                        for key, value in upgraded.items()
                        if key != "content_hash"
                    }
                    upgraded["content_hash"] = hashlib.sha256(
                        json.dumps(
                            hash_payload,
                            ensure_ascii=False,
                            sort_keys=True,
                            default=str,
                        ).encode("utf-8")
                    ).hexdigest()

                self._write_json(target_path, upgraded)
                if target_path.resolve() != source_path.resolve():
                    source_path.unlink(missing_ok=True)
                action["status"] = "applied"
                report["applied"] += 1

        return report

    def _normalize_scope(self, *, course_id: str, scope_type: Optional[str], scope_id: Optional[str]) -> Dict[str, Any]:
        return normalize_workspace_scope(
            course_id=course_id,
            scope_type=scope_type or SCOPE_TYPE_COURSE,
            scope_id=scope_id,
        )

    @staticmethod
    def _matches_scope(
        item: Dict[str, Any],
        *,
        scope_type: Optional[str],
        scope_ids: Optional[Set[str]],
        aggregate: bool,
    ) -> bool:
        item_scope_type = str(item.get("scope_type") or SCOPE_TYPE_COURSE).strip() or SCOPE_TYPE_COURSE
        item_scope_id = str(item.get("scope_id") or "").strip() or None

        if not scope_type:
            return True

        normalized_scope_type = str(scope_type).strip()
        if normalized_scope_type == SCOPE_TYPE_COURSE:
            if aggregate:
                return True
            return item_scope_type == SCOPE_TYPE_COURSE

        if normalized_scope_type != "knowledge_point":
            return True

        if item_scope_type != "knowledge_point":
            return False
        if not scope_ids:
            return item_scope_id is not None
        return item_scope_id in scope_ids

    @staticmethod
    def _matches_library(
        item: Dict[str, Any],
        *,
        library_type: Optional[str],
        owner_user_id: Optional[str],
    ) -> bool:
        normalized_library_type = str(library_type or "").strip() or None
        if not normalized_library_type:
            return True

        item_library_type = str(item.get("library_type") or LIBRARY_TYPE_COURSE).strip() or LIBRARY_TYPE_COURSE
        if item_library_type != normalized_library_type:
            return False

        normalized_owner_user_id = str(owner_user_id or "").strip() or None
        if normalized_library_type == LIBRARY_TYPE_PERSONAL and normalized_owner_user_id:
            return str(item.get("owner_user_id") or "").strip() == normalized_owner_user_id
        return True

    def get_course_dir(self, course_id: str) -> Path:
        return self.courses_dir / course_id

    def _knowledge_base_documents_dir(self, course_id: str) -> Path:
        return self.get_course_dir(course_id) / "knowledge_base" / "documents"

    def get_classroom_audio_dir(self, course_id: str, classroom_id: str) -> Path:
        """课件配音文件目录（SPEC-04 §5 media 迁移落盘位置），跟课件 JSON
        本身（`generated_materials/classrooms/{id}.json`）同级、按 id 分子目录，
        不与 `_material_file` 的单文件约定冲突。"""
        return self._classroom_media_dir(course_id, classroom_id) / "audio"

    def get_classroom_video_dir(self, course_id: str, classroom_id: str) -> Path:
        """Stable storage root for MP4/SRT/timeline artifacts derived from a classroom."""
        return self._classroom_media_dir(course_id, classroom_id) / "video"

    def get_classroom_qa_dir(
        self,
        course_id: str,
        classroom_id: str,
        owner_user_id: str,
    ) -> Path:
        """Per-student classroom Q&A root without exposing the owner in paths."""
        owner_hash = hashlib.sha256(owner_user_id.encode("utf-8")).hexdigest()[:24]
        if classroom_id.startswith("resource_"):
            # Static-resource sessions reuse the same atomic store but avoid the
            # longer classroom media path, which can exceed Windows path limits.
            return self.get_course_dir(course_id) / "resource_qa" / classroom_id[9:] / owner_hash
        return self._classroom_media_dir(course_id, classroom_id) / "qa" / owner_hash

    def _classroom_media_dir(self, course_id: str, classroom_id: str) -> Path:
        safe_classroom_id = self._normalize_material_id(classroom_id)
        return self._material_dir(course_id, "classroom") / f"{safe_classroom_id}_media"

    def _build_recovered_knowledge_base_entry(self, course_id: str, file_path: Path) -> Dict[str, Any]:
        relative_path = file_path.relative_to(self.get_course_dir(course_id)).as_posix()
        file_stat = file_path.stat()
        return {
            "id": (
                "doc-"
                + uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"edu-ai/course-document/{course_id}/{relative_path.casefold()}",
                ).hex
            ),
            "filename": file_path.name,
            "path": relative_path,
            "size": file_stat.st_size,
            "uploaded_at": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            "course_id": course_id,
            "scope_type": SCOPE_TYPE_COURSE,
            "scope_id": None,
            "library_type": LIBRARY_TYPE_COURSE,
            "owner_user_id": None,
            "promoted_from_document_id": None,
        }

    def _recover_orphaned_knowledge_base_entries(
        self,
        course_id: str,
        entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        kb_documents_dir = self._knowledge_base_documents_dir(course_id)
        if not kb_documents_dir.exists():
            return []

        indexed_paths = {
            str(item.get("path") or "").replace("\\", "/").strip()
            for item in entries
            if str(item.get("path") or "").strip()
        }
        orphaned_files = sorted(
            (path for path in kb_documents_dir.iterdir() if path.is_file()),
            key=lambda path: (path.stat().st_mtime, path.name.lower()),
        )

        recovered_entries: List[Dict[str, Any]] = []
        for file_path in orphaned_files:
            relative_path = file_path.relative_to(self.get_course_dir(course_id)).as_posix()
            if relative_path in indexed_paths:
                continue
            recovered_entries.append(self._build_recovered_knowledge_base_entry(course_id, file_path))
        return recovered_entries

    def create_course_structure(self, course_id: str) -> Path:
        course_dir = self.get_course_dir(course_id)
        self._knowledge_base_documents_dir(course_id).mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "audio").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "lesson_plans").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "graphs").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "reports").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "videos").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "lecture_sessions").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "blogs").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "quizzes").mkdir(parents=True, exist_ok=True)

        metadata_file = course_dir / "metadata.json"
        if not metadata_file.exists():
            metadata = {
                "course_id": course_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            self.save_course_metadata(course_id, metadata)

        index_file = course_dir / "knowledge_base" / "index.json"
        if not index_file.exists():
            self.save_knowledge_base_index(course_id, [])
        return course_dir

    def save_course_info(self, course_id: str, course_info: Dict[str, Any]) -> bool:
        try:
            info_file = self.get_course_dir(course_id) / "course_info.json"
            metadata = self.get_course_metadata(course_id)
            now = datetime.now().isoformat()
            payload = dict(course_info)
            payload.setdefault("id", course_id)
            payload.setdefault("revision", 0)
            payload.setdefault("created_at", metadata.get("created_at") or now)
            payload["updated_at"] = payload.get("updated_at") or now
            if self._course_uses_postgres():
                self._course_repository().upsert(payload)
                return True
            self._write_json(info_file, payload)
            metadata["updated_at"] = now
            self.save_course_metadata(course_id, metadata)
            from app.persistence.hooks import shadow_upsert_course

            shadow_upsert_course(payload)
            return True
        except Exception as e:
            print(f"Error saving course info: {e}")
            return False

    def get_course_info(self, course_id: str) -> Optional[Dict[str, Any]]:
        try:
            if self._course_uses_postgres():
                return self._course_repository().get(course_id)
            info_file = self.get_course_dir(course_id) / "course_info.json"
            if not info_file.exists():
                return None
            info = self._read_json(info_file)
            if not info:
                return None
            metadata = self.get_course_metadata(course_id)
            normalized = dict(info)
            normalized["revision"] = int(normalized.get("revision") or 0)
            normalized.setdefault("created_by", None)
            normalized.setdefault("created_at", metadata.get("created_at"))
            normalized.setdefault("updated_at", metadata.get("updated_at"))
            return normalized
        except Exception as e:
            print(f"Error loading course info: {e}")
            return None

    def list_course_infos(self) -> List[Dict[str, Any]]:
        """Return course metadata from the configured source of truth.

        Course asset directories are intentionally still used for uploaded and
        generated files, but they must not decide whether a PostgreSQL-backed
        course exists. This also keeps courses visible when the API is started
        from a different worktree that shares the same database.
        """
        if self._course_uses_postgres():
            return self._course_repository().list()

        results: List[Dict[str, Any]] = []
        if not self.courses_dir.exists():
            return results
        for course_dir in self.courses_dir.iterdir():
            if not course_dir.is_dir():
                continue
            info = self.get_course_info(course_dir.name)
            if info:
                results.append(info)
        return results

    def update_course_info(
        self,
        course_id: str,
        course_info: Dict[str, Any],
        *,
        expected_revision: int,
    ) -> Dict[str, Any]:
        with self._storage_lock():
            current = self.get_course_info(course_id)
            if current is None:
                raise KeyError(course_id)
            actual_revision = int(current.get("revision") or 0)
            if actual_revision != int(expected_revision):
                raise CourseRevisionConflict(
                    course_id=course_id,
                    expected=int(expected_revision),
                    actual=actual_revision,
                )
            now = datetime.now().isoformat()
            updated = {
                **current,
                **dict(course_info),
                "id": course_id,
                "revision": actual_revision + 1,
                "updated_at": now,
            }
            if self._course_uses_postgres():
                self._course_repository().upsert(updated)
                return updated
            self._write_json(
                self.get_course_dir(course_id) / "course_info.json", updated
            )
            metadata = self.get_course_metadata(course_id)
            metadata["updated_at"] = now
            self.save_course_metadata(course_id, metadata)
            from app.persistence.hooks import shadow_upsert_course

            shadow_upsert_course(updated)
            return updated

    def save_course_metadata(self, course_id: str, metadata: Dict[str, Any]) -> bool:
        if self._app_state_uses_postgres():
            self._app_state_repository().put("course_metadata", course_id, metadata)
            return True
        try:
            metadata_file = self.get_course_dir(course_id) / "metadata.json"
            self._write_json(metadata_file, metadata)
            return True
        except Exception as e:
            print(f"Error saving course metadata: {e}")
            return False

    def get_course_metadata(self, course_id: str) -> Dict[str, Any]:
        if self._app_state_uses_postgres():
            metadata = self._app_state_repository().get("course_metadata", course_id)
            if metadata:
                return metadata
            return {
                "course_id": course_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        metadata_file = self.get_course_dir(course_id) / "metadata.json"
        metadata = self._read_json(metadata_file)
        if metadata:
            return metadata
        return {
            "course_id": course_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _app_state_uses_postgres() -> bool:
        return str(os.getenv("APP_STATE_PERSISTENCE_MODE", "json")).strip().lower() == "postgres"

    @staticmethod
    def _app_state_repository():
        from app.persistence.dependencies import get_postgres_app_state_repository
        return get_postgres_app_state_repository()

    def save_knowledge_base_file(
        self,
        course_id: str,
        file_data: bytes,
        filename: str,
        *,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
        library_type: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        promoted_from_document_id: Optional[str] = None,
    ) -> Optional[str]:
        try:
            kb_documents_dir = self.get_course_dir(course_id) / "knowledge_base" / "documents"
            kb_documents_dir.mkdir(parents=True, exist_ok=True)

            file_path = kb_documents_dir / filename
            with open(file_path, "wb") as f:
                f.write(file_data)

            normalized_scope = self._normalize_scope(
                course_id=course_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
            relative_path = f"knowledge_base/documents/{filename}".replace("\\", "/")
            index = self.get_knowledge_base_index(course_id)
            index = [
                item
                for item in index
                if str(item.get("path") or "").replace("\\", "/").strip() != relative_path
            ]
            file_info = {
                "id": f"doc-{uuid.uuid4().hex}",
                "filename": filename,
                "path": relative_path,
                "size": len(file_data),
                "uploaded_at": datetime.now().isoformat(),
                "course_id": course_id,
                "scope_type": normalized_scope["scope_type"],
                "scope_id": normalized_scope["scope_id"],
                "library_type": str(library_type or LIBRARY_TYPE_COURSE).strip() or LIBRARY_TYPE_COURSE,
                "owner_user_id": str(owner_user_id or "").strip() or None,
                "promoted_from_document_id": str(promoted_from_document_id or "").strip() or None,
            }
            index.append(file_info)
            self.save_knowledge_base_index(course_id, index)
            return str(file_path.relative_to(self.get_course_dir(course_id)))
        except Exception as e:
            print(f"Error saving knowledge base file: {e}")
            return None

    def get_knowledge_base_index(
        self,
        course_id: str,
        *,
        scope_type: Optional[str] = None,
        scope_ids: Optional[Set[str]] = None,
        aggregate: bool = False,
        library_type: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        index_file = self.get_course_dir(course_id) / "knowledge_base" / "index.json"
        entries: List[Dict[str, Any]] = []
        if self._knowledge_uses_postgres():
            entries = self._knowledge_repository().list_documents(course_id)
        elif index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    raw_entries = json.load(f)
                    entries = list(raw_entries) if isinstance(raw_entries, list) else []
            except Exception:
                entries = []

        recovered_entries = self._recover_orphaned_knowledge_base_entries(course_id, entries)
        if recovered_entries:
            entries = [*entries, *recovered_entries]
            self.save_knowledge_base_index(course_id, entries)

        normalized_entries: List[Dict[str, Any]] = []
        for item in entries:
            next_item = dict(item or {})
            next_item["library_type"] = str(next_item.get("library_type") or LIBRARY_TYPE_COURSE)
            next_item["owner_user_id"] = str(next_item.get("owner_user_id") or "").strip() or None
            is_personal = next_item["library_type"] == LIBRARY_TYPE_PERSONAL
            next_item["course_id"] = (
                str(next_item.get("course_id") or "").strip() or None
                if is_personal
                else str(next_item.get("course_id") or course_id)
            )
            next_item["scope_type"] = str(
                next_item.get("scope_type")
                or (LIBRARY_TYPE_PERSONAL if is_personal else SCOPE_TYPE_COURSE)
            )
            next_item["scope_id"] = (
                str(next_item.get("scope_id") or "").strip()
                or (
                    f"personal:{next_item['owner_user_id']}"
                    if is_personal and next_item["owner_user_id"]
                    else None
                )
            )
            next_item["promoted_from_document_id"] = str(next_item.get("promoted_from_document_id") or "").strip() or None
            if self._matches_scope(
                next_item,
                scope_type=scope_type,
                scope_ids=scope_ids,
                aggregate=aggregate,
            ) and self._matches_library(
                next_item,
                library_type=library_type,
                owner_user_id=owner_user_id,
            ):
                normalized_entries.append(next_item)
        return normalized_entries

    def save_knowledge_base_index(self, course_id: str, index: List[Dict[str, Any]]) -> bool:
        if self._knowledge_uses_postgres():
            self._knowledge_repository().replace_documents(course_id, index)
            return True
        try:
            index_file = self.get_course_dir(course_id) / "knowledge_base" / "index.json"
            index_file.parent.mkdir(parents=True, exist_ok=True)
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving knowledge base index: {e}")
            return False

    def save_knowledge_graph(self, course_id: str, graph_data: Dict[str, Any]) -> bool:
        if self._knowledge_uses_postgres():
            self._knowledge_repository().upsert_graph(course_id, graph_data)
            return True
        try:
            graph_file = self.get_course_dir(course_id) / "knowledge_graph.json"
            self._write_json(graph_file, graph_data)
            return True
        except Exception as e:
            print(f"Error saving knowledge graph: {e}")
            return False

    def get_knowledge_graph(self, course_id: str) -> Optional[Dict[str, Any]]:
        if self._knowledge_uses_postgres():
            return self._knowledge_repository().get_graph(course_id)
        try:
            graph_file = self.get_course_dir(course_id) / "knowledge_graph.json"
            if not graph_file.exists():
                return None
            return self._read_json(graph_file)
        except Exception as e:
            print(f"Error loading knowledge graph: {e}")
            return None

    @staticmethod
    def _knowledge_uses_postgres() -> bool:
        return (
            str(os.getenv("KNOWLEDGE_PERSISTENCE_MODE", "json")).strip().lower()
            == "postgres"
        )

    @staticmethod
    def _knowledge_repository():
        from app.persistence.dependencies import get_postgres_knowledge_repository

        return get_postgres_knowledge_repository()

    def save_generated_material(
        self,
        course_id: str,
        material_type: str,
        material_id: str,
        material_data: Dict[str, Any],
        file_data: Optional[bytes] = None,
        *,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        visibility: Optional[Literal["course", "private"]] = None,
        source_job_id: Optional[str] = None,
        config_snapshot_id: Optional[str] = None,
        source_snapshot: Optional[Dict[str, Any]] = None,
        config_snapshot: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            generation_context = _GENERATION_PERSISTENCE_CONTEXT.get()
            owner_user_id = (
                str(owner_user_id or generation_context.get("owner_user_id") or "").strip()
                or None
            )
            source_job_id = (
                str(source_job_id or generation_context.get("source_job_id") or "").strip()
                or None
            )
            config_snapshot_id = (
                str(
                    config_snapshot_id
                    or generation_context.get("config_snapshot_id")
                    or ""
                ).strip()
                or None
            )
            normalized_material_type = str(material_type or "").strip()
            if normalized_material_type not in FORMAL_MATERIAL_TYPES:
                raise ValueError(f"unsupported material type: {normalized_material_type}")
            safe_material_id = self._normalize_material_id(material_id)
            if not safe_material_id:
                raise ValueError("material_id is required")
            material_dir = self._material_dir(course_id, material_type)
            material_dir.mkdir(parents=True, exist_ok=True)

            material_file = self._material_file(course_id, material_type, material_id)
            with self._storage_lock():
                existing_data = self._load_material_manifest(
                    course_id, material_type, material_id
                ) or {}
                next_data = dict(existing_data)
                next_data.update(material_data or {})
                normalized_scope = self._normalize_scope(
                    course_id=course_id,
                    scope_type=scope_type or next_data.get("scope_type"),
                    scope_id=scope_id if scope_id is not None else next_data.get("scope_id"),
                )
                now = datetime.now().isoformat()
                next_data["schema_version"] = 2
                next_data["version"] = int(existing_data.get("version") or 0) + 1
                next_data["material_type"] = normalized_material_type
                next_data["material_id"] = safe_material_id
                next_data["course_id"] = course_id
                next_data["scope_type"] = normalized_scope["scope_type"]
                next_data["scope_id"] = normalized_scope["scope_id"]
                next_data["owner_user_id"] = (
                    str(owner_user_id or next_data.get("owner_user_id") or "").strip()
                    or None
                )
                next_data["created_by"] = (
                    str(
                        next_data.get("created_by")
                        or next_data.get("owner_user_id")
                        or ""
                    ).strip()
                    or None
                )
                normalized_visibility = str(
                    visibility
                    or next_data.get("visibility")
                    or ("private" if next_data["owner_user_id"] else "course")
                ).strip()
                if normalized_visibility not in {"course", "private"}:
                    raise ValueError(
                        f"unsupported material visibility: {normalized_visibility}"
                    )
                next_data["visibility"] = normalized_visibility
                next_data["source_job_id"] = (
                    str(source_job_id or next_data.get("source_job_id") or "").strip()
                    or None
                )
                next_data["config_snapshot_id"] = (
                    str(
                        config_snapshot_id
                        or next_data.get("config_snapshot_id")
                        or ""
                    ).strip()
                    or None
                )
                if source_snapshot is not None:
                    next_data["source_snapshot"] = copy.deepcopy(source_snapshot)
                else:
                    next_data["source_snapshot"] = copy.deepcopy(
                        next_data.get("source_snapshot") or {}
                    )
                if config_snapshot is not None:
                    next_data["config_snapshot"] = copy.deepcopy(config_snapshot)
                else:
                    next_data["config_snapshot"] = copy.deepcopy(
                        next_data.get("config_snapshot") or {}
                    )
                next_data["source"] = dict(next_data.get("source") or {})
                next_data["status"] = str(next_data.get("status") or "ready")
                next_data["created_at"] = str(
                    next_data.get("created_at")
                    or existing_data.get("created_at")
                    or now
                )
                next_data["updated_at"] = now
                next_data["is_pinned"] = bool(
                    next_data.get(
                        "is_pinned", existing_data.get("is_pinned", False)
                    )
                )
                next_data["pinned_at"] = (
                    str(
                        next_data.get("pinned_at")
                        or existing_data.get("pinned_at")
                        or now
                    )
                    if next_data["is_pinned"]
                    else None
                )

                staged_attachment: Optional[Path] = None
                attachment_path: Optional[Path] = None
                if file_data is not None:
                    file_ext = str(next_data.get("file_extension") or ".txt")
                    if not file_ext.startswith("."):
                        file_ext = f".{file_ext}"
                    file_ext = re.sub(r"[^.a-zA-Z0-9_-]", "", file_ext) or ".bin"
                    attachment_path = material_dir / f"{safe_material_id}{file_ext}"
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=material_dir,
                        prefix=f".{safe_material_id}-",
                        suffix=".artifact.tmp",
                        delete=False,
                    ) as handle:
                        staged_attachment = Path(handle.name)
                        handle.write(file_data)
                        handle.flush()
                        os.fsync(handle.fileno())
                    next_data["file_path"] = str(
                        attachment_path.relative_to(self.get_course_dir(course_id))
                    ).replace("\\", "/")
                    next_data["artifact_paths"] = [next_data["file_path"]]
                    next_data["content_hash"] = hashlib.sha256(file_data).hexdigest()
                else:
                    payload_for_hash = json.dumps(
                        material_data or {},
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    ).encode("utf-8")
                    next_data["content_hash"] = hashlib.sha256(
                        payload_for_hash
                    ).hexdigest()

                previous_attachment: Optional[bytes] = None
                try:
                    if staged_attachment is not None and attachment_path is not None:
                        if attachment_path.exists():
                            previous_attachment = attachment_path.read_bytes()
                        os.replace(staged_attachment, attachment_path)
                        staged_attachment = None
                    self._persist_material_manifest(next_data)
                except Exception:
                    if staged_attachment is not None:
                        staged_attachment.unlink(missing_ok=True)
                    if attachment_path is not None:
                        if previous_attachment is None:
                            attachment_path.unlink(missing_ok=True)
                        else:
                            attachment_path.write_bytes(previous_attachment)
                    raise
            return True
        except Exception as e:
            print(f"Error saving generated material: {e}")
            return False

    def get_stored_generated_material(
        self,
        course_id: str,
        material_type: str,
        material_id: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            material_data = self._load_material_manifest(
                course_id, material_type, material_id
            )
            if not material_data:
                return None
            normalized = self._normalize_material_manifest(
                material_data,
                course_id=course_id,
                material_type=material_type,
                material_id=material_id,
            )
            return normalized
        except Exception as e:
            print(f"Error loading stored generated material: {e}")
            return None

    def save_published_material_manifest(
        self,
        course_id: str,
        material_type: str,
        material_id: str,
        material_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        normalized_material_type = str(material_type or "").strip()
        if normalized_material_type not in FORMAL_MATERIAL_TYPES:
            raise ValueError(f"unsupported material type: {normalized_material_type}")
        safe_material_id = self._normalize_material_id(material_id)
        if not safe_material_id:
            raise ValueError("material_id is required")
        material_file = self._material_file(
            course_id, normalized_material_type, safe_material_id
        )
        with self._storage_lock():
            existing = self._load_material_manifest(
                course_id, normalized_material_type, safe_material_id
            ) or {}
            now = datetime.now().isoformat()
            payload = copy.deepcopy(dict(material_data or {}))
            payload.update(
                {
                    "schema_version": 2,
                    "version": int(existing.get("version") or 0) + 1,
                    "material_id": safe_material_id,
                    "material_type": normalized_material_type,
                    "course_id": course_id,
                    "visibility": "course",
                    "owner_user_id": None,
                    "created_at": str(existing.get("created_at") or now),
                    "updated_at": now,
                }
            )
            payload.setdefault("scope_type", SCOPE_TYPE_COURSE)
            payload.setdefault("scope_id", None)
            payload.setdefault("status", "ready")
            payload.setdefault("is_pinned", bool(existing.get("is_pinned", False)))
            payload.setdefault("pinned_at", existing.get("pinned_at"))
            self._persist_material_manifest(payload)
        return self._normalize_material_manifest(
            payload,
            course_id=course_id,
            material_type=normalized_material_type,
            material_id=safe_material_id,
        )

    def update_generated_material_metadata(
        self,
        course_id: str,
        material_type: str,
        material_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        material_file = self._material_file(course_id, material_type, material_id)
        with self._storage_lock():
            stored = self._load_material_manifest(
                course_id, material_type, material_id
            )
            if not stored:
                return None
            stored.update(copy.deepcopy(dict(updates or {})))
            stored["updated_at"] = datetime.now().isoformat()
            self._persist_material_manifest(stored)
        return self._normalize_material_manifest(
            stored,
            course_id=course_id,
            material_type=material_type,
            material_id=material_id,
        )

    def get_generated_material(
        self,
        course_id: str,
        material_type: str,
        material_id: str,
        *,
        owner_user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            normalized = self.get_stored_generated_material(
                course_id, material_type, material_id
            )
            if not normalized:
                return None
            return (
                normalized
                if self._material_owner_matches(normalized, owner_user_id)
                else None
            )
        except Exception as e:
            print(f"Error loading generated material: {e}")
            return None

    def list_generated_materials(
        self,
        course_id: str,
        material_type: Optional[str] = None,
        *,
        scope_type: Optional[str] = None,
        scope_ids: Optional[Set[str]] = None,
        aggregate: bool = False,
        owner_user_id: Optional[str] = None,
        space: MaterialSpace = "all",
        sort: str = "pinned",
    ) -> List[Dict[str, Any]]:
        if space not in {"mine", "course", "all"}:
            raise ValueError(f"unsupported material space: {space}")
        materials: List[Dict[str, Any]] = []

        try:
            if self._material_uses_postgres():
                for material_data in self._material_repository().list(
                    course_id, material_type
                ):
                    if not self._material_owner_matches(
                        material_data, owner_user_id
                    ):
                        continue
                    if not self._matches_material_space(material_data, space):
                        continue
                    if self._matches_scope(
                        material_data,
                        scope_type=scope_type,
                        scope_ids=scope_ids,
                        aggregate=aggregate,
                    ):
                        materials.append(material_data)
                return self._sort_generated_materials(materials, sort=sort)
            generated_materials_dir = self.get_course_dir(course_id) / "generated_materials"
            if not generated_materials_dir.exists():
                return []

            if material_type:
                type_dir = generated_materials_dir / TYPE_MAPPING.get(material_type, "others")
                type_dirs = [type_dir] if type_dir.exists() else []
            else:
                type_dirs = [type_dir for type_dir in generated_materials_dir.iterdir() if type_dir.is_dir()]

            for type_dir in type_dirs:
                derived_type = DIR_TO_TYPE.get(type_dir.name, material_type or "unknown")
                for json_file in type_dir.glob("*.json"):
                    try:
                        material_data = self._read_json(json_file)
                        if not material_data:
                            continue
                        material_data = self._normalize_material_manifest(
                            material_data,
                            course_id=course_id,
                            material_type=derived_type,
                            material_id=json_file.stem,
                        )
                        if not self._material_owner_matches(
                            material_data, owner_user_id
                        ):
                            continue
                        if not self._matches_material_space(material_data, space):
                            continue
                        if self._matches_scope(
                            material_data,
                            scope_type=scope_type,
                            scope_ids=scope_ids,
                            aggregate=aggregate,
                        ):
                            materials.append(material_data)
                    except Exception as exc:
                        log.warning(
                            "Skipping invalid generated material %s for course %s: %s",
                            json_file,
                            course_id,
                            exc,
                        )
        except Exception as e:
            print(f"Error listing generated materials: {e}")

        return self._sort_generated_materials(materials, sort=sort)

    def delete_generated_material(
        self,
        course_id: str,
        material_type: str,
        material_id: str,
        *,
        owner_user_id: Optional[str] = None,
    ) -> bool:
        try:
            material_file = self._material_file(course_id, material_type, material_id)
            stored = self._load_material_manifest(
                course_id, material_type, material_id
            ) or {}
            if not stored:
                return False
            if not self._material_owner_matches(stored, owner_user_id):
                return False

            artifact_paths = set(stored.get("artifact_paths") or [])
            if stored.get("file_path"):
                artifact_paths.add(stored["file_path"])
            for relative_file_path in artifact_paths:
                attachment_path = self.get_file_path(
                    course_id, str(relative_file_path)
                ).resolve()
                course_root = self.get_course_dir(course_id).resolve()
                try:
                    attachment_path.relative_to(course_root)
                except ValueError:
                    continue
                if attachment_path.is_dir():
                    shutil.rmtree(attachment_path)
                elif attachment_path.exists():
                    attachment_path.unlink()
            media_dir = self._material_dir(course_id, material_type) / (
                f"{self._normalize_material_id(material_id)}_media"
            )
            if media_dir.exists():
                shutil.rmtree(media_dir)
            if self._material_uses_postgres():
                self._material_repository().delete(
                    course_id, material_type, self._normalize_material_id(material_id)
                )
            else:
                material_file.unlink()
            return True
        except Exception as e:
            print(f"Error deleting generated material: {e}")
            return False

    def pin_generated_material(
        self,
        course_id: str,
        material_type: str,
        material_id: str,
        is_pinned: bool = True,
        *,
        owner_user_id: Optional[str] = None,
    ) -> bool:
        try:
            material_data = self._load_material_manifest(
                course_id, material_type, material_id
            )
            if not material_data:
                return False
            if not self._material_owner_matches(material_data, owner_user_id):
                return False

            material_data["is_pinned"] = bool(is_pinned)
            material_data["pinned_at"] = datetime.now().isoformat() if is_pinned else None
            material_data["updated_at"] = datetime.now().isoformat()
            self._persist_material_manifest(material_data)
            return True
        except Exception as e:
            print(f"Error pinning generated material: {e}")
            return False

    def rename_generated_material(
        self,
        course_id: str,
        material_type: str,
        material_id: str,
        title: str,
        *,
        owner_user_id: Optional[str] = None,
    ) -> bool:
        normalized_title = str(title or "").strip()
        if not normalized_title:
            return False
        try:
            material_file = self._material_file(
                course_id, material_type, material_id
            )
            with self._storage_lock():
                material_data = self._load_material_manifest(
                    course_id, material_type, material_id
                )
                if not material_data or not self._material_owner_matches(
                    material_data, owner_user_id
                ):
                    return False
                material_data["title"] = normalized_title
                material_data["name"] = normalized_title
                material_data["version"] = int(material_data.get("version") or 1) + 1
                material_data["updated_at"] = datetime.now().isoformat()
                self._persist_material_manifest(material_data)
            return True
        except Exception as e:
            print(f"Error renaming generated material: {e}")
            return False

    def check_generated_material_integrity(
        self,
        course_id: str,
        material_type: str,
        material_id: str,
        *,
        owner_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        material = self.get_generated_material(
            course_id,
            material_type,
            material_id,
            owner_user_id=owner_user_id,
        )
        if material is None:
            return {"ok": False, "missing": ["manifest"]}
        missing: List[str] = []
        for relative_path in material.get("artifact_paths") or []:
            if not self.get_file_path(course_id, str(relative_path)).exists():
                missing.append(str(relative_path))
        return {
            "ok": not missing,
            "missing": missing,
            "content_hash": material.get("content_hash"),
            "version": material.get("version"),
        }

    def delete_course(self, course_id: str) -> bool:
        course_dir = self.get_course_dir(course_id)
        tombstone = course_dir.with_name(
            f".{course_dir.name}.deleting-{uuid.uuid4().hex}"
        )
        moved_to_tombstone = False
        logical_delete_completed = False
        try:
            if course_dir.exists():
                course_dir.rename(tombstone)
                moved_to_tombstone = True
            if self._course_uses_postgres():
                if not self._course_repository().delete(course_id):
                    if moved_to_tombstone and tombstone.exists():
                        tombstone.rename(course_dir)
                    return False
            else:
                from app.persistence.hooks import shadow_delete_course

                shadow_delete_course(course_id)
            logical_delete_completed = True
            if moved_to_tombstone and tombstone.exists():
                try:
                    shutil.rmtree(tombstone)
                except OSError:
                    log.exception(
                        "Course was deleted but its tombstone directory needs later cleanup: %s",
                        tombstone,
                    )
            return True
        except Exception as e:
            if (
                not logical_delete_completed
                and moved_to_tombstone
                and tombstone.exists()
                and not course_dir.exists()
            ):
                try:
                    tombstone.rename(course_dir)
                except OSError:
                    log.exception("Failed to restore course directory after delete failure")
            print(f"Error deleting course: {e}")
            return False

    @staticmethod
    def _course_uses_postgres() -> bool:
        from app.persistence.modes import PersistenceMode, PersistenceSettings

        return PersistenceSettings.from_environment().course is PersistenceMode.POSTGRES

    @staticmethod
    def _course_repository():
        from app.persistence.dependencies import get_core_postgres_repositories

        _, repository, _ = get_core_postgres_repositories()
        return repository

    def get_file_path(self, course_id: str, relative_path: str) -> Path:
        return self.get_course_dir(course_id) / relative_path

    def file_exists(self, course_id: str, relative_path: str) -> bool:
        return self.get_file_path(course_id, relative_path).exists()


storage_manager = CourseStorageManager()
