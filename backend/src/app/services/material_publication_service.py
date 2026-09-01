"""Publish private generated materials as stable, sanitized course snapshots."""

from __future__ import annotations

import copy
import hashlib
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from core.course_storage import CourseStorageManager


PublicationAction = Literal["published", "updated", "unchanged"]


class MaterialPublicationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PublicationResult:
    action: PublicationAction
    source_material_id: str
    material: dict[str, Any]


_COMMON_PUBLICATION_FIELDS = frozenset(
    {
        "title",
        "name",
        "topic",
        "summary",
        "text",
        "status",
        "scope_type",
        "scope_id",
        "file_extension",
    }
)

_PUBLICATION_FIELDS_BY_TYPE: dict[str, frozenset[str]] = {
    "report": _COMMON_PUBLICATION_FIELDS
    | frozenset(
        {
            "content", "final_markdown", "markdown", "report", "report_content",
            "mainContent", "outline", "source_count",
        }
    ),
    "lesson_plan": _COMMON_PUBLICATION_FIELDS | frozenset({"content", "plan"}),
    "quiz": _COMMON_PUBLICATION_FIELDS | frozenset({"content", "questions"}),
    "flashcard": _COMMON_PUBLICATION_FIELDS
    | frozenset({"content", "flashcards"}),
    "graph": _COMMON_PUBLICATION_FIELDS | frozenset({"content"}),
    "game": _COMMON_PUBLICATION_FIELDS | frozenset({"content"}),
    "classroom": _COMMON_PUBLICATION_FIELDS
    | frozenset(
        {"content", "stage", "scenes", "scenes_count", "voice_status", "video_status"}
    ),
    "blog": _COMMON_PUBLICATION_FIELDS
    | frozenset({"content", "final_markdown", "markdown", "outline"}),
    "audio": _COMMON_PUBLICATION_FIELDS | frozenset({"content", "voice_status"}),
    "video": _COMMON_PUBLICATION_FIELDS | frozenset({"content", "video_status"}),
    "ai_lecture_session": _COMMON_PUBLICATION_FIELDS
    | frozenset({"content", "stage", "scenes", "scenes_count"}),
}

_COMMON_PUBLIC_KEYS = frozenset(
    {
        "id", "type", "title", "name", "topic", "summary", "text", "content",
        "status", "count", "duration", "difficulty", "category", "description",
    }
)

_PUBLIC_NESTED_KEYS_BY_TYPE: dict[str, frozenset[str]] = {
    "report": _COMMON_PUBLIC_KEYS
    | frozenset(
        {
            "introduction", "mainContent", "keyFindings", "conclusions",
            "recommendations", "subsections", "sections", "outline", "markdown",
            "final_markdown", "report_content",
        }
    ),
    "lesson_plan": _COMMON_PUBLIC_KEYS
    | frozenset(
        {
            "objectives", "keyPoints", "hardPoints", "process", "homework", "step",
            "knowledge_points", "key_points", "hard_points", "plan",
        }
    ),
    "quiz": _COMMON_PUBLIC_KEYS
    | frozenset(
        {
            "question_type", "questions", "question", "stem", "choices", "options",
            "answer", "correct_answer", "analysis", "explanation", "score", "tags",
        }
    ),
    "flashcard": _COMMON_PUBLIC_KEYS
    | frozenset(
        {
            "cards", "flashcards", "front", "back", "source_doc_id", "show_sources",
        }
    ),
    "graph": _COMMON_PUBLIC_KEYS
    | frozenset({"root", "children", "max_depth", "label", "value"}),
    "game": _COMMON_PUBLIC_KEYS
    | frozenset(
        {
            "game_type", "template_id", "game_data", "html_path", "html_url",
            "categories", "items", "categoryId", "pairs", "left", "right", "matches",
            "pair_id", "card_a", "card_b",
        }
    ),
    "classroom": _COMMON_PUBLIC_KEYS
    | frozenset(
        {
            "stage", "scenes", "scenes_count", "mode", "metadata", "settings", "theme",
            "createdAt", "updatedAt", "version", "actions", "notes", "transition", "canvas",
            "viewportSize", "viewportRatio", "themeColors", "backgroundColor", "fontColor",
            "fontName", "elements", "background", "color", "left", "top", "width", "height",
            "rotate", "defaultFontName", "defaultColor", "opacity", "flipH", "flipV", "locked",
            "groupId", "link", "shadow", "outline", "fill", "line", "points", "src", "poster",
            "autoplay", "loop", "muted", "volume", "elementId", "audioUrl", "start", "end",
            "shape", "latex", "rows", "columns", "data", "code", "language", "state", "key",
            "value", "question", "options", "answer", "explanation",
        }
    ),
    "blog": _COMMON_PUBLIC_KEYS
    | frozenset({"outline", "markdown", "final_markdown", "sections", "subsections"}),
    "audio": _COMMON_PUBLIC_KEYS
    | frozenset({"url", "file_url", "mime_type", "transcript", "voice_status"}),
    "video": _COMMON_PUBLIC_KEYS
    | frozenset({"url", "file_url", "mime_type", "poster", "video_status", "transcript"}),
    "ai_lecture_session": _COMMON_PUBLIC_KEYS
    | frozenset({"stage", "scenes", "scenes_count", "session_id"}),
}


