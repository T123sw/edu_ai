"""Read canonical content and apply exact, validated edits without dropping unseen data."""
from __future__ import annotations

from copy import deepcopy
import json
import re

TYPES = {"report", "report_outline", "lesson_plan", "blog", "quiz", "flashcard", "graph", "game", "classroom"}
TEXT_KEYS = ("content", "final_markdown", "markdown", "report", "report_content", "text")


def read_content(material: dict, artifact_type: str):
    if artifact_type == "report_outline":
        value = material.get("outline")
    elif artifact_type in {"report", "lesson_plan", "blog"}:
        value = next((material[k] for k in TEXT_KEYS if isinstance(material.get(k), str) and material[k].strip()), None)
        if value is None and artifact_type == "lesson_plan":
            value = material.get("plan") or (material.get("content") if isinstance(material.get("content"), dict) else None)
    elif artifact_type == "classroom":
        value = {"stage": material.get("stage"), "scenes": material.get("scenes")}
    else:
        value = material.get("content")
        if value is None and artifact_type == "quiz":
            value = {"questions": material.get("questions")}
        if value is None and artifact_type == "flashcard":
            value = {"cards": material.get("flashcards")}
        if artifact_type == "game" and isinstance(value, dict):
            value = {k: deepcopy(value[k]) for k in ("game_type", "template_id", "game_data") if k in value}
    if value is None or value == "":
        raise ValueError("资料原文不存在，无法修改")
    validate(artifact_type, value)
    return deepcopy(value)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _items(value, key):
    items = value.get(key)
    if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
        raise ValueError(f"{key} 必须包含有效条目")
    return items


