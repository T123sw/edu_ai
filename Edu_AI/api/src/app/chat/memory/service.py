from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.chat.memory.domain import (
    AgentMemoryContext,
    CandidateExtractionResult,
    MemoryCandidate,
    MemoryPolicyDecision,
    MemoryRecordDraft,
    MemoryWriteResult,
)
from app.chat.memory.langmem_adapter import LangMemAdapter
from app.chat.memory.policy import MemoryWritePolicy
from app.chat.memory.rule_extractor import RuleMemoryExtractor
from app.chat.memory.settings import AgentMemorySettings


def _actor_id(actor: Any) -> str:
    if isinstance(actor, dict):
        return str(actor.get("user_id") or actor.get("username") or "").strip()
    return str(
        getattr(actor, "user_id", None)
        or getattr(actor, "username", None)
        or actor
        or ""
    ).strip()


_LANGMEM_EXECUTOR = ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="agent-memory-langmem"
)


class AgentMemoryService:
    def __init__(
        self,
        *,
        repository,
        settings: AgentMemorySettings | None = None,
        langmem_adapter: LangMemAdapter | None = None,
        rule_extractor: RuleMemoryExtractor | None = None,
        policy: MemoryWritePolicy | None = None,
        embedding_provider=None,
    ):
        self.repository = repository
        self.settings = settings or AgentMemorySettings.from_environment()
        self.langmem_adapter = langmem_adapter or LangMemAdapter(settings=self.settings)
        self.rule_extractor = rule_extractor or RuleMemoryExtractor()
        self.policy = policy or MemoryWritePolicy(
            min_confidence=self.settings.min_confidence
        )
        self.embedding_provider = embedding_provider

    def _embed(self, text: str) -> tuple[list[float] | None, str | None]:
        if not self.settings.embedding_enabled:
            return None, None
        try:
            if self.embedding_provider is None:
                from app.chat.memory.embedding import MemoryEmbeddingProvider

                self.embedding_provider = MemoryEmbeddingProvider()
            return self.embedding_provider.embed(
                text
            ), self.embedding_provider.model_name
        except Exception:
            return None, None

    def persist_turn(
        self,
        *,
        actor,
        conversation_id: str,
        course_id: str | None,
        user_message: str,
        assistant_message: str,
        agent_state: dict,
        tool_events: list[dict],
    ) -> MemoryWriteResult:
        subject_user_id = _actor_id(actor)
        if not self.settings.enabled or not subject_user_id or not conversation_id:
            return MemoryWriteResult(provider_status="disabled")

        rule_candidates = self.rule_extractor.extract(user_message)
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ]
        policy_hint = {
            "allowed_types": [
                "preference",
                "profile_fact",
                "episode",
                "correction",
                "strategy_hint",
            ],
            "course_id": course_id,
        }
        if self.settings.langmem_enabled and self.settings.langmem_background:
            langmem_result = CandidateExtractionResult(
                provider="langmem", status="scheduled"
            )
            candidates = rule_candidates
        else:
            langmem_result = self.langmem_adapter.extract_candidates(
                messages=messages,
                existing_memories=[],
                policy_hint=policy_hint,
            )
            candidates = self._merge_candidates(
                langmem_result.candidates, rule_candidates
            )

        result = self._persist_candidates(
            subject_user_id=subject_user_id,
            conversation_id=conversation_id,
            course_id=course_id,
            candidates=candidates,
            provider=("langmem" if langmem_result.status == "ok" else "rules"),
            provider_status=langmem_result.status,
            latency_ms=langmem_result.latency_ms,
            source_text=user_message,
        )
        if self.settings.langmem_enabled and self.settings.langmem_background:
            _LANGMEM_EXECUTOR.submit(
                self._persist_langmem_background,
                subject_user_id=subject_user_id,
                conversation_id=conversation_id,
                course_id=course_id,
                messages=messages,
                policy_hint=policy_hint,
            )
        return result

    def _persist_langmem_background(
        self,
        *,
        subject_user_id: str,
        conversation_id: str,
        course_id: str | None,
        messages: list[dict],
        policy_hint: dict,
    ) -> None:
        langmem_result = self.langmem_adapter.extract_candidates(
            messages=messages,
            existing_memories=[],
            policy_hint=policy_hint,
        )
        if langmem_result.status != "ok":
            self.repository.add_audit(
                subject_user_id=subject_user_id,
                conversation_id=conversation_id,
                event_type="langmem.completed",
                provider="langmem",
                decision="error",
                reason=langmem_result.error or langmem_result.status,
                payload={"candidate_count": 0},
                latency_ms=langmem_result.latency_ms,
            )
            return
        self._persist_candidates(
            subject_user_id=subject_user_id,
            conversation_id=conversation_id,
            course_id=course_id,
            candidates=langmem_result.candidates,
            provider="langmem",
            provider_status="ok",
            latency_ms=langmem_result.latency_ms,
            source_text=next(
                (
                    str(message.get("content") or "")
                    for message in messages
                    if message.get("role") == "user"
                ),
                "",
            ),
        )

    def _persist_candidates(
        self,
        *,
        subject_user_id: str,
        conversation_id: str,
        course_id: str | None,
        candidates: list[MemoryCandidate],
        provider: str,
        provider_status: str,
        latency_ms: int,
        source_text: str,
    ) -> MemoryWriteResult:
        decisions = []
        for candidate in candidates:
            decision = self.policy.evaluate(candidate)
            if decision.allowed and candidate.source_span not in source_text:
                decision = MemoryPolicyDecision(
                    allowed=False,
                    reason="source_span_not_found",
                    candidate=candidate,
                )
            decisions.append(decision)
        result = MemoryWriteResult(
            candidate_count=len(candidates),
            accepted_count=sum(decision.allowed for decision in decisions),
            rejected_count=sum(not decision.allowed for decision in decisions),
            shadow_candidate_count=len(candidates) if self.settings.shadow_mode else 0,
            provider=provider,
            provider_status=provider_status,
            decisions=decisions,
        )

        for decision in decisions:
            candidate = decision.candidate
            audit_payload = {
                "memory_type": candidate.memory_type,
                "content": candidate.content,
                "source_span": candidate.source_span,
                "confidence": candidate.confidence,
                "shadow_mode": self.settings.shadow_mode,
            }
            self.repository.add_audit(
                subject_user_id=subject_user_id,
                conversation_id=conversation_id,
                event_type="candidate.evaluated",
                provider=result.provider,
                decision=(
                    "shadow"
                    if self.settings.shadow_mode and decision.allowed
                    else "accepted"
                    if decision.allowed
                    else "rejected"
                ),
                reason=decision.reason,
                payload=audit_payload,
                latency_ms=latency_ms,
            )
            if not decision.allowed or self.settings.shadow_mode:
                continue

            embedding, embedding_model = self._embed(candidate.content)
            scoped_course_id = (
                course_id
                if candidate.memory_type in {"episode", "strategy_hint"}
                or candidate.profile_axis == "resource_preference"
                else None
            )
            source_digest = hashlib.sha256(
                f"{conversation_id}|{candidate.source_span}".encode("utf-8")
            ).hexdigest()[:16]
            memory = self.repository.upsert_memory(
                MemoryRecordDraft(
                    subject_user_id=subject_user_id,
                    owner_user_id=subject_user_id,
                    course_id=scoped_course_id,
                    conversation_id=conversation_id,
                    memory_type=candidate.memory_type,
                    fact_kind=(
                        "preference"
                        if candidate.memory_type in {"preference", "correction"}
                        else "summary"
                        if candidate.memory_type == "episode"
                        else "inference"
                        if candidate.memory_type == "strategy_hint"
                        else "fact"
                    ),
                    content=candidate.content,
                    structured_payload={
                        "reason": candidate.reason,
                        "raw_provider_payload": candidate.raw_provider_payload,
                    },
                    confidence=candidate.confidence,
                    source_type="conversation",
                    source_id=f"{conversation_id}:{source_digest}",
                    source_span=candidate.source_span,
                    profile_axis=candidate.profile_axis,
                    expires_at=candidate.expires_at,
                    supersedes_axis=candidate.supersedes_axis,
                    embedding=embedding,
                    embedding_model=embedding_model,
                    extractor=result.provider,
                    extractor_version=(
                        "langmem-0.0.30"
                        if result.provider == "langmem"
                        else self.rule_extractor.version
                    ),
                )
            )
            result.memory_ids.append(memory.memory_id)
            result.written_count += 1

        if result.written_count:
            accepted = [
                decision.candidate.content for decision in decisions if decision.allowed
            ]
            self.repository.add_episode(
                conversation_id=conversation_id,
                owner_user_id=subject_user_id,
                course_id=course_id,
                summary="；".join(accepted),
                salient_points=accepted,
                extractor=result.provider,
                extractor_version=(
                    "langmem-0.0.30"
                    if result.provider == "langmem"
                    else self.rule_extractor.version
                ),
                confidence=max(
                    decision.candidate.confidence
                    for decision in decisions
                    if decision.allowed
                ),
            )
        return result

    @staticmethod
    def _merge_candidates(
        primary: list[MemoryCandidate], fallback: list[MemoryCandidate]
    ) -> list[MemoryCandidate]:
        merged: list[MemoryCandidate] = []
        seen: set[tuple[str, str]] = set()
        for candidate in [*primary, *fallback]:
            key = (
                candidate.memory_type,
                candidate.profile_axis or candidate.content.strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(candidate)
        return merged

    def read_for_agent(
        self,
        *,
        actor,
        conversation_id: str,
        course_id: str | None,
        task_id: str | None,
        query: str,
        token_budget: int,
    ) -> AgentMemoryContext:
        subject_user_id = _actor_id(actor)
        if not self.settings.enabled or not subject_user_id:
            return AgentMemoryContext(retrieval_notes=["agent_memory_disabled"])
        query_embedding, _ = self._embed(query)
        profiles = self.repository.list_profile_facts(
            subject_user_id=subject_user_id, course_id=course_id
        )
        memories = self.repository.search(
            subject_user_id=subject_user_id,
            course_id=course_id,
            query=query,
            query_embedding=query_embedding,
            limit=self.settings.retrieval_limit,
        )
        profiles, memories, truncated = self._fit_token_budget(
            profiles, memories, token_budget=token_budget
        )
        return AgentMemoryContext(
            profile_facts=profiles,
            conversation_memories=memories,
            retrieval_notes=[
                f"profile_facts={len(profiles)}",
                f"conversation_memories={len(memories)}",
                f"token_budget_truncated={str(truncated).lower()}",
            ],
        )

    @staticmethod
    def _fit_token_budget(profiles, memories, *, token_budget: int):
        remaining = max(64, int(token_budget or 0) * 4)
        selected_profiles = []
        selected_memories = []
        truncated = False
        for fact in profiles:
            cost = len(fact.profile_axis) + len(fact.value) + 12
            if cost > remaining:
                truncated = True
                if not selected_profiles and remaining > 24:
                    selected_profiles.append(
                        fact.model_copy(update={"value": fact.value[: remaining - 20]})
                    )
                break
            selected_profiles.append(fact)
            remaining -= cost
        for memory in memories:
            cost = len(memory.content) + 8
            if cost > remaining:
                truncated = True
                break
            selected_memories.append(memory)
            remaining -= cost
        if len(selected_profiles) < len(profiles) or len(selected_memories) < len(
            memories
        ):
            truncated = True
        return selected_profiles, selected_memories, truncated

    def confirm_profile_fact(
        self,
        *,
        actor,
        profile_axis: str,
        value: str,
        course_id: str | None = None,
    ):
        subject_user_id = _actor_id(actor)
        normalized_axis = str(profile_axis or "").strip()
        normalized_value = str(value or "").strip()
        if not subject_user_id or not normalized_axis or not normalized_value:
            raise ValueError("actor, profile_axis and value are required")
        scoped_course_id = (
            course_id if normalized_axis == "resource_preference" else None
        )
        return self.repository.upsert_memory(
            MemoryRecordDraft(
                subject_user_id=subject_user_id,
                owner_user_id=subject_user_id,
                course_id=scoped_course_id,
                memory_type="profile_fact",
                fact_kind="fact",
                content=normalized_value,
                structured_payload={"confirmed_by_user": True},
                confidence=1.0,
                source_type="user_confirmation",
                source_id=f"profile-confirmation:{subject_user_id}:{normalized_axis}",
                source_span=normalized_value,
                profile_axis=normalized_axis,
                supersedes_axis=True,
                extractor="user_confirmation",
                extractor_version="1",
            )
        )

    def read(self, *, user_id: str, conversation_id: str | None):
        context = self.read_for_agent(
            actor={"user_id": user_id},
            conversation_id=conversation_id or "",
            course_id=None,
            task_id=None,
            query="",
            token_budget=self.settings.token_budget,
        )
        return {"summary": "", "context": context.model_dump(mode="json")}

    @staticmethod
    def build_prompt(context: AgentMemoryContext) -> str:
        lines: list[str] = []
        if context.profile_facts:
            lines.append("用户长期画像（仅用于调整表达方式，不作为成绩或掌握度事实）：")
            lines.extend(
                f"- [{fact.profile_axis}] {fact.value}"
                for fact in context.profile_facts
            )
        if context.conversation_memories:
            lines.append("与当前问题相关的历史对话记忆：")
            lines.extend(
                f"- {memory.content}" for memory in context.conversation_memories
            )
        return "\n".join(lines)