def _sanitize_nested(value: Any, *, allowed_keys: frozenset[str]) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_nested(item, allowed_keys=allowed_keys)
            for key, item in value.items()
            if str(key) in allowed_keys
        }
    if isinstance(value, list):
        return [_sanitize_nested(item, allowed_keys=allowed_keys) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_nested(item, allowed_keys=allowed_keys) for item in value]
    return copy.deepcopy(value)


class MaterialPublicationService:
    def __init__(self, manager: CourseStorageManager) -> None:
        self._manager = manager

    @staticmethod
    def _published_id(
        course_id: str,
        owner_user_id: str,
        material_type: str,
        material_id: str,
    ) -> str:
        identity = (
            f"{course_id}\0{owner_user_id}\0{material_type}\0{material_id}"
        ).encode("utf-8")
        return f"published-{hashlib.sha256(identity).hexdigest()[:20]}"

    def _load_owned_private_source(
        self,
        *,
        course_id: str,
        material_type: str,
        material_id: str,
        owner_user_id: str,
    ) -> dict[str, Any]:
        source = self._manager.get_generated_material(
            course_id,
            material_type,
            material_id,
            owner_user_id=owner_user_id,
        )
        if (
            not source
            or source.get("visibility") != "private"
            or str(source.get("owner_user_id") or "") != owner_user_id
        ):
            raise MaterialPublicationError(
                "MATERIAL_NOT_FOUND", "private material not found"
            )
        return source

    def _validated_artifact_sources(
        self, course_id: str, source: dict[str, Any]
    ) -> list[Path]:
        relative_paths = list(source.get("artifact_paths") or [])
        if source.get("file_path") and source["file_path"] not in relative_paths:
            relative_paths.append(source["file_path"])
        course_root = self._manager.get_course_dir(course_id).resolve()
        resolved_paths: list[Path] = []
        for raw_path in relative_paths:
            candidate = Path(str(raw_path or ""))
            if not str(candidate) or candidate.is_absolute():
                raise MaterialPublicationError(
                    "MATERIAL_ARTIFACT_UNSAFE", "artifact path must be course-relative"
                )
            resolved = (course_root / candidate).resolve()
            try:
                resolved.relative_to(course_root)
            except ValueError as exc:
                raise MaterialPublicationError(
                    "MATERIAL_ARTIFACT_UNSAFE", "artifact path leaves course root"
                ) from exc
            if not resolved.exists():
                raise MaterialPublicationError(
                    "MATERIAL_PUBLICATION_INVALID", "source artifact is missing"
                )
            resolved_paths.append(resolved)
        return resolved_paths

    @staticmethod
    def _validate_artifact_tree(source: Path, course_root: Path) -> None:
        candidates = [source]
        if source.is_dir():
            for root, dirnames, filenames in os.walk(source, followlinks=False):
                candidates.extend(Path(root) / name for name in (*dirnames, *filenames))
        for candidate in candidates:
            is_junction = getattr(candidate, "is_junction", lambda: False)
            if candidate.is_symlink() or is_junction():
                raise MaterialPublicationError(
                    "MATERIAL_ARTIFACT_UNSAFE", "artifact tree contains a link"
                )
            try:
                candidate.resolve().relative_to(course_root)
            except ValueError as exc:
                raise MaterialPublicationError(
                    "MATERIAL_ARTIFACT_UNSAFE", "artifact tree leaves course root"
                ) from exc

    def _stage_artifacts(
        self,
        *,
        course_id: str,
        material_type: str,
        published_id: str,
        sources: list[Path],
    ) -> tuple[Path | None, Path, list[str]]:
        course_root = self._manager.get_course_dir(course_id).resolve()
        parent = (
            course_root / "generated_materials" / "published" / material_type
        )
        final_dir = parent / published_id
        if not sources:
            return None, final_dir, []
        parent.mkdir(parents=True, exist_ok=True)
        staging = parent / f".{published_id}-{uuid.uuid4().hex}.tmp"
        staging.mkdir(parents=True, exist_ok=False)
        published_paths: list[str] = []
        try:
            for index, source in enumerate(sources):
                self._validate_artifact_tree(source, course_root)
                target_name = source.name
                target = staging / target_name
                if target.exists():
                    target = staging / f"{index}-{target_name}"
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
                final_target = final_dir / target.name
                published_paths.append(
                    str(final_target.relative_to(course_root)).replace("\\", "/")
                )
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return staging, final_dir, published_paths

    @staticmethod
    def _swap_artifact_directory(
        staging: Path | None, final_dir: Path
    ) -> Path | None:
        if staging is None:
            return None
        backup: Path | None = None
        if final_dir.exists():
            backup = final_dir.parent / f".{final_dir.name}-{uuid.uuid4().hex}.bak"
            os.replace(final_dir, backup)
        os.replace(staging, final_dir)
        return backup

    @staticmethod
    def _restore_artifact_directory(final_dir: Path, backup: Path | None) -> None:
        if final_dir.exists():
            shutil.rmtree(final_dir, ignore_errors=True)
        if backup and backup.exists():
            os.replace(backup, final_dir)

    @staticmethod
    def _discard_backup(backup: Path | None) -> None:
        if backup and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)

    @staticmethod
    def _restore_manifest(path: Path, previous: bytes | None) -> None:
        if previous is None:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        staged: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.stem}-restore-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                staged = Path(handle.name)
                handle.write(previous)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(staged, path)
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    def _snapshot_payload(
        self,
        *,
        source: dict[str, Any],
        material_type: str,
        owner_user_id: str,
        published_paths: list[str],
    ) -> dict[str, Any]:
        allowed_nested_keys = _PUBLIC_NESTED_KEYS_BY_TYPE.get(
            material_type, _COMMON_PUBLIC_KEYS
        )
        allowed_top_level_fields = _PUBLICATION_FIELDS_BY_TYPE.get(
            material_type, _COMMON_PUBLICATION_FIELDS
        )
        payload = {
            key: _sanitize_nested(source[key], allowed_keys=allowed_nested_keys)
            for key in allowed_top_level_fields
            if key in source
        }
        now = datetime.now().isoformat()
        payload.update(
            {
                "created_by": owner_user_id,
                "published_by": owner_user_id,
                "published_at": now,
                "published_from_material_id": source["material_id"],
                "published_from_owner_user_id": owner_user_id,
                "published_from_version": int(source.get("version") or 1),
                "publication_status": "published",
                "artifact_paths": published_paths,
                "file_path": published_paths[0] if published_paths else None,
            }
        )
        return payload

    def publish(
        self,
        *,
        course_id: str,
        material_type: str,
        material_id: str,
        owner_user_id: str,
    ) -> PublicationResult:
        normalized_owner = str(owner_user_id or "").strip()
        if not normalized_owner:
            raise MaterialPublicationError(
                "MATERIAL_NOT_FOUND", "private material not found"
            )
        with self._manager._storage_lock():
            source = self._load_owned_private_source(
                course_id=course_id,
                material_type=material_type,
                material_id=material_id,
                owner_user_id=normalized_owner,
            )
            published_id = self._published_id(
                course_id,
                normalized_owner,
                material_type,
                source["material_id"],
            )
            existing = self._manager.get_stored_generated_material(
                course_id, material_type, published_id
            )
            source_version = int(source.get("version") or 1)
            if existing and int(existing.get("published_from_version") or 0) == source_version:
                return PublicationResult("unchanged", source["material_id"], existing)

            sources = self._validated_artifact_sources(course_id, source)
            staging, final_dir, published_paths = self._stage_artifacts(
                course_id=course_id,
                material_type=material_type,
                published_id=published_id,
                sources=sources,
            )
            publication_file = self._manager._material_file(
                course_id, material_type, published_id
            )
            previous_manifest = (
                publication_file.read_bytes() if publication_file.exists() else None
            )
            backup: Path | None = None
            try:
                backup = self._swap_artifact_directory(staging, final_dir)
                payload = self._snapshot_payload(
                    source=source,
                    material_type=material_type,
                    owner_user_id=normalized_owner,
                    published_paths=published_paths,
                )
                published = self._manager.save_published_material_manifest(
                    course_id,
                    material_type,
                    published_id,
                    payload,
                )
                if not published:
                    raise MaterialPublicationError(
                        "MATERIAL_PUBLICATION_INVALID", "publication write failed"
                    )
                linked = self._manager.update_generated_material_metadata(
                    course_id,
                    material_type,
                    source["material_id"],
                    {
                        "published_material_id": published_id,
                        "published_version": source_version,
                        "published_at": published["published_at"],
                    },
                )
                if not linked:
                    raise MaterialPublicationError(
                        "MATERIAL_PUBLICATION_INVALID", "source link write failed"
                    )
            except MaterialPublicationError:
                self._restore_artifact_directory(final_dir, backup)
                self._restore_manifest(publication_file, previous_manifest)
                raise
            except Exception as exc:
                self._restore_artifact_directory(final_dir, backup)
                self._restore_manifest(publication_file, previous_manifest)
                raise MaterialPublicationError(
                    "MATERIAL_PUBLICATION_INVALID", "publication failed"
                ) from exc
            self._discard_backup(backup)
            return PublicationResult(
                "updated" if existing else "published",
                source["material_id"],
                published,
            )

    def withdraw(
        self,
        *,
        course_id: str,
        material_type: str,
        published_material_id: str,
    ) -> dict[str, Any]:
        with self._manager._storage_lock():
            published = self._manager.get_stored_generated_material(
                course_id, material_type, published_material_id
            )
            if (
                not published
                or published.get("visibility") != "course"
                or not published.get("published_from_material_id")
                or not published.get("published_from_owner_user_id")
            ):
                raise MaterialPublicationError(
                    "MATERIAL_PUBLICATION_INVALID", "publication not found"
                )
            source = self._manager.get_stored_generated_material(
                course_id,
                material_type,
                str(published["published_from_material_id"]),
            )
            linked_source = bool(
                source
                and source.get("visibility") == "private"
                and source.get("owner_user_id")
                == published.get("published_from_owner_user_id")
            )
            publication_file = self._manager._material_file(
                course_id, material_type, published_material_id
            )
            publication_manifest = publication_file.read_bytes()
            source_file = (
                self._manager._material_file(
                    course_id, material_type, str(source["material_id"])
                )
                if linked_source
                else None
            )
            source_manifest = (
                source_file.read_bytes()
                if source_file is not None and source_file.exists()
                else None
            )
            course_root = self._manager.get_course_dir(course_id).resolve()
            final_dir = (
                course_root
                / "generated_materials"
                / "published"
                / material_type
                / published_material_id
            )
            artifact_backup = final_dir.parent / (
                f".{published_material_id}-{uuid.uuid4().hex}.withdraw.bak"
            )
            if final_dir.exists():
                shutil.copytree(final_dir, artifact_backup, symlinks=True)
            try:
                if not self._manager.delete_generated_material(
                    course_id, material_type, published_material_id
                ):
                    raise MaterialPublicationError(
                        "MATERIAL_PUBLICATION_INVALID", "publication removal failed"
                    )
                if linked_source:
                    cleared = self._manager.update_generated_material_metadata(
                        course_id,
                        material_type,
                        source["material_id"],
                        {
                            "published_material_id": None,
                            "published_version": None,
                            "published_at": None,
                        },
                    )
                    if not cleared:
                        raise MaterialPublicationError(
                            "MATERIAL_PUBLICATION_INVALID",
                            "source publication link removal failed",
                        )
            except Exception as exc:
                self._restore_manifest(publication_file, publication_manifest)
                if source_file is not None:
                    self._restore_manifest(source_file, source_manifest)
                if final_dir.exists():
                    shutil.rmtree(final_dir, ignore_errors=True)
                if artifact_backup.exists():
                    os.replace(artifact_backup, final_dir)
                if isinstance(exc, MaterialPublicationError):
                    raise
                raise MaterialPublicationError(
                    "MATERIAL_PUBLICATION_INVALID", "publication withdrawal failed"
                ) from exc
            if artifact_backup.exists():
                shutil.rmtree(artifact_backup, ignore_errors=True)
            return published
