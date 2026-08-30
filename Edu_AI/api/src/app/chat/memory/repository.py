from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.engine import Engine

from app.chat.memory.domain import MemoryRecord, MemoryRecordDraft, ProfileFact
from app.database import (
    AgentMemoryAuditEvent,
    AgentMemoryItem,
    ConversationEpisode,
    UserProfileFact,
    database_session,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalized(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _tokens(value: str) -> set[str]:
    text = _normalized(value)
    ascii_tokens = set(re.findall(r"[a-z0-9_]+", text))
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]+", text)
    chinese_tokens: set[str] = set()
    try:
        import jieba

        for chunk in chinese_chunks:
            chinese_tokens.update(
                token for token in jieba.cut(chunk) if len(token.strip()) > 1
            )
    except ImportError:
        pass
    for chunk in chinese_chunks:
        chinese_tokens.update(
            chunk[index : index + 2] for index in range(max(0, len(chunk) - 1))
        )
    return ascii_tokens | chinese_tokens


def _cosine(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


class SqlAlchemyMemoryRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    @staticmethod
    def _fingerprint(draft: MemoryRecordDraft) -> str:
        raw = "|".join(
            (
                draft.subject_user_id,
                draft.course_id or "",
                draft.memory_type,
                draft.profile_axis or "",
                _normalized(draft.content),
            )
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def upsert_memory(self, draft: MemoryRecordDraft) -> MemoryRecord:
        fingerprint = self._fingerprint(draft)
        now = _utc_now()
        with database_session(engine=self._engine) as session:
            record = session.scalar(
                select(AgentMemoryItem).where(
                    AgentMemoryItem.fingerprint == fingerprint
                )
            )
            if draft.supersedes_axis and draft.profile_axis:
                scope_filter = (
                    AgentMemoryItem.course_id.is_(None)
                    if draft.course_id is None
                    else AgentMemoryItem.course_id == draft.course_id
                )
                previous = session.scalars(
                    select(AgentMemoryItem).where(
                        AgentMemoryItem.subject_user_id == draft.subject_user_id,
                        scope_filter,
                        AgentMemoryItem.profile_axis == draft.profile_axis,
                        AgentMemoryItem.status == "active",
                    )
                ).all()
                for item in previous:
                    if record is None or item.memory_id != record.memory_id:
                        item.status = "superseded"
                        item.updated_at = now
            if record is not None:
                record.evidence_count += 1
                record.confidence = max(record.confidence, draft.confidence)
                record.source_id = draft.source_id
                record.source_span = draft.source_span
                record.status = "active"
                record.updated_at = now
                self._upsert_profile(session, record, draft, now)
                session.flush()
                return self._to_memory(record)

            record = AgentMemoryItem(
                memory_id=f"mem-{uuid4().hex}",
                subject_user_id=draft.subject_user_id,
                owner_user_id=draft.owner_user_id,
                course_id=draft.course_id,
                conversation_id=draft.conversation_id,
                task_id=draft.task_id,
                memory_type=draft.memory_type,
                fact_kind=draft.fact_kind,
                content=draft.content,
                structured_payload=dict(draft.structured_payload),
                confidence=draft.confidence,
                importance=draft.importance,
                visibility=draft.visibility,
                status="active",
                source_type=draft.source_type,
                source_id=draft.source_id,
                source_span=draft.source_span,
                profile_axis=draft.profile_axis,
                evidence_count=1,
                fingerprint=fingerprint,
                embedding=draft.embedding,
                embedding_model=draft.embedding_model,
                extractor=draft.extractor,
                extractor_version=draft.extractor_version,
                valid_from=now,
                valid_until=draft.expires_at,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.flush()
            self._upsert_profile(session, record, draft, now)
            session.flush()
            return self._to_memory(record)

    def add_episode(
        self,
        *,
        conversation_id: str,
        owner_user_id: str,
        course_id: str | None,
        summary: str,
        salient_points: list[str],
        extractor: str,
        extractor_version: str,
        confidence: float,
    ) -> str:
        digest = hashlib.sha256(
            f"{conversation_id}|{_normalized(summary)}".encode("utf-8")
        ).hexdigest()[:24]
        episode_id = f"episode-{digest}"
        with database_session(engine=self._engine) as session:
            existing = session.get(ConversationEpisode, episode_id)
            if existing is not None:
                return episode_id
            session.add(
                ConversationEpisode(
                    episode_id=episode_id,
                    conversation_id=conversation_id,
                    owner_user_id=owner_user_id,
                    course_id=course_id,
                    message_start_position=0,
                    message_end_position=1,
                    summary=summary,
                    salient_points=salient_points,
                    extractor=extractor,
                    extractor_version=extractor_version,
                    confidence=confidence,
                    visibility="private",
                    metadata_json={},
                    extracted_at=_utc_now(),
                )
            )
        return episode_id

    @staticmethod
    def _upsert_profile(
        session, record, draft: MemoryRecordDraft, now: datetime
    ) -> None:
        if not draft.profile_axis:
            return
        course_scope_key = draft.course_id or ""
        profile = session.scalar(
            select(UserProfileFact).where(
                UserProfileFact.subject_user_id == draft.subject_user_id,
                UserProfileFact.course_scope_key == course_scope_key,
                UserProfileFact.profile_axis == draft.profile_axis,
                UserProfileFact.status == "active",
            )
        )
        if profile is None:
            profile = UserProfileFact(
                profile_fact_id=f"profile-{uuid4().hex}",
                subject_user_id=draft.subject_user_id,
                course_id=draft.course_id,
                course_scope_key=course_scope_key,
                profile_axis=draft.profile_axis,
                value=draft.content,
                evidence_count=record.evidence_count,
                source_memory_ids=[record.memory_id],
                confidence=draft.confidence,
                visibility=draft.visibility,
                status="active",
                last_seen_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(profile)
            return
        source_ids = list(profile.source_memory_ids or [])
        if record.memory_id not in source_ids:
            source_ids.append(record.memory_id)
        profile.value = draft.content
        profile.evidence_count = max(profile.evidence_count + 1, record.evidence_count)
        profile.source_memory_ids = source_ids
        profile.confidence = max(profile.confidence, draft.confidence)
        profile.last_seen_at = now
        profile.updated_at = now

    def get(self, memory_id: str) -> MemoryRecord | None:
        with database_session(engine=self._engine) as session:
            record = session.get(AgentMemoryItem, memory_id)
            return self._to_memory(record) if record is not None else None

    def search(
        self,
        *,
        subject_user_id: str,
        course_id: str | None,
        query: str,
        limit: int,
        query_embedding: list[float] | None = None,
    ) -> list[MemoryRecord]:
        now = _utc_now()
        scope_filter = (
            AgentMemoryItem.course_id.is_(None)
            if course_id is None
            else AgentMemoryItem.course_id == course_id
        )
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(AgentMemoryItem).where(
                    AgentMemoryItem.subject_user_id == subject_user_id,
                    scope_filter,
                    AgentMemoryItem.status == "active",
                    AgentMemoryItem.visibility.in_(
                        ("private", "course_student", "course_teacher_summary")
                    ),
                    or_(
                        AgentMemoryItem.valid_until.is_(None),
                        AgentMemoryItem.valid_until > now,
                    ),
                )
            ).all()
            query_tokens = _tokens(query)
            ranked: list[tuple[float, AgentMemoryItem]] = []
            for record in records:
                content_tokens = _tokens(record.content)
                lexical = (
                    len(query_tokens & content_tokens)
                    / len(query_tokens | content_tokens)
                    if query_tokens and content_tokens
                    else 0.0
                )
                semantic = _cosine(query_embedding, record.embedding)
                score = 0.6 * semantic + 0.35 * lexical + 0.05 * record.importance
                if not query.strip() or lexical > 0 or semantic > 0:
                    ranked.append((score, record))
            ranked.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
            return [
                self._to_memory(record, score=score) for score, record in ranked[:limit]
            ]

    def list_profile_facts(
        self, *, subject_user_id: str, course_id: str | None = None
    ) -> list[ProfileFact]:
        if course_id is None:
            scope_filter = UserProfileFact.course_id.is_(None)
        else:
            scope_filter = or_(
                UserProfileFact.course_id.is_(None),
                UserProfileFact.course_id == course_id,
            )
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(UserProfileFact)
                .where(
                    UserProfileFact.subject_user_id == subject_user_id,
                    scope_filter,
                    UserProfileFact.status == "active",
                )
                .order_by(
                    UserProfileFact.confidence.desc(),
                    UserProfileFact.last_seen_at.desc(),
                )
            ).all()
            return [self._to_profile(record) for record in records]

    def invalidate(self, *, memory_id: str, subject_user_id: str, reason: str) -> bool:
        with database_session(engine=self._engine) as session:
            record = session.get(AgentMemoryItem, memory_id)
            if record is None or record.subject_user_id != subject_user_id:
                return False
            record.status = "invalidated"
            record.updated_at = _utc_now()
            if record.profile_axis:
                profile = session.scalar(
                    select(UserProfileFact).where(
                        UserProfileFact.subject_user_id == subject_user_id,
                        UserProfileFact.course_scope_key == (record.course_id or ""),
                        UserProfileFact.profile_axis == record.profile_axis,
                        UserProfileFact.status == "active",
                    )
                )
                if profile is not None and memory_id in list(
                    profile.source_memory_ids or []
                ):
                    profile.status = "invalidated"
                    profile.updated_at = _utc_now()
            self._add_audit_in_session(
                session,
                subject_user_id=subject_user_id,
                conversation_id=record.conversation_id,
                event_type="memory.invalidated",
                provider="user",
                decision="invalidated",
                reason=reason,
                payload={"memory_id": memory_id},
                latency_ms=0,
            )
            return True

    def add_audit(
        self,
        *,
        subject_user_id: str,
        conversation_id: str | None,
        event_type: str,
        provider: str,
        decision: str,
        reason: str,
        payload: dict,
        latency_ms: int = 0,
    ) -> None:
        with database_session(engine=self._engine) as session:
            self._add_audit_in_session(
                session,
                subject_user_id=subject_user_id,
                conversation_id=conversation_id,
                event_type=event_type,
                provider=provider,
                decision=decision,
                reason=reason,
                payload=payload,
                latency_ms=latency_ms,
            )

    @staticmethod
    def _add_audit_in_session(session, **values) -> None:
        session.add(
            AgentMemoryAuditEvent(
                audit_id=f"audit-{uuid4().hex}",
                created_at=_utc_now(),
                **values,
            )
        )

    @staticmethod
    def _to_memory(record: AgentMemoryItem, *, score: float = 0.0) -> MemoryRecord:
        return MemoryRecord(
            memory_id=record.memory_id,
            subject_user_id=record.subject_user_id,
            owner_user_id=record.owner_user_id,
            course_id=record.course_id,
            conversation_id=record.conversation_id,
            memory_type=record.memory_type,
            fact_kind=record.fact_kind,
            content=record.content,
            confidence=record.confidence,
            importance=record.importance,
            visibility=record.visibility,
            status=record.status,
            source_type=record.source_type,
            source_id=record.source_id,
            source_span=record.source_span,
            profile_axis=record.profile_axis,
            evidence_count=record.evidence_count,
            score=score,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _to_profile(record: UserProfileFact) -> ProfileFact:
        return ProfileFact(
            profile_fact_id=record.profile_fact_id,
            subject_user_id=record.subject_user_id,
            course_id=record.course_id,
            profile_axis=record.profile_axis,
            value=record.value,
            confidence=record.confidence,
            evidence_count=record.evidence_count,
            visibility=record.visibility,
            status=record.status,
            source_memory_ids=list(record.source_memory_ids or []),
            last_seen_at=record.last_seen_at,
        )
