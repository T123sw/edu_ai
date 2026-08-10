from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from app.database import ArtifactFile, Material, MaterialVersion, database_session

from .postgres_repositories import _iso_timestamp, _required_text, _timestamp


class PostgresMaterialRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def upsert(self, material: Mapping[str, Any]) -> None:
        payload = dict(material)
        course_id = _required_text(payload.get("course_id"), "course_id")
        material_type = _required_text(payload.get("material_type"), "material_type")
        material_id = _required_text(payload.get("material_id"), "material_id")
        key = (course_id, material_type, material_id)
        version = int(payload.get("version") or 1)
        updated_at = _timestamp(payload.get("updated_at"))
        with database_session(engine=self._engine) as session:
            record = session.get(Material, key)
            if record is None:
                record = Material(
                    course_id=course_id,
                    material_type=material_type,
                    material_id=material_id,
                )
                session.add(record)
            record.title = str(
                payload.get("title") or payload.get("topic") or material_id
            )
            record.status = str(payload.get("status") or "ready")
            record.visibility = str(payload.get("visibility") or "course")
            record.owner_user_id = str(
                payload.get("owner_user_id") or payload.get("created_by") or ""
            ).strip() or None
            record.scope_type = str(payload.get("scope_type") or "course")
            record.scope_id = str(payload.get("scope_id") or "").strip() or None
            record.version = version
            record.source_job_id = (
                str(payload.get("source_job_id") or "").strip() or None
            )
            record.content_hash = (
                str(payload.get("content_hash") or "").strip() or None
            )
            record.is_pinned = bool(payload.get("is_pinned", False))
            record.pinned_at = (
                _timestamp(payload.get("pinned_at"))
                if str(payload.get("pinned_at") or "").strip()
                else None
            )
            record.created_at = _timestamp(payload.get("created_at"))
            record.updated_at = updated_at
            record.raw_payload = payload

            existing_version = session.scalar(
                select(MaterialVersion).where(
                    MaterialVersion.course_id == course_id,
                    MaterialVersion.material_type == material_type,
                    MaterialVersion.material_id == material_id,
                    MaterialVersion.version == version,
                )
            )
            if existing_version is None:
                session.add(
                    MaterialVersion(
                        course_id=course_id,
                        material_type=material_type,
                        material_id=material_id,
                        version=version,
                        created_at=updated_at,
                        payload=payload,
                    )
                )

            session.execute(
                delete(ArtifactFile).where(
                    ArtifactFile.course_id == course_id,
                    ArtifactFile.material_type == material_type,
                    ArtifactFile.material_id == material_id,
                )
            )
            artifact_paths = list(payload.get("artifact_paths") or [])
            if payload.get("file_path") and payload["file_path"] not in artifact_paths:
                artifact_paths.append(payload["file_path"])
            for path in dict.fromkeys(str(item) for item in artifact_paths if item):
                session.add(
                    ArtifactFile(
                        course_id=course_id,
                        material_type=material_type,
                        material_id=material_id,
                        path=path,
                        content_hash=record.content_hash,
                        metadata_payload={},
                    )
                )

    def get(
        self, course_id: str, material_type: str, material_id: str
    ) -> dict[str, Any] | None:
        key = (
            _required_text(course_id, "course_id"),
            _required_text(material_type, "material_type"),
            _required_text(material_id, "material_id"),
        )
        with database_session(engine=self._engine) as session:
            record = session.get(Material, key)
            return self._payload(record) if record is not None else None

    def list(
        self, course_id: str, material_type: str | None = None
    ) -> list[dict[str, Any]]:
        normalized_course_id = _required_text(course_id, "course_id")
        with database_session(engine=self._engine) as session:
            statement = select(Material).where(Material.course_id == normalized_course_id)
            if material_type:
                statement = statement.where(Material.material_type == material_type)
            records = session.scalars(
                statement.order_by(Material.updated_at.desc(), Material.material_id)
            ).all()
            return [self._payload(record) for record in records]

    def delete(self, course_id: str, material_type: str, material_id: str) -> bool:
        key = (
            _required_text(course_id, "course_id"),
            _required_text(material_type, "material_type"),
            _required_text(material_id, "material_id"),
        )
        with database_session(engine=self._engine) as session:
            record = session.get(Material, key)
            if record is None:
                return False
            session.delete(record)
            return True

    @staticmethod
    def _payload(record: Material) -> dict[str, Any]:
        payload = dict(record.raw_payload or {})
        payload.update(
            {
                "course_id": record.course_id,
                "material_type": record.material_type,
                "material_id": record.material_id,
                "title": record.title,
                "status": record.status,
                "visibility": record.visibility,
                "owner_user_id": record.owner_user_id,
                "scope_type": record.scope_type,
                "scope_id": record.scope_id,
                "version": record.version,
                "source_job_id": record.source_job_id,
                "content_hash": record.content_hash,
                "is_pinned": record.is_pinned,
                "pinned_at": (
                    _iso_timestamp(record.pinned_at) if record.pinned_at else None
                ),
                "created_at": _iso_timestamp(record.created_at),
                "updated_at": _iso_timestamp(record.updated_at),
            }
        )
        return payload
