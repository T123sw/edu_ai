from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Engine

from app.database import (
    KnowledgeDocument,
    KnowledgeBuild,
    KnowledgeGraphVersion,
    KnowledgeLibrary,
    KnowledgeQualityCheck,
    KnowledgeSourceCandidate,
    RuntimeIndexEntry,
    database_session,
)
from app.services.course_knowledge_graph_incremental import incremental_graph_issues

from .postgres_repositories import _timestamp


class KnowledgeBuildRevisionConflict(ValueError):
    pass


class KnowledgeBuildBaselineConflict(ValueError):
    pass


class PostgresKnowledgeRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    @staticmethod
    def _ensure_library(session, library_id: str, entries=None) -> None:
        library = session.get(KnowledgeLibrary, library_id)
        if library is None:
            first = dict((entries or [{}])[0]) if entries else {}
            library = KnowledgeLibrary(
                library_id=library_id,
                library_type=str(first.get("library_type") or "course"),
                course_id=(
                    str(first.get("course_id") or library_id)
                    if str(first.get("library_type") or "course") != "personal"
                    else str(first.get("course_id") or "").strip() or None
                ),
                owner_user_id=str(first.get("owner_user_id") or "").strip() or None,
                metadata_payload={},
            )
            session.add(library)

    def replace_documents(
        self, library_id: str, documents: list[Mapping[str, Any]]
    ) -> None:
        normalized_library_id = str(library_id or "").strip()
        if not normalized_library_id:
            raise ValueError("library_id is required")
        payloads = [dict(item) for item in documents]
        with database_session(engine=self._engine) as session:
            self._ensure_library(session, normalized_library_id, payloads)
            session.execute(
                delete(KnowledgeDocument).where(
                    KnowledgeDocument.library_id == normalized_library_id
                )
            )
            for position, payload in enumerate(payloads):
                document_id = str(
                    payload.get("id")
                    or payload.get("document_id")
                    or hashlib.sha256(
                        str(payload.get("path") or position).encode("utf-8")
                    ).hexdigest()[:24]
                )
                created = payload.get("uploaded_at") or payload.get("created_at")
                session.add(
                    KnowledgeDocument(
                        library_id=normalized_library_id,
                        document_id=document_id,
                        filename=str(payload.get("filename") or payload.get("file_name") or ""),
                        path=str(payload.get("path") or payload.get("physical_path") or "").strip() or None,
                        content_hash=str(payload.get("hash") or payload.get("content_hash") or "").strip() or None,
                        scope_type=str(payload.get("scope_type") or "course"),
                        scope_id=str(payload.get("scope_id") or "").strip() or None,
                        status=str(payload.get("status") or "ready"),
                        created_at=_timestamp(created),
                        updated_at=_timestamp(payload.get("updated_at") or created),
                        raw_payload=payload,
                    )
                )

    def list_documents(self, library_id: str) -> list[dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.library_id == library_id)
                .order_by(KnowledgeDocument.created_at, KnowledgeDocument.document_id)
            ).all()
            return [dict(record.raw_payload or {}) for record in records]

    def delete_library(self, library_id: str) -> bool:
        normalized_library_id = str(library_id or "").strip()
        if not normalized_library_id:
            raise ValueError("library_id is required")
        with database_session(engine=self._engine) as session:
            library = session.get(KnowledgeLibrary, normalized_library_id)
            if library is None:
                return False
            build_ids = select(KnowledgeBuild.build_id).where(
                KnowledgeBuild.library_id == normalized_library_id
            )
            session.execute(
                delete(KnowledgeSourceCandidate).where(
                    KnowledgeSourceCandidate.build_id.in_(build_ids)
                )
            )
            session.execute(
                delete(KnowledgeQualityCheck).where(
                    KnowledgeQualityCheck.build_id.in_(build_ids)
                )
            )
            session.execute(
                delete(KnowledgeBuild).where(
                    KnowledgeBuild.library_id == normalized_library_id
                )
            )
            session.execute(
                delete(KnowledgeDocument).where(
                    KnowledgeDocument.library_id == normalized_library_id
                )
            )
            session.execute(
                delete(KnowledgeGraphVersion).where(
                    KnowledgeGraphVersion.library_id == normalized_library_id
                )
            )
            session.delete(library)
            return True

    def upsert_graph(self, library_id: str, graph: Mapping[str, Any]) -> None:
        payload = dict(graph)
        graph_data = dict(payload.get("data") or {})
        published_at = (
            datetime.now(timezone.utc)
            if graph_data.get("publication_status") == "published"
            else None
        )
        with database_session(engine=self._engine) as session:
            self._ensure_library(session, library_id)
            current = session.scalar(
                select(func.max(KnowledgeGraphVersion.version)).where(
                    KnowledgeGraphVersion.library_id == library_id
                )
            )
            session.add(
                KnowledgeGraphVersion(
                    library_id=library_id,
                    version=int(current or 0) + 1,
                    source_build_id=str(graph_data.get("source_build_id") or "").strip() or None,
                    published_at=published_at,
                    graph_payload=payload,
                )
            )

    def get_graph(self, library_id: str) -> dict[str, Any] | None:
        with database_session(engine=self._engine) as session:
            record = session.scalar(
                select(KnowledgeGraphVersion)
                .where(KnowledgeGraphVersion.library_id == library_id)
                .order_by(KnowledgeGraphVersion.version.desc())
                .limit(1)
            )
            return dict(record.graph_payload) if record is not None else None

    def get_latest_graph_version(self, library_id: str) -> dict[str, Any] | None:
        with database_session(engine=self._engine) as session:
            record = session.scalar(
                select(KnowledgeGraphVersion)
                .where(KnowledgeGraphVersion.library_id == library_id)
                .order_by(KnowledgeGraphVersion.version.desc())
                .limit(1)
            )
            if record is None:
                return None
            return {
                "version": int(record.version),
                "graph": dict(record.graph_payload or {}),
            }

    def replace_runtime_index(
        self, index_name: str, entries: Mapping[str, Mapping[str, Any]]
    ) -> None:
        normalized_name = str(index_name or "").strip()
        with database_session(engine=self._engine) as session:
            session.execute(
                delete(RuntimeIndexEntry).where(
                    RuntimeIndexEntry.index_name == normalized_name
                )
            )
            for entry_key, source in entries.items():
                payload = dict(source or {})
                session.add(
                    RuntimeIndexEntry(
                        index_name=normalized_name,
                        entry_key=str(entry_key),
                        owner_user_id=str(payload.get("owner") or payload.get("owner_user_id") or "").strip() or None,
                        content_hash=str(payload.get("hash") or payload.get("content_hash") or "").strip() or None,
                        payload=payload,
                    )
                )

    def load_runtime_index(self, index_name: str) -> dict[str, dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(RuntimeIndexEntry)
                .where(RuntimeIndexEntry.index_name == index_name)
                .order_by(RuntimeIndexEntry.entry_key)
            ).all()
            return {record.entry_key: dict(record.payload or {}) for record in records}

    def create_build_draft(
        self,
        *,
        course_id: str,
        triggered_by: str,
        plan: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized_course_id = str(course_id or "").strip()
        if not normalized_course_id:
            raise ValueError("course_id is required")
        build_id = f"kb-{uuid4().hex}"
        now = datetime.now(timezone.utc)
        plan_snapshot = dict(plan)
        plan_snapshot.setdefault("source_candidates", [])
        plan_snapshot.setdefault("warnings", [])
        with database_session(engine=self._engine) as session:
            self._ensure_library(
                session,
                normalized_course_id,
                [{"library_type": "course", "course_id": normalized_course_id}],
            )
            session.add(
                KnowledgeBuild(
                    build_id=build_id,
                    library_id=normalized_course_id,
                    triggered_by=str(triggered_by or "").strip(),
                    status="draft",
                    phase="draft_config",
                    progress=0,
                    revision=1,
                    plan_snapshot=plan_snapshot,
                    metrics={},
                    created_at=now,
                    updated_at=now,
                )
            )
        result = self.get_build(build_id)
        if result is None:
            raise RuntimeError("failed to persist knowledge build draft")
        return result

    def create_build_preview(
        self,
        *,
        course_id: str,
        triggered_by: str,
        plan: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized_course_id = str(course_id or "").strip()
        if not normalized_course_id:
            raise ValueError("course_id is required")
        build_id = f"kb-{uuid4().hex}"
        now = datetime.now(timezone.utc)
        plan_snapshot = dict(plan)
        candidates = [dict(item) for item in plan_snapshot.get("source_candidates") or []]
        with database_session(engine=self._engine) as session:
            self._ensure_library(
                session,
                normalized_course_id,
                [{"library_type": "course", "course_id": normalized_course_id}],
            )
            session.add(
                KnowledgeBuild(
                    build_id=build_id,
                    library_id=normalized_course_id,
                    triggered_by=str(triggered_by or "").strip(),
                    status="draft",
                    phase="source_review",
                    progress=0,
                    revision=1,
                    plan_snapshot=plan_snapshot,
                    metrics={"candidate_count": len(candidates)},
                    created_at=now,
                    updated_at=now,
                )
            )
            for candidate in candidates:
                original_id = str(candidate.get("candidate_id") or uuid4().hex)
                session.add(
                    KnowledgeSourceCandidate(
                        candidate_id=f"{build_id}:{original_id}",
                        build_id=build_id,
                        topic_id=str(candidate.get("topic_id") or "").strip() or None,
                        url=str(candidate.get("url") or "").strip(),
                        title=str(candidate.get("title") or candidate.get("url") or ""),
                        domain=str(candidate.get("domain") or ""),
                        source_type=str(candidate.get("source_type") or "web"),
                        language=str(candidate.get("language") or "").strip() or None,
                        authority_tier=str(candidate.get("authority_tier") or "").strip() or None,
                        license_info={
                            "name": candidate.get("license_name"),
                            "url": candidate.get("license_url"),
                        },
                        review_status=str(candidate.get("review_status") or "pending"),
                        review_reason=str(candidate.get("review_reason") or "").strip() or None,
                        selected=bool(candidate.get("selected")),
                        relevance_score=float(candidate.get("relevance_score") or 0),
                        metadata_payload=dict(candidate.get("metadata") or {}),
                        created_at=now,
                    )
                )
        return {
            "build_id": build_id,
            "status": "draft",
            "phase": "source_review",
            **plan_snapshot,
        }

    def get_build(self, build_id: str) -> dict[str, Any] | None:
        with database_session(engine=self._engine) as session:
            record = session.get(KnowledgeBuild, build_id)
            if record is None:
                return None
            candidates = session.scalars(
                select(KnowledgeSourceCandidate)
                .where(KnowledgeSourceCandidate.build_id == build_id)
                .order_by(KnowledgeSourceCandidate.created_at, KnowledgeSourceCandidate.candidate_id)
            ).all()
            checks = session.scalars(
                select(KnowledgeQualityCheck)
                .where(KnowledgeQualityCheck.build_id == build_id)
                .order_by(KnowledgeQualityCheck.check_id)
            ).all()
            plan = dict(record.plan_snapshot or {})
            plan["source_candidates"] = [
                {
                    "candidate_id": item.candidate_id.split(":", 1)[-1],
                    "topic_id": item.topic_id,
                    "title": item.title,
                    "url": item.url,
                    "domain": item.domain,
                    "source_type": item.source_type,
                    "language": item.language,
                    "license_name": (item.license_info or {}).get("name"),
                    "license_url": (item.license_info or {}).get("url"),
                    "authority_tier": item.authority_tier,
                    "review_status": item.review_status,
                    "review_reason": item.review_reason,
                    "selected": item.selected,
                    "relevance_score": item.relevance_score,
                    "metadata": dict(item.metadata_payload or {}),
                }
                for item in candidates
            ]
            return {
                "build_id": record.build_id,
                "library_id": record.library_id,
                "status": record.status,
                "phase": record.phase,
                "progress": record.progress,
                "revision": record.revision,
                "graph_confirmed_at": (
                    record.graph_confirmed_at.isoformat()
                    if record.graph_confirmed_at
                    else None
                ),
                "confirmed_graph_revision": record.confirmed_graph_revision,
                "confirmed_by": record.confirmed_by,
                "metrics": dict(record.metrics or {}),
                "quality_score": record.quality_score,
                "error": dict(record.error) if record.error else None,
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat(),
                "quality_checks": [
                    {
                        "check_type": item.check_type,
                        "status": item.status,
                        "score": item.score,
                        "threshold": item.threshold,
                        "details": dict(item.details or {}),
                    }
                    for item in checks
                ],
                **plan,
            }

    def update_build_draft(
        self,
        build_id: str,
        *,
        expected_revision: int,
        changes: Mapping[str, Any],
        phase: str = "draft_config",
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with database_session(engine=self._engine) as session:
            record = session.get(KnowledgeBuild, build_id)
            if record is None:
                raise KeyError(build_id)
            if record.status != "draft":
                raise ValueError("只有草案状态的构建可以修改")
            if record.revision != int(expected_revision):
                raise KnowledgeBuildRevisionConflict(
                    f"构建草案版本冲突：当前 {record.revision}，提交 {expected_revision}"
                )
            next_plan = dict(record.plan_snapshot or {})
            next_plan.update(dict(changes))
            result = session.execute(
                update(KnowledgeBuild)
                .where(
                    KnowledgeBuild.build_id == build_id,
                    KnowledgeBuild.status == "draft",
                    KnowledgeBuild.revision == int(expected_revision),
                )
                .values(
                    phase=str(phase),
                    revision=int(expected_revision) + 1,
                    plan_snapshot=next_plan,
                    graph_confirmed_at=None,
                    confirmed_graph_revision=None,
                    confirmed_by=None,
                    updated_at=now,
                    error=None,
                )
            )
            if result.rowcount != 1:
                raise KnowledgeBuildRevisionConflict("构建草案已被其他请求更新")
        loaded = self.get_build(build_id)
        if loaded is None:
            raise KeyError(build_id)
        return loaded

    def confirm_build_graph(
        self,
        build_id: str,
        *,
        expected_revision: int,
        confirmed_by: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with database_session(engine=self._engine) as session:
            record = session.get(KnowledgeBuild, build_id)
            if record is None:
                raise KeyError(build_id)
            if record.status != "draft":
                raise ValueError("只有草案状态的构建可以确认")
            if record.revision != int(expected_revision):
                raise KnowledgeBuildRevisionConflict(
                    f"构建草案版本冲突：当前 {record.revision}，提交 {expected_revision}"
                )
            if not dict(record.plan_snapshot or {}).get("graph_draft"):
                raise ValueError("图谱草案不存在，无法确认")
            result = session.execute(
                update(KnowledgeBuild)
                .where(
                    KnowledgeBuild.build_id == build_id,
                    KnowledgeBuild.status == "draft",
                    KnowledgeBuild.revision == int(expected_revision),
                )
                .values(
                    phase="graph_confirmed",
                    graph_confirmed_at=now,
                    confirmed_graph_revision=int(expected_revision),
                    confirmed_by=str(confirmed_by or "").strip(),
                    updated_at=now,
                    error=None,
                )
            )
            if result.rowcount != 1:
                raise KnowledgeBuildRevisionConflict("构建草案已被其他请求更新")
        loaded = self.get_build(build_id)
        if loaded is None:
            raise KeyError(build_id)
        return loaded

    def update_build(
        self,
        build_id: str,
        *,
        status: str,
        phase: str,
        progress: int,
        metrics: Mapping[str, Any] | None = None,
        quality_score: float | None = None,
        error: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with database_session(engine=self._engine) as session:
            record = session.get(KnowledgeBuild, build_id)
            if record is None:
                raise KeyError(build_id)
            record.status = str(status)
            record.phase = str(phase)
            record.progress = max(0, min(100, int(progress)))
            record.updated_at = now
            if record.started_at is None and status in {"running", "publishing"}:
                record.started_at = now
            if metrics is not None:
                record.metrics = dict(metrics)
            if quality_score is not None:
                record.quality_score = float(quality_score)
            record.error = dict(error) if error else None
            if status in {"succeeded", "failed", "blocked", "canceled"}:
                record.finished_at = now
            if status == "succeeded":
                record.published_at = now
        result = self.get_build(build_id)
        if result is None:
            raise KeyError(build_id)
        return result

    def replace_build_source_candidates(
        self,
        build_id: str,
        *,
        topics: list[Mapping[str, Any]],
        candidates: list[Mapping[str, Any]],
        warnings: list[Mapping[str, Any]],
        discovery_metrics: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Persist discovery results during an immutable, already-started build."""
        now = datetime.now(timezone.utc)
        with database_session(engine=self._engine) as session:
            record = session.get(KnowledgeBuild, build_id)
            if record is None:
                raise KeyError(build_id)
            if record.status not in {"queued", "running"}:
                raise ValueError("只有已启动的构建可以写入网络发现结果")
            session.execute(
                delete(KnowledgeSourceCandidate).where(
                    KnowledgeSourceCandidate.build_id == build_id
                )
            )
            plan = dict(record.plan_snapshot or {})
            plan["topics"] = [dict(item) for item in topics]
            plan["warnings"] = [*list(plan.get("warnings") or []), *[dict(item) for item in warnings]]
            record.plan_snapshot = plan
            record.metrics = {**dict(record.metrics or {}), "source_discovery": dict(discovery_metrics)}
            record.updated_at = now
            for candidate in candidates:
                original_id = str(candidate.get("candidate_id") or uuid4().hex)
                session.add(
                    KnowledgeSourceCandidate(
                        candidate_id=f"{build_id}:{original_id}",
                        build_id=build_id,
                        topic_id=str(candidate.get("topic_id") or "").strip() or None,
                        url=str(candidate.get("url") or "").strip(),
                        title=str(candidate.get("title") or candidate.get("url") or ""),
                        domain=str(candidate.get("domain") or ""),
                        source_type=str(candidate.get("source_type") or "web"),
                        language=str(candidate.get("language") or "").strip() or None,
                        authority_tier=str(candidate.get("authority_tier") or "").strip() or None,
                        license_info={
                            "name": candidate.get("license_name"),
                            "url": candidate.get("license_url"),
                        },
                        review_status=str(candidate.get("review_status") or "discovered"),
                        review_reason=str(candidate.get("review_reason") or "").strip() or None,
                        selected=bool(candidate.get("selected")),
                        relevance_score=float(candidate.get("relevance_score") or 0),
                        metadata_payload=dict(candidate.get("metadata") or {}),
                        created_at=now,
                    )
                )
        loaded = self.get_build(build_id)
        if loaded is None:
            raise KeyError(build_id)
        return loaded

    def update_source_candidate_result(
        self,
        build_id: str,
        candidate_id: str,
        *,
        review_status: str,
        review_reason: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        with database_session(engine=self._engine) as session:
            record = session.get(
                KnowledgeSourceCandidate,
                f"{build_id}:{candidate_id}",
            )
            if record is None:
                raise KeyError(candidate_id)
            record.review_status = str(review_status)
            record.review_reason = str(review_reason or "").strip() or None
            if metadata is not None:
                record.metadata_payload = {
                    **dict(record.metadata_payload or {}),
                    **dict(metadata),
                }

    def queue_build(self, build_id: str, *, selected_source_count: int) -> None:
        now = datetime.now(timezone.utc)
        with database_session(engine=self._engine) as session:
            result = session.execute(
                update(KnowledgeBuild)
                .where(
                    KnowledgeBuild.build_id == build_id,
                    KnowledgeBuild.status == "draft",
                    KnowledgeBuild.graph_confirmed_at.is_not(None),
                    KnowledgeBuild.confirmed_graph_revision
                    == KnowledgeBuild.revision,
                )
                .values(
                    status="queued",
                    phase="queued",
                    progress=0,
                    metrics={"selected_source_count": int(selected_source_count)},
                    updated_at=now,
                    error=None,
                )
            )
            if result.rowcount != 1:
                current = session.get(KnowledgeBuild, build_id)
                if current is None:
                    raise KeyError(build_id)
                if (
                    current.graph_confirmed_at is None
                    or current.confirmed_graph_revision != current.revision
                ):
                    raise ValueError("知识图谱尚未确认，不能启动正式构建")
                raise ValueError("该构建计划已经启动或不再可用")

    def requeue_build(self, build_id: str) -> None:
        now = datetime.now(timezone.utc)
        with database_session(engine=self._engine) as session:
            result = session.execute(
                update(KnowledgeBuild)
                .where(
                    KnowledgeBuild.build_id == build_id,
                    KnowledgeBuild.status.in_({"blocked", "failed"}),
                    KnowledgeBuild.graph_confirmed_at.is_not(None),
                    KnowledgeBuild.confirmed_graph_revision == KnowledgeBuild.revision,
                )
                .values(
                    status="queued",
                    phase="retry_queued",
                    progress=0,
                    updated_at=now,
                    finished_at=None,
                    error=None,
                )
            )
            if result.rowcount != 1:
                raise ValueError("只有已确认且失败或阻塞的构建可以重试")

    def record_quality_check(
        self,
        build_id: str,
        *,
        check_type: str,
        status: str,
        score: float | None,
        threshold: float | None,
        details: Mapping[str, Any],
    ) -> None:
        with database_session(engine=self._engine) as session:
            if session.get(KnowledgeBuild, build_id) is None:
                raise KeyError(build_id)
            session.add(
                KnowledgeQualityCheck(
                    build_id=build_id,
                    check_type=check_type,
                    status=status,
                    score=score,
                    threshold=threshold,
                    details=dict(details),
                    created_at=datetime.now(timezone.utc),
                )
            )

    def publish_build(
        self,
        build_id: str,
        *,
        graph: Mapping[str, Any],
        document_ids: list[str],
        metrics: Mapping[str, Any],
        quality_score: float,
    ) -> int:
        now = datetime.now(timezone.utc)
        with database_session(engine=self._engine) as session:
            build = session.get(KnowledgeBuild, build_id)
            if build is None:
                raise KeyError(build_id)
            if build.status != "publishing":
                raise ValueError("构建记录不在可发布状态")
            plan = dict(build.plan_snapshot or {})
            config = dict(plan.get("config") or {})
            if config.get("update_strategy") == "incremental":
                expected = plan.get("baseline_graph_version")
                current_version = session.scalar(
                    select(func.max(KnowledgeGraphVersion.version)).where(
                        KnowledgeGraphVersion.library_id == build.library_id
                    )
                )
                normalized_current = (
                    int(current_version) if current_version is not None else None
                )
                if expected != normalized_current:
                    raise KnowledgeBuildBaselineConflict(
                        f"图谱基线版本冲突：草案 {expected}，当前 {normalized_current}"
                    )
                issues = incremental_graph_issues(plan.get("baseline_graph"), graph)
                if issues:
                    raise ValueError(
                        {"code": "GRAPH_BASELINE_VIOLATION", "issues": issues}
                    )
            normalized_document_ids = {str(item) for item in document_ids if str(item)}
            if normalized_document_ids:
                documents = session.scalars(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.library_id == build.library_id,
                        KnowledgeDocument.document_id.in_(normalized_document_ids),
                    )
                ).all()
                if len(documents) != len(normalized_document_ids):
                    raise ValueError("待发布课程文档记录不完整")
                for document in documents:
                    payload = dict(document.raw_payload or {})
                    payload["status"] = "ready"
                    document.status = "ready"
                    document.updated_at = now
                    document.raw_payload = payload
            current = session.scalar(
                select(func.max(KnowledgeGraphVersion.version)).where(
                    KnowledgeGraphVersion.library_id == build.library_id
                )
            )
            next_version = int(current or 0) + 1
            session.add(
                KnowledgeGraphVersion(
                    library_id=build.library_id,
                    version=next_version,
                    source_build_id=build_id,
                    published_at=now,
                    graph_payload=dict(graph),
                )
            )
            build.status = "succeeded"
            build.phase = "published"
            build.progress = 100
            build.metrics = dict(metrics)
            build.quality_score = float(quality_score)
            build.error = None
            build.updated_at = now
            build.finished_at = now
            build.published_at = now
        return next_version

    def list_graph_versions(self, library_id: str) -> list[dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(KnowledgeGraphVersion)
                .where(KnowledgeGraphVersion.library_id == library_id)
                .order_by(KnowledgeGraphVersion.version.desc())
            ).all()
            return [
                {
                    "version": item.version,
                    "source_build_id": item.source_build_id,
                    "created_at": item.created_at.isoformat(),
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                    "node_count": int((item.graph_payload or {}).get("data", {}).get("node_count") or 0),
                }
                for item in records
            ]

    def rollback_graph(self, library_id: str, version: int) -> dict[str, Any]:
        with database_session(engine=self._engine) as session:
            target = session.scalar(
                select(KnowledgeGraphVersion).where(
                    KnowledgeGraphVersion.library_id == library_id,
                    KnowledgeGraphVersion.version == int(version),
                )
            )
            if target is None:
                raise KeyError(version)
            current = session.scalar(
                select(func.max(KnowledgeGraphVersion.version)).where(
                    KnowledgeGraphVersion.library_id == library_id
                )
            )
            payload = dict(target.graph_payload or {})
            data = dict(payload.get("data") or {})
            data.update({"publication_status": "published", "rolled_back_from_version": int(version)})
            payload["data"] = data
            next_version = int(current or 0) + 1
            session.add(
                KnowledgeGraphVersion(
                    library_id=library_id,
                    version=next_version,
                    source_build_id=target.source_build_id,
                    published_at=datetime.now(timezone.utc),
                    graph_payload=payload,
                )
            )
        return {"version": next_version, "rolled_back_from_version": int(version), "graph": payload}
