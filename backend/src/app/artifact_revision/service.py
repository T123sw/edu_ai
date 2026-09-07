from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

from app.chat.skill_manager import SkillManager

from app.chat.domain.artifact_reference import ArtifactReferencePayload
from .adapters import TYPES, read_content, validate, apply_edits, content_updates, editable_paths
from .storage import RevisionStorage, RevisionConflict

_LABELS = {"report": "报告", "report_outline": "大纲", "lesson_plan": "教案", "blog": "博客", "quiz": "习题", "flashcard": "闪卡", "graph": "思维导图", "game": "游戏", "classroom": "课堂"}


def reference(material, kind=None):
    return {"artifact_id": material["material_id"], "artifact_type": kind or material["material_type"], "version_id": f'v{material["version"]}', "title": material.get("title") or material.get("topic") or material["material_id"], "source_course_id": material["course_id"]}


class ArtifactRevisionService:
    def __init__(self, manager, llm=None, *, skill_manager=None, submitter=None, is_cancel_requested=None, before_save=None):
        self.manager = manager
        self.llm = llm
        self.submitter = submitter
        self.before_save = before_save or (lambda: None)
        self.is_cancel_requested = is_cancel_requested or (lambda: False)
        self.storage = RevisionStorage(manager)
        self.skills = skill_manager if skill_manager is not None else SkillManager(
            skills_dir=Path(__file__).resolve().parents[3] / "skills"
        )

    def _clarify(self, message, state, candidates=()):
        return {"status": "needs_clarification", "message": message, "pending": state, "candidates": list(candidates)}

    def run(self, *, owner_user_id: str, conversation_id: str, course_id: str | None,
            question: str, operation_id: str, artifact_reference=None, pending=None,
            scope_id: str | None = None, session_artifacts=None, frozen_target=False, current_question=None, actor_role="teacher") -> dict:
        if not artifact_reference and not pending and not re.search(r"修改|改写|重写|调整|简化|改一下|删掉", question):
            return {"status": "not_applicable", "message": ""}
        try:
            if not owner_user_id or not conversation_id or not operation_id:
                raise ValueError("修改需要认证主体、会话和操作编号")
            ref = ArtifactReferencePayload.model_validate(artifact_reference).model_dump(exclude_none=True) if artifact_reference else None
            state = {"actor_role": actor_role, "owner_user_id": owner_user_id, "conversation_id": conversation_id, "operation_id": operation_id, "question": question, "reference": ref, "course_id": course_id, "scope_id": scope_id}
            if pending:
                if pending.get("owner_user_id") != owner_user_id or pending.get("conversation_id") != conversation_id:
                    raise ValueError("待处理修改不属于当前会话")
                state = deepcopy(pending)
                state["question"] += "\n用户补充：" + question
                ref = state.get("reference")
                course_id, scope_id = state.get("course_id"), state.get("scope_id")
                operation_id = state["operation_id"]
            # An explicitly named competing title supersedes a selected reference only
            # when unique among authorized candidates; otherwise ask, never guess.
            candidates = self.manager.list_generated_materials(course_id, owner_user_id=owner_user_id, space="mine", sort="updated_desc") if course_id and (not ref or re.search(r'[《“"]', question)) else []
            candidates = [m for m in candidates if m.get("owner_user_id") == owner_user_id and m.get("visibility") == "private" and m.get("material_type") in TYPES]
            # Quoted replacement text is an edit instruction, not a competing
            # artifact title. Book-title brackets or an explicit edit verb
            # immediately before a quoted title identify a target.
            explicit_title = re.search(r"《([^》]+)》|(?:修改|编辑|重写|改写)\s*[“\"]([^”\"]+)[”\"]", question)
            if explicit_title and not frozen_target:
                named_title = explicit_title[1] or explicit_title[2]
                matches = [m for m in candidates if named_title in str(m.get("title") or m.get("topic") or "")]
                if len(matches) == 1:
                    ref = reference(matches[0])
                elif not ref or named_title not in str(ref.get("title") or ""):
                    state["reference"] = None
                    state["candidate_references"] = [reference(m) for m in matches]
                    return self._clarify("请明确要修改哪份资料。", state, state["candidate_references"])
            if not ref:
                if scope_id:
                    candidates = [m for m in candidates if m.get("scope_id") == scope_id]
                mentioned = [k for k, label in _LABELS.items() if label in state["question"]]
                if mentioned:
                    candidates = [m for m in candidates if m["material_type"] in mentioned]
                    label_pattern = "|".join(re.escape(_LABELS[k]) for k in mentioned)
                    topic_match = re.search(r"(?:生成的|的)([^，。！？\s]{1,30}?)(?:" + label_pattern + r")", state["question"])
                    if topic_match:
                        topic = topic_match[1]
                        candidates = [m for m in candidates if topic in str(m.get("title") or "") or topic in str(m.get("topic") or "")]
                # Use known title words rather than a fuzzy top score.
                matched = [m for m in candidates if str(m.get("title") or "").strip() and str(m["title"]).removesuffix(".md") in question]
                if matched:
                    candidates = matched
                if re.search(r"上次|刚才|刚生成|上一份", state["question"]):
                    session_ids = {a.get("artifact_id") or a.get("material_id") for a in (session_artifacts or [])}
                    in_session = [m for m in candidates if m["material_id"] in session_ids]
                    if in_session:
                        candidates = in_session
                    # Creation time only, never updated_at. Ties remain ambiguous.
                    def generated_time(material):
                        try:
                            date = datetime.fromisoformat(str(material.get("created_at") or "").replace("Z", "+00:00"))
                            return date.replace(tzinfo=timezone.utc).timestamp() if date.tzinfo is None else date.timestamp()
                        except ValueError:
                            return None
                    dates = [generated_time(m) for m in candidates]
                    if dates and all(date is not None for date in dates):
                        newest = max(dates)
                        candidates = [m for m in candidates if generated_time(m) == newest]
                choice = re.fullmatch(r"(?:第)?([1-9]\d*)(?:份|个)?", question.strip())
                if pending and choice:
                    choices = pending.get("candidate_references", [])
                    index = int(choice[1]) - 1
                    if 0 <= index < len(choices):
                        ref = choices[index]
                if not ref and len(candidates) == 1:
                    ref = reference(candidates[0])
                if not ref:
                    refs = [dict(reference(m), created_at=m.get("created_at"), scope_id=m.get("scope_id")) for m in candidates[:20]]
                    state["candidate_references"] = refs
                    return self._clarify("请指定要修改的资料（可回复候选序号或完整标题）。", state, refs)
            state["reference"] = ref
            kind = ref["artifact_type"]
            stored_kind = "report" if kind == "report_outline" else kind
            target_course = ref.get("source_course_id") or course_id
            if not target_course:
                return self._clarify("请提供资料所属课程或从资料预览选择“让 AI 修改”。", state)
            material = self.storage.get(target_course, stored_kind, ref["artifact_id"], owner_user_id)
            base = int(str(ref.get("version_id") or f'v{material["version"]}').removeprefix("v"))
            state["reference"] = reference(material, kind) | {"version_id": f"v{base}"}
            full_question = state["question"]
            fingerprint = hashlib.sha256(json.dumps([owner_user_id, conversation_id, target_course, kind, ref["artifact_id"], base, full_question], ensure_ascii=False).encode()).hexdigest()
            receipt = self.storage.retry(material, operation_id, fingerprint)
            if receipt:
                return self._completed(self.storage.version(target_course, stored_kind, ref["artifact_id"], owner_user_id, receipt["version"]), kind)
            if material["version"] != base:
                raise RevisionConflict("资料已有新版本，请查看变化后使用最新版重试")
            source = self.storage.version(target_course, stored_kind, ref["artifact_id"], owner_user_id, base)
            content = self._content(source, kind)
            if self.submitter is not None:
                return self.submitter(state=state, source=source, current_question=question, prior_pending=pending)
            if self.llm is None:
                raise ValueError("修改模型暂不可用，原资料未改变")
            system_prompt = self.skills.extract_section("edu-artifact-revision", "SYSTEM_PROMPT")
            if not system_prompt:
                raise ValueError("资料修改技能未加载，原资料未改变")
            prompt = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps({"instruction": full_question, "current_question": current_question if current_question is not None else question, "artifact_type": kind, "reference": state["reference"], "source": content, "editable_paths": editable_paths(content)}, ensure_ascii=False)},
            ]
            for attempt in range(2):
                response = self.llm.invoke(prompt)
                raw = getattr(response, "content", response)
                if not isinstance(raw, str):
                    raise ValueError("模型响应不是有效文本")
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
                try:
                    output = json.loads(raw)
                    if not isinstance(output, dict):
                        raise ValueError("模型必须返回 JSON 对象")
                    actions = [key for key in ("answer", "question", "edits") if key in output]
                    if len(actions) != 1:
                        raise ValueError("每次只能返回 answer、question、edits 中一种动作")
                    if actions[0] in {"answer", "question"}:
                        text = output[actions[0]]
                        if not isinstance(text, str) or not text.strip():
                            raise ValueError("回答或追问必须是具体的非空文本")
                        if text.strip() == "具体追问":
                            raise ValueError("不能返回占位文案，请依据原文回答或提出具体问题")
                        if actions[0] == "answer":
                            result = {"status": "answered", "message": text.strip(), "artifact_reference": state["reference"]}
                            if pending:
                                result["pending"] = deepcopy(pending)
                                result["awaiting_clarification"] = True
                            return result
                        return self._clarify(text.strip(), state)
                    edits = output.get("edits")
                    updated = apply_edits(content, edits)
                    validate(kind, updated)
                    break
                except (ValueError, KeyError, TypeError) as error:
                    if attempt:
                        raise ValueError("修改未通过原文匹配或结构校验，原资料未改变") from error
                    prompt.extend([
                        {"role": "assistant", "content": raw},
                        {"role": "user", "content": "修改尚未保存。请修正输出：" + str(error) + "。path 从 source 本身开始，不要包含 source/content 包装层，严格使用 editable_paths 中的数字下标。"},
                    ])
            if kind == "classroom" and updated["stage"]["id"] != content["stage"]["id"]:
                raise ValueError("修改不能更换课堂 ID")
            summary = f"已修改 {len(edits)} 处内容"
            changes = [{"path": e.get("path", []), "before": e["before"] if isinstance(e["before"], str) else json.dumps(e["before"], ensure_ascii=False), "after": e["after"] if isinstance(e["after"], str) else json.dumps(e["after"], ensure_ascii=False)} for e in edits]
            updates = content_updates(source, kind, updated)
            if updates.get("revision_audio_invalidated"):
                summary += "；已清除改动讲解的旧配音，播放时需重新配音"
            if kind == "game":
                updates = self._render_game(source, updated, operation_id)
            self.before_save()
            if self.is_cancel_requested():
                raise ValueError("任务已取消，原资料未改变")
            saved = self.storage.save(source, updates, owner=owner_user_id, operation_id=operation_id, fingerprint=fingerprint, summary=summary, changes=changes)
            return self._completed(saved, kind)
        except RevisionConflict as exc:
            return {"status": "conflict", "message": str(exc), "pending": locals().get("state")}
        except Exception as exc:
            # Never echo storage paths, SQL, model output or another owner's data.
            message = str(exc) if type(exc) is ValueError else "修改失败，原资料未改变，请重试"
            return {"status": "failed", "message": message, "pending": locals().get("state")}

    def _content(self, material, kind):
        # Legacy text exports can have a server file pointer instead of inline text.
        if kind in {"report", "blog", "lesson_plan"} and not any(material.get(k) for k in ("content", "report", "final_markdown", "markdown", "report_content", "text", "plan")):
            relative = material.get("file_path")
            if not isinstance(relative, str) or not relative:
                raise ValueError("资料原文不存在，无法修改")
            root = self.manager.get_course_dir(material["course_id"]).resolve()
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or path.suffix.lower() not in {".md", ".txt", ".markdown"} or not path.is_file() or path.stat().st_size > 2_000_000:
                raise ValueError("资料原文无法安全完整读取")
            material = {**material, "content": path.read_text(encoding="utf-8")}
        return read_content(material, kind)

    def _render_game(self, source, content, operation_id):
        from app.chat.application.game_template_registry import get_game_template_spec
        from app.chat.application.knowledge_base_direct_game_service_v2 import KnowledgeBaseDirectGameServiceV2
        template = get_game_template_spec(content["game_type"])
        renderer = KnowledgeBaseDirectGameServiceV2(course_storage_manager=self.manager)
        # New immutable path; old HTML remains usable by old versions.
        suffix = hashlib.sha256(operation_id.encode()).hexdigest()[:16]
        from app.chat.application.knowledge_base_direct_game_service_v2 import _safe_segment
        from urllib.parse import quote
        target = renderer.storage_root / _safe_segment(source["owner_user_id"], "owner") / _safe_segment(source["course_id"], "course") / _safe_segment(f'{source["material_id"]}-revision-{suffix}', "artifact") / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        game_json = json.dumps(content["game_data"], ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        target.write_text(template.html_template_path.read_text(encoding="utf-8").replace("__GAME_DATA_JSON__", game_json), encoding="utf-8")
        relative = target.relative_to(renderer.storage_root).as_posix()
        url = "/api/chat/v2/games/html?path=" + quote(relative, safe="")
        return {"content": {**content, "html_path": relative, "html_url": url}}

    @staticmethod
    def _completed(material, kind):
        metadata = material["revision"]
        artifact = {k: v for k, v in material.items() if k not in {"revision_history", "revision_operations"}}
        artifact.update(artifact_id=material["material_id"], artifact_type=kind, material_version=material["version"], version={"version_id": f'v{material["version"]}', "version_number": material["version"], "root_artifact_id": material["material_id"], "parent_artifact_id": material["material_id"]})
        if kind == "report_outline":
            artifact["content"] = material["outline"]
        return {"status": "completed", "message": "已保存新版本", "artifact_reference": reference(material, kind), "artifact": artifact, "summary": metadata["summary"], "changes": metadata["changes"], "base_version_id": f'v{metadata["base_version"]}'}

    def read_version(self, *, owner_user_id, course_id, artifact_type, artifact_id, version):
        return self.storage.version(course_id, "report" if artifact_type == "report_outline" else artifact_type, artifact_id, owner_user_id, version)

    def restore(self, *, owner_user_id, course_id, artifact_type, artifact_id, version, base_version, operation_id):
        try:
            kind = "report" if artifact_type == "report_outline" else artifact_type
            source = self.storage.get(course_id, kind, artifact_id, owner_user_id)
            fingerprint = hashlib.sha256(json.dumps(["restore", owner_user_id, course_id, kind, artifact_id, version, base_version]).encode()).hexdigest()
            receipt = self.storage.retry(source, operation_id, fingerprint)
            if receipt:
                return self._completed(self.storage.version(course_id, kind, artifact_id, owner_user_id, receipt["version"]), artifact_type)
            if source["version"] != base_version:
                raise RevisionConflict("资料已有新版本")
            old = self.read_version(owner_user_id=owner_user_id, course_id=course_id, artifact_type=artifact_type, artifact_id=artifact_id, version=version)
            content = self._content(old, artifact_type)
            updates = content_updates(source, artifact_type, content)
            if artifact_type == "game":
                updates = self._render_game(source, content, operation_id)
            self.before_save()
            if self.is_cancel_requested():
                raise ValueError("任务已取消，原资料未改变")
            saved = self.storage.save(source, updates, owner=owner_user_id, operation_id=operation_id, fingerprint=fingerprint, summary=f"恢复第 {version} 版内容", changes=[])
            return self._completed(saved, artifact_type)
        except RevisionConflict as exc:
            return {"status": "conflict", "message": str(exc)}
        except Exception:
            return {"status": "failed", "message": "恢复失败，原资料未改变"}
