from __future__ import annotations

import re

from app.chat.orchestrator.conversation_memory_compactor import ConversationMemoryCompactor


class ConversationMemoryExtractor:
    def __init__(self, *, compactor: ConversationMemoryCompactor | None = None):
        self.compactor = compactor or ConversationMemoryCompactor()

    _TOPIC_PREFIX_PATTERNS = [
        r"^(请你|请帮我|帮我|麻烦你|可以|能否|能不能|我想|想请你|继续|再)\s*",
        r"^(分析|解释|总结|概括|归纳|整理|生成|撰写|判断|比较|评价|说明|梳理|提炼|讨论|回答|告诉我)\s*",
    ]
    _ISSUE_KEYWORDS = [
        "问题",
        "不足",
        "困难",
        "分心",
        "参与度低",
        "参与度",
        "吸引力不足",
        "互动",
        "纪律",
        "薄弱",
        "不稳",
        "听不懂",
        "拖堂",
        "错误",
        "缺乏",
        "混乱",
        "偏少",
    ]
    _STOP_TOPICS = {
        "",
        "继续",
        "继续分析",
        "继续总结",
        "继续解释",
        "再展开",
        "再说说",
        "详细一点",
        "展开一点",
    }
    _SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "生物", "历史", "地理", "政治", "道法"]
    _STUDENT_SIGNAL_KEYWORDS = [
        "参与度",
        "分心",
        "走神",
        "注意力",
        "举手",
        "回应",
        "后排",
        "抬头",
        "专注",
        "纪律",
        "互动",
        "听讲",
        "讨论",
    ]
    _EVIDENCE_KEYWORDS = [
        "前",
        "后排",
        "举手",
        "响应",
        "走神",
        "观察",
        "多次",
        "明显",
        "较少",
        "偏短",
    ]

    _GENERIC_TOPIC_PHRASES = {
        "具体一点",
        "详细一点",
        "展开一点",
        "再具体一点",
        "介绍下整个过程",
        "介绍整个过程",
        "整个过程",
        "继续",
        "继续说",
        "继续分析",
        "继续生成",
    }
    _INTERROGATIVE_TOKENS = [
        "吗",
        "呢",
        "哪个",
        "哪些",
        "还是",
        "是否",
        "如何",
        "什么",
        "为什么",
        "怎么",
        "哪一个",
        "哪方面",
        "您想",
        "你想",
        "更关注",
    ]

    _USER_WORKFLOW_CONTROL_PATTERNS = [
        r"^请?基于(当前|以上).*(生成|整理).*(报告|教案|练习|测验|ppt|PPT)",
        r"^根据已确认的?大纲开始生成",
        r"^确认并继续$",
        r"^继续生成(报告|正文)?$",
        r"^开始生成(报告|正文)?$",
    ]
    _ASSISTANT_WORKFLOW_CONTROL_PATTERNS = [
        r"^我将基于.+(生成|整理).+",
        r"^已识别用户请求生成.+",
        r"^大纲已生成",
        r"^请确认或指出要修改的地方",
    ]
    _ASSISTANT_META_OPENERS = [
        "这是一个非常好的问题",
        "这是一个非常实际的问题",
        "这个问题很有意思",
        "这是个很好的问题",
    ]

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

    @staticmethod
    def _dedupe_dicts_keep_order(items: list[dict], *, limit: int, key: str = "content") -> list[dict]:
        seen: set[str] = set()
        result: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            content = str(item.get(key) or "").strip()
            if not content or content in seen:
                continue
            seen.add(content)
            result.append(item)
            if len(result) >= limit:
                break
        return result

    @staticmethod
    def _merge_source_message_ids(existing_ids: list[str], new_ids: list[str]) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []
        for value in list(existing_ids or []) + list(new_ids or []):
            normalized = str(value or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
        return merged

    @staticmethod
    def _confidence_for_source_count(count: int) -> str:
        if count >= 3:
            return "high"
        if count >= 2:
            return "medium"
        return "low"

    @staticmethod
    def _clean_clause(text: str) -> str:
        cleaned = re.sub(r"^[\-\*\d\.\)\s]+", "", str(text or "").strip())
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip("，。；：、")

    def _split_clauses(self, *texts: str) -> list[str]:
        clauses: list[str] = []
        for text in texts:
            for raw_clause in re.split(r"[，。！？；\n]", str(text or "")):
                clause = self._clean_clause(raw_clause)
                if clause:
                    clauses.append(clause)
        return clauses

    def _strip_topic_prefix(self, text: str) -> str:
        value = str(text or "").strip()
        for pattern in self._TOPIC_PREFIX_PATTERNS:
            value = re.sub(pattern, "", value)
        value = re.sub(r"^(关于|围绕|针对|对于|对)\s*", "", value)
        value = re.sub(
            r"(面向.+|给.+看|正式一点|口语一点|轻松一点|控制在.+字左右|控制在.+左右)$",
            "",
            value,
        )
        return self._clean_clause(value)

    def _extract_goal(self, question: str, *, action_name: str = "", workflow_type: str = "") -> str | None:
        text = str(question or "")
        if workflow_type == "report" or "报告" in text:
            return "生成报告"
        if workflow_type == "lesson_plan" or "教案" in text:
            return "整理教案"
        if workflow_type == "quiz" or "练习" in text or "题目" in text:
            return "生成练习"
        if "分析" in text:
            return "分析问题"
        if "解释" in text or "为什么" in text or "原因" in text:
            return "解释原因"
        if "总结" in text or "概括" in text or "归纳" in text:
            return "总结内容"
        if action_name == "chat.reply":
            return "继续对话"
        return None

    def _extract_explicit_user_goal(self, question: str) -> str | None:
        text = str(question or "")
        if not text:
            return None
        if "分析" in text:
            return "分析问题"
        if "解释" in text or "为什么" in text or "原因" in text:
            return "解释原因"
        if "总结" in text or "概括" in text or "归纳" in text:
            return "总结内容"
        return None

    def _merge_explicit_goals(self, goal: str | None, existing_goals: list[str]) -> list[str]:
        return self._dedupe_keep_order(([goal] if goal else []) + list(existing_goals or []), limit=5)

    @staticmethod
    def _layer_constraints(*, explicit_constraints: dict, derived_constraints: dict) -> dict:
        merged = {
            **dict(explicit_constraints or {}),
            **dict(derived_constraints or {}),
        }
        explicit_extra = list(explicit_constraints.get("extra_constraints") or []) if explicit_constraints else []
        derived_extra = list(derived_constraints.get("extra_constraints") or []) if derived_constraints else []
        if explicit_extra or derived_extra:
            merged["extra_constraints"] = ConversationMemoryExtractor._dedupe_keep_order(
                explicit_extra + derived_extra,
                limit=6,
            )
        return merged

    def _extract_topics(self, question: str, existing_topics: list[str]) -> list[str]:
        cleaned_question = self._strip_topic_prefix(question)
        clauses = [part for part in self._split_clauses(cleaned_question) if part.strip()]
        topic_candidates: list[str] = []
        for clause in clauses[:2]:
            if self._is_generic_topic_clause(clause):
                continue
            if len(clause) < 4:
                continue
            topic_candidates.append(clause)
        return self._dedupe_keep_order(topic_candidates + list(existing_topics or []), limit=5)

    def _is_generic_topic_clause(self, clause: str) -> bool:
        normalized = self._clean_clause(clause)
        if not normalized:
            return True
        if normalized in self._STOP_TOPICS or normalized in self._GENERIC_TOPIC_PHRASES:
            return True
        if normalized.startswith("比如"):
            return True
        if normalized.endswith("过程") and len(normalized) <= 8:
            return True
        if normalized.endswith("一点") and len(normalized) <= 8:
            return True
        return False

    @staticmethod
    def _matches_any_pattern(text: str, patterns: list[str]) -> bool:
        normalized = str(text or "").strip()
        if not normalized:
            return False
        return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    def _classify_user_text(self, text: str) -> str:
        normalized = self._clean_clause(text)
        if not normalized:
            return "empty"
        if self._matches_any_pattern(normalized, self._USER_WORKFLOW_CONTROL_PATTERNS):
            return "workflow_control"
        return "user_content"

    def _classify_assistant_text(self, text: str) -> str:
        normalized = self._clean_clause(text)
        if not normalized:
            return "empty"
        if self._matches_any_pattern(normalized, self._ASSISTANT_WORKFLOW_CONTROL_PATTERNS):
            return "workflow_control"
        if any(normalized.startswith(prefix) for prefix in self._ASSISTANT_META_OPENERS):
            return "assistant_meta"
        return "assistant_content"

    def _strip_assistant_meta_openers(self, text: str) -> str:
        normalized = str(text or "").strip()
        for prefix in self._ASSISTANT_META_OPENERS:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].lstrip("，。:：!！?？ ")
                break
        return normalized

    def _semantic_user_text(self, text: str) -> str:
        return str(text or "").strip() if self._classify_user_text(text) == "user_content" else ""

    def _semantic_assistant_text(self, text: str) -> str:
        classification = self._classify_assistant_text(text)
        if classification in {"assistant_content", "assistant_meta"}:
            return self._strip_assistant_meta_openers(text)
        return ""

    def classify_message_kind(
        self,
        *,
        role: str,
        text: str,
        workflow_type: str = "",
        action_name: str = "",
        artifacts: list[dict] | None = None,
    ) -> str:
        normalized_role = str(role or "").strip()
        if normalized_role == "user":
            classification = self._classify_user_text(text)
            return "workflow_control" if classification == "workflow_control" else "user_content"

        if normalized_role == "assistant":
            classification = self._classify_assistant_text(text)
            if classification == "workflow_control":
                return "workflow_control"
            if classification == "assistant_meta":
                return "assistant_meta"
            if workflow_type or str(action_name or "").startswith("generate.") or list(artifacts or []):
                return "workflow_result"
            return "assistant_content"

        return "unknown"

    def _extract_extra_constraints(self, question: str, existing_extra: list[str]) -> list[str]:
        extras = list(existing_extra or [])
        text = str(question or "")
        patterns = [
            r"(按[^，。；]+输出)",
            r"(加入[^，。；]+)",
            r"(突出[^，。；]+)",
            r"(保留[^，。；]+)",
        ]
        matches: list[str] = []
        for pattern in patterns:
            matches.extend(re.findall(pattern, text))

        normalized: list[str] = []
        for item in matches:
            value = self._clean_clause(item)
            value = re.sub(r"^按", "", value)
            normalized.append(value)
        return self._dedupe_keep_order(extras + normalized, limit=6)

    def _extract_constraints(self, question: str, existing_constraints: dict, request) -> dict:
        text = str(question or "")
        constraints = dict(existing_constraints or {})

        audience_match = re.search(r"面向([^，。；\s]+)", text)
        if audience_match:
            constraints["audience"] = audience_match.group(1)

        if "正式" in text:
            constraints["tone"] = "正式"
        elif "口语" in text or "轻松" in text:
            constraints["tone"] = "轻松"

        length_match = re.search(r"(\d+\s*字)", text)
        if length_match:
            constraints["length"] = length_match.group(1).replace(" ", "")

        grade_match = re.search(r"(高一|高二|高三|初一|初二|初三|一年级|二年级|三年级|四年级|五年级|六年级)", text)
        if grade_match:
            constraints["grade_level"] = grade_match.group(1)

        for subject in self._SUBJECTS:
            if subject in text:
                constraints["subject"] = subject
                break

        course_id = getattr(request, "course_id", None)
        if course_id and not constraints.get("course_id"):
            constraints["course_id"] = course_id

        constraints["extra_constraints"] = self._extract_extra_constraints(
            text,
            list(existing_constraints.get("extra_constraints", [])) if existing_constraints else [],
        )
        return constraints

    def _extract_explicit_constraints(self, question: str, existing_constraints: dict) -> dict:
        explicit_constraints = self._extract_constraints(question, existing_constraints, request=None)
        explicit_constraints.pop("course_id", None)
        return explicit_constraints

    def _extract_derived_workflow_constraints(self, request, existing_constraints: dict) -> dict:
        derived = dict(existing_constraints or {})
        course_id = getattr(request, "course_id", None)
        if course_id:
            derived["course_id"] = course_id
        return derived

    def _extract_issues(self, *texts: str, existing_issues: list[str]) -> list[str]:
        issues: list[str] = []
        for clause in self._split_clauses(*texts):
            if any(keyword in clause for keyword in self._ISSUE_KEYWORDS):
                issues.append(clause[:40])
        return self._dedupe_keep_order(issues + list(existing_issues or []), limit=5)

    def _extract_student_signals(self, *texts: str, existing_signals: list[str]) -> list[str]:
        signals: list[str] = []
        for clause in self._split_clauses(*texts):
            if any(keyword in clause for keyword in self._STUDENT_SIGNAL_KEYWORDS):
                signals.append(clause[:40])
        return self._dedupe_keep_order(signals + list(existing_signals or []), limit=5)

    @staticmethod
    def _find_latest_message_id(recent_messages: list[dict], role: str) -> str | None:
        for message in reversed(list(recent_messages or [])):
            if str(message.get("role") or "").strip() == role:
                message_id = str(message.get("message_id") or "").strip()
                if message_id:
                    return message_id
        return None

    def _extract_evidence_points(self, *texts: str, existing_points: list[dict], recent_messages: list[dict]) -> list[dict]:
        evidence_points: list[dict] = []
        assistant_message_id = self._find_latest_message_id(recent_messages, "assistant")
        for clause in self._split_clauses(*texts):
            if len(clause) < 8:
                continue
            if any(keyword in clause for keyword in self._EVIDENCE_KEYWORDS):
                source_ids = [assistant_message_id] if assistant_message_id else []
                evidence_points.append(
                    {
                        "type": "observation",
                        "content": clause[:60],
                        "source_type": "assistant_message",
                        "source_message_ids": source_ids,
                        "confidence": self._confidence_for_source_count(len(source_ids)),
                    }
                )
        return self._merge_evidence_points(
            existing_points=list(existing_points or []),
            new_points=evidence_points,
            limit=5,
        )

    def _merge_evidence_points(self, *, existing_points: list[dict], new_points: list[dict], limit: int) -> list[dict]:
        merged_by_content: dict[str, dict] = {}
        order: list[str] = []

        for item in list(existing_points or []) + list(new_points or []):
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            if content not in merged_by_content:
                merged_by_content[content] = {
                    "type": str(item.get("type") or "observation"),
                    "content": content,
                    "source_type": str(item.get("source_type") or "assistant_message"),
                    "source_message_ids": list(item.get("source_message_ids") or []),
                    "confidence": str(item.get("confidence") or "low"),
                }
                order.append(content)
                continue

            current = merged_by_content[content]
            current_ids = self._merge_source_message_ids(
                list(current.get("source_message_ids") or []),
                list(item.get("source_message_ids") or []),
            )
            current["source_message_ids"] = current_ids
            current["confidence"] = self._confidence_for_source_count(len(current_ids))

        merged_list = [merged_by_content[content] for content in order]
        return merged_list[:limit]

    def _extract_user_stated_facts(self, question: str, existing_facts: list[str]) -> list[str]:
        facts: list[str] = []
        for clause in self._split_clauses(question):
            if len(clause) < 6:
                continue
            if any(token in clause for token in self._INTERROGATIVE_TOKENS):
                continue
            if any(token in clause for token in ["请", "帮我", "生成", "分析", "总结", "解释", "介绍"]):
                continue
            facts.append(clause[:48])
        return self._dedupe_keep_order(facts + list(existing_facts or []), limit=5)

    def _extract_assistant_fact_candidates(self, answer: str, existing_facts: list[str]) -> list[str]:
        facts: list[str] = []
        for clause in self._split_clauses(answer):
            if len(clause) < 8:
                continue
            if any(token in clause for token in ["建议", "可以", "如果", "请你", "是否"]):
                continue
            if any(token in clause for token in self._INTERROGATIVE_TOKENS):
                continue
            if clause.startswith("比如"):
                continue
            facts.append(clause[:48])
        return self._dedupe_keep_order(facts + list(existing_facts or []), limit=5)

    @staticmethod
    def _project_confirmed_facts(*, user_stated_facts: list[str], existing_memory: dict) -> list[str]:
        if user_stated_facts:
            return list(user_stated_facts)
        return list((existing_memory or {}).get("confirmed_facts") or [])

    @staticmethod
    def _build_summary(*, topics: list[str], goal: str | None, issues: list[str], answer: str, existing_summary: str) -> str:
        if topics and goal:
            goal_phrase = {
                "分析问题": "进行分析",
                "解释原因": "进行解释",
                "总结内容": "进行总结",
                "继续对话": "继续对话",
            }.get(goal, goal)
            summary = f"当前围绕{'、'.join(topics[:2])}{goal_phrase}"
            if issues:
                summary += f"，已识别重点问题：{issues[0]}"
            return summary
        if topics:
            return f"当前围绕{'、'.join(topics[:2])}继续讨论"
        if answer:
            shortened = answer.strip().replace("\n", " ")
            return shortened[:60]
        return str(existing_summary or "")

    def _merge_goals(self, goal: str | None, existing_goals: list[str]) -> list[str]:
        return self._dedupe_keep_order(([goal] if goal else []) + list(existing_goals or []), limit=5)

    def build_state_patch(self, *, request, result: dict, existing_state: dict, recent_messages: list[dict]) -> dict:
        _ = recent_messages
        question = str(getattr(request, "question", "") or "").strip()
        answer = str(((result.get("message") or {}).get("content")) or "").strip()
        semantic_question = self._semantic_user_text(question)
        semantic_answer = self._semantic_assistant_text(answer)
        workflow = result.get("workflow") or {}
        action_name = str(((result.get("action") or {}).get("name")) or "").strip()

        existing_summary = str(((existing_state.get("conversation_summary") or {}).get("summary_text")) or "")
        existing_memory = dict(existing_state.get("conversation_memory") or {})
        existing_memory_meta = dict(existing_state.get("conversation_memory_meta") or {})

        explicit_goal = self._extract_explicit_user_goal(semantic_question)
        derived_goal = self._extract_goal(
            question,
            action_name=action_name,
            workflow_type=str(workflow.get("type") or ""),
        )
        explicit_goals = self._merge_explicit_goals(
            explicit_goal,
            list(existing_memory.get("explicit_user_goals") or []),
        )
        topics = self._extract_topics(semantic_question, list(existing_memory.get("current_topics") or []))
        explicit_constraints = self._extract_explicit_constraints(
            semantic_question,
            dict(
                existing_memory.get("explicit_user_constraints")
                or existing_memory.get("constraints")
                or {}
            ),
        )
        derived_constraints = self._extract_derived_workflow_constraints(
            request,
            dict(existing_memory.get("derived_workflow_constraints") or {}),
        )
        constraints = self._layer_constraints(
            explicit_constraints=explicit_constraints,
            derived_constraints=derived_constraints,
        )
        issues = self._extract_issues(
            semantic_question,
            semantic_answer,
            existing_issues=list(existing_memory.get("teaching_issues") or []),
        )
        student_signals = self._extract_student_signals(
            semantic_question,
            semantic_answer,
            existing_signals=list(existing_memory.get("student_signals") or []),
        )
        evidence_points = self._extract_evidence_points(
            semantic_answer,
            existing_points=list(existing_memory.get("evidence_points") or []),
            recent_messages=recent_messages,
        )
        user_stated_facts = self._extract_user_stated_facts(
            semantic_question,
            list(existing_memory.get("user_stated_facts") or []),
        )
        assistant_fact_candidates = self._extract_assistant_fact_candidates(
            semantic_answer,
            list(existing_memory.get("assistant_fact_candidates") or []),
        )
        confirmed_facts = self._project_confirmed_facts(
            user_stated_facts=user_stated_facts,
            existing_memory=existing_memory,
        )
        goals = self._dedupe_keep_order(
            ([derived_goal] if derived_goal else [])
            + list(explicit_goals or [])
            + list(existing_memory.get("user_goals") or []),
            limit=5,
        )
        if not semantic_question and not semantic_answer and existing_summary:
            summary = existing_summary
        else:
            summary = self._build_summary(
                topics=topics,
                goal=explicit_goal if semantic_question else None,
                issues=issues,
                answer=semantic_answer,
                existing_summary=existing_summary,
            )

        merged_memory = {
            **existing_memory,
            "current_topics": topics,
            "explicit_user_goals": explicit_goals,
            "derived_workflow_goal": derived_goal,
            "user_goals": goals,
            "user_stated_facts": user_stated_facts,
            "assistant_fact_candidates": assistant_fact_candidates,
            "confirmed_facts": confirmed_facts,
            "teaching_issues": issues,
            "student_signals": student_signals,
            "evidence_points": evidence_points,
            "explicit_user_constraints": explicit_constraints,
            "derived_workflow_constraints": derived_constraints,
            "constraints": constraints,
        }
        if existing_memory.get("referenced_artifact_ids"):
            merged_memory["referenced_artifact_ids"] = list(existing_memory.get("referenced_artifact_ids") or [])

        compacted_memory, memory_meta = self.compactor.compact(
            memory=merged_memory,
            existing_meta=existing_memory_meta,
            action_name=action_name,
            workflow_type=str(workflow.get("type") or ""),
        )

        return {
            "conversation_summary": {
                "summary_text": summary,
            },
            "conversation_memory": compacted_memory,
            "conversation_memory_meta": memory_meta,
        }
