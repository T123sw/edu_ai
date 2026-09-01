from __future__ import annotations

import re


class ConversationMemoryCompactor:
    _WORKFLOW_CONTROL_PATTERNS = [
        r"^请?基于(当前|以上).*(生成|整理).*(报告|教案|练习|测验)",
        r"^根据已确认的?大纲开始生成",
        r"^确认并继续$",
        r"^继续生成(报告|正文)?$",
        r"^开始生成(报告|正文)?$",
    ]
    _GENERATION_GOALS = {"生成报告", "整理教案", "生成练习"}
    _DROPPABLE_GOALS_ON_GENERATION = {"继续对话"}

    @classmethod
    def _matches_any_pattern(cls, text: str, patterns: list[str]) -> bool:
        normalized = str(text or "").strip()
        if not normalized:
            return False
        return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    @classmethod
    def _is_residue_topic(cls, topic: str) -> bool:
        normalized = str(topic or "").strip()
        if not normalized:
            return True
        if cls._matches_any_pattern(normalized, cls._WORKFLOW_CONTROL_PATTERNS):
            return True
        return normalized in {"确认并继续", "继续生成", "开始生成"}

    @staticmethod
    def _dedupe_keep_order(values: list[str], *, limit: int) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = str(value or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
            if len(result) >= limit:
                break
        return result

    @classmethod
    def _clean_topics(cls, topics: list[str]) -> list[str]:
        cleaned = [topic for topic in list(topics or []) if not cls._is_residue_topic(topic)]
        return cls._dedupe_keep_order(cleaned, limit=5)

    @classmethod
    def _clean_goals(cls, goals: list[str], *, derived_goal: str) -> list[str]:
        cleaned = list(goals or [])
        if derived_goal in cls._GENERATION_GOALS:
            cleaned = [goal for goal in cleaned if goal not in cls._DROPPABLE_GOALS_ON_GENERATION]
        return cls._dedupe_keep_order(cleaned, limit=5)

    @classmethod
    def _should_compact(
        cls,
        *,
        turn_count: int,
        last_compacted_turn: int,
        action_name: str,
        workflow_type: str,
        derived_goal: str,
    ) -> tuple[bool, str]:
        if workflow_type or str(action_name or "").startswith("generate.") or derived_goal in cls._GENERATION_GOALS:
            return True, "workflow_turn"
        if turn_count - int(last_compacted_turn or 0) >= 4:
            return True, "periodic_turn_window"
        return False, ""

    def compact(
        self,
        *,
        memory: dict,
        existing_meta: dict,
        action_name: str = "",
        workflow_type: str = "",
    ) -> tuple[dict, dict]:
        current_meta = dict(existing_meta or {})
        turn_count = int(current_meta.get("turn_count") or 0) + 1
        last_compacted_turn = int(current_meta.get("last_compacted_turn") or 0)
        compaction_count = int(current_meta.get("compaction_count") or 0)
        derived_goal = str((memory or {}).get("derived_workflow_goal") or "").strip()

        should_compact, reason = self._should_compact(
            turn_count=turn_count,
            last_compacted_turn=last_compacted_turn,
            action_name=action_name,
            workflow_type=workflow_type,
            derived_goal=derived_goal,
        )

        compacted_memory = dict(memory or {})
        if should_compact:
            compacted_memory["current_topics"] = self._clean_topics(list(compacted_memory.get("current_topics") or []))
            compacted_memory["user_goals"] = self._clean_goals(
                list(compacted_memory.get("user_goals") or []),
                derived_goal=derived_goal,
            )
            compaction_count += 1
            last_compacted_turn = turn_count

        meta = {
            "turn_count": turn_count,
            "last_compacted_turn": last_compacted_turn,
            "compaction_count": compaction_count,
        }
        if should_compact:
            meta["last_compaction_reason"] = reason
        elif current_meta.get("last_compaction_reason"):
            meta["last_compaction_reason"] = current_meta.get("last_compaction_reason")

        return compacted_memory, meta