def validate(kind: str, content):
    if len(json.dumps(content, ensure_ascii=False)) > 2_000_000:
        raise ValueError("内容过大，不能完整校验")
    if kind in {"report", "blog", "lesson_plan"} and isinstance(content, str):
        if not content.strip():
            raise ValueError("正文不能为空")
        return
    if kind == "report_outline":
        if not isinstance(content, list) or not content or not all(isinstance(c, dict) and _text(c.get("chapter_title") or c.get("title")) for c in content):
            raise ValueError("报告大纲章节无效")
        return
    if not isinstance(content, dict):
        raise ValueError("结构化资料必须是对象")
    if kind == "lesson_plan":
        if not _text(content.get("title")) or not isinstance(content.get("objectives"), list):
            raise ValueError("教案必须保留标题和教学目标")
        _items(content, "process")
    elif kind == "quiz":
        ids = set()
        for q in _items(content, "questions"):
            if not all(_text(q.get(k)) for k in ("stem", "answer", "explanation")):
                raise ValueError("习题必须有题干、答案和解析")
            if q.get("id"):
                if q["id"] in ids:
                    raise ValueError("题目 ID 重复")
                ids.add(q["id"])
            options = q.get("options")
            if options is not None:
                if not isinstance(options, list) or len(options) < 2 or not all(_text(o) for o in options):
                    raise ValueError("习题选项无效")
                answer = q["answer"].strip()
                letters = re.sub(r"[\s,，、;；]+", "", answer).upper()
                if answer not in options and (not re.fullmatch("[A-Z]+", letters) or any(ord(c) - 65 >= len(options) for c in letters)):
                    raise ValueError("答案与选项不匹配")
    elif kind == "flashcard":
        for card in _items(content, "cards"):
            if not _text(card.get("front")) or not _text(card.get("back")):
                raise ValueError("闪卡必须保留正反面配对")
    elif kind == "graph":
        seen = set()
        def visit(node):
            if not isinstance(node, dict) or not _text(node.get("id")) or not _text(node.get("title")):
                raise ValueError("导图节点缺少 ID 或标题")
            if node["id"] in seen:
                raise ValueError("导图节点 ID 重复或存在环")
            seen.add(node["id"])
            children = node.get("children", [])
            if not isinstance(children, list):
                raise ValueError("导图 children 无效")
            for child in children:
                visit(child)
        visit(content.get("root"))
        for edge in content.get("edges", []):
            if edge.get("source") not in seen or edge.get("target") not in seen:
                raise ValueError("导图存在悬空引用")
    elif kind == "game":
        from jsonschema import validate as validate_schema
        from app.chat.application.game_template_registry import get_game_template_spec
        template = get_game_template_spec(content.get("game_type"))
        validate_schema(content.get("game_data"), json.loads(template.schema_path.read_text()))
        data = content["game_data"]
        items = data.get("pairs", data.get("items", data.get("matches", [])))
        ids = [i.get("id", i.get("pair_id")) for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError("游戏条目 ID 重复")
        if "categories" in data:
            categories = {c["id"] for c in data["categories"]}
            if any(i.get("categoryId") not in categories for i in items):
                raise ValueError("游戏分类引用无效")
    elif kind == "classroom":
        from app.services.classroom_validation import validate_stage
        stage = content.get("stage")
        scenes = _items(content, "scenes")
        if not isinstance(stage, dict):
            raise ValueError("课堂 Stage 无效")
        if any(not isinstance(s.get("content"), dict) or s["content"].get("type") not in {"slide", "quiz", "interactive", "pbl"} for s in scenes):
            raise ValueError("课堂 Scene 类型无效")
        action_types = {"spotlight", "laser", "speech", "wb_open", "wb_draw_text", "wb_draw_shape", "wb_draw_chart", "wb_draw_latex", "wb_draw_table", "wb_draw_line", "wb_clear", "wb_delete", "wb_close", "wb_draw_code", "wb_edit_code", "play_video", "discussion", "widget_highlight", "widget_setState", "widget_annotation", "widget_reveal"}
        for scene in scenes:
            actions = scene.get("actions", [])
            if not isinstance(actions, list) or any(not isinstance(a, dict) or a.get("type") not in action_types for a in actions):
                raise ValueError("课堂 Action 类型无效")
            if any(a.get("type") == "speech" and not _text(a.get("text")) for a in actions):
                raise ValueError("课堂讲解文本不能为空")
        errors = validate_stage(stage, scenes)
        if errors:
            raise ValueError("；".join(errors))
    else:
        raise ValueError("该资料结构暂不支持修改")


def apply_edits(source, edits: list[dict]):
    """Exact matches on strings at explicit JSON paths. No implicit whole-document replacement."""
    result = deepcopy(source)
    if not isinstance(edits, list) or not edits or len(edits) > 100:
        raise ValueError("模型未返回有效修改")
    for edit in edits:
        path, before, after = edit.get("path", []), edit.get("before"), edit.get("after")
        operation = edit.get("op", "replace")
        if not isinstance(path, list):
            raise ValueError("修改路径必须是数组")
        if operation == "replace" and (not _text(before) or not isinstance(after, str) or before == after):
            raise ValueError("修改必须提供路径和真实的前后差异")
        if operation not in {"replace", "insert", "delete"}:
            raise ValueError("不支持的修改操作")
        parent, key, value = None, None, result
        if path and isinstance(path[-1], str) and (path[-1] in {"id", "type", "game_type", "template_id", "source", "url", "src"} or path[-1].endswith(("Id", "Url", "_id", "_url"))):
            raise ValueError("修改不能改变身份、类型或媒体引用")
        if operation == "insert":
            if not path or type(path[-1]) is not int or before is not None or not isinstance(after, (dict, str)):
                raise ValueError("新增条目必须指定数组下标、before=null 和 after 内容")
            for part in path[:-1]:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                elif isinstance(value, list) and type(part) is int and 0 <= part < len(value):
                    value = value[part]
                else:
                    raise ValueError("新增路径不在原文中")
            if not isinstance(value, list) or not 0 <= path[-1] <= len(value):
                raise ValueError("新增位置不在原数组中")
            value.insert(path[-1], deepcopy(after))
            continue
        for key in path:
            parent = value
            if isinstance(parent, list) and type(key) is int and 0 <= key < len(parent):
                value = parent[key]
            elif isinstance(parent, dict) and isinstance(key, str) and key in parent:
                value = parent[key]
            else:
                raise ValueError("修改路径不在原文中")
        if operation == "delete":
            if not isinstance(parent, list) or value != before or after is not None:
                raise ValueError("删除必须唯一匹配原数组条目，after=null")
            del parent[key]
            continue
        if not isinstance(value, str) or value.count(before) != 1:
            raise ValueError("修改片段未唯一匹配原文")
        replacement = value.replace(before, after, 1)
        if parent is None:
            result = replacement
        else:
            parent[key] = replacement
    return result


def content_updates(material: dict, kind: str, content) -> dict:
    updates = {"content": content}
    if kind in {"report", "blog", "lesson_plan"} and isinstance(content, str):
        updates.update({k: content for k in TEXT_KEYS if k in material and isinstance(material[k], str)})
    if kind == "lesson_plan" and isinstance(content, dict):
        updates["plan"] = content
    if kind == "report_outline":
        updates = {"outline": content}
    if kind == "quiz":
        updates["questions"] = content["questions"]
    if kind == "flashcard":
        updates["flashcards"] = content["cards"]
    if kind == "classroom":
        content = deepcopy(content)
        old_actions = {(scene.get("id"), action.get("id")): action for scene in material.get("scenes", []) for action in scene.get("actions", [])}
        invalidated = False
        for scene in content["scenes"]:
            for action in scene.get("actions", []):
                previous = old_actions.get((scene.get("id"), action.get("id")), {})
                if action.get("type") == "speech" and action.get("text") != previous.get("text"):
                    action.pop("audioUrl", None)
                    action.pop("audioId", None)
                    invalidated = True
        updates.update(content=content, stage=content["stage"], scenes=content["scenes"], scenes_count=len(content["scenes"]))
        if invalidated:
            updates["voice_status"] = "pending"
            updates["revision_audio_invalidated"] = True
    return updates


def editable_paths(value, path=()):
    if isinstance(value, str):
        return [list(path)]
    if isinstance(value, dict):
        return [p for key, item in value.items() for p in editable_paths(item, (*path, key))]
    if isinstance(value, list):
        return [p for key, item in enumerate(value) for p in editable_paths(item, (*path, key))]
    return []
