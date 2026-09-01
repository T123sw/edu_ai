from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


UNWANTED_LABELS = {"序", "序言", "前言", "参考文献", "纸质书", "关于本书"}
PLACEHOLDER_PATTERNS = (
    "教材原文对应小节",
    "一位少女翩翩起舞",
    "此处为占位",
    "待补充",
    "暂无内容",
)


def _walk(node: dict[str, Any], *, parent_id: str | None = None):
    yield node, parent_id
    for child in node.get("children") or []:
        yield from _walk(child, parent_id=str(node.get("id") or ""))


def _substantive_text(markdown: str) -> str:
    lines = []
    metadata_prefixes = (
        "来源：",
        "许可：",
        "语言：",
        "版本：",
        "署名：",
        "使用限制：",
        "translation_notice:",
    )
    for line in str(markdown or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(metadata_prefixes):
            continue
        if stripped.startswith("![") or stripped.startswith("!!!"):
            continue
        if stripped.startswith("#"):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="审计课程知识图谱与教学资料质量")
    parser.add_argument(
        "course_dir",
        type=Path,
        nargs="?",
        default=Path("../course_data/courses/computational-thinking"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    course_dir = args.course_dir.resolve()
    graph = json.loads((course_dir / "knowledge_graph.json").read_text(encoding="utf-8"))
    index = json.loads((course_dir / "knowledge_base" / "index.json").read_text(encoding="utf-8"))
    nodes_with_parent = list(_walk(graph))
    nodes = [node for node, _ in nodes_with_parent]
    node_ids = {str(node.get("id") or "") for node in nodes}
    leaves = [node for node in nodes if not (node.get("children") or [])]
    leaf_ids = {str(node.get("id") or "") for node in leaves}
    docs_by_scope: dict[str, list[dict[str, Any]]] = defaultdict(list)
    quality_by_scope: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_domains: Counter[str] = Counter()
    content_hashes: dict[str, list[str]] = defaultdict(list)
    invalid_docs: list[dict[str, Any]] = []
    missing_media: list[dict[str, str]] = []

    for document in index:
        scope_id = str(document.get("scope_id") or "")
        docs_by_scope[scope_id].append(document)
        source_domains[str(document.get("source_domain") or "unknown")] += 1
        path = course_dir / str(document.get("path") or "")
        reasons: list[str] = []
        if not path.exists():
            reasons.append("file_missing")
            text = ""
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                reasons.append("not_utf8_text")
                text = ""
        substantive = _substantive_text(text)
        chinese_chars = len(re.findall(r"[\u3400-\u9fff]", substantive))
        has_structure = bool(
            "```" in text or "$$" in text or re.search(r"^\s*\|.+\|\s*$", text, re.MULTILINE)
        )
        if len(substantive) < 800 and not (chinese_chars >= 500 and has_structure):
            reasons.append("content_too_thin")
        if any(pattern in text for pattern in PLACEHOLDER_PATTERNS):
            reasons.append("placeholder_content")
        if document.get("library_type") != "course":
            reasons.append("wrong_library_scope")
        if scope_id not in node_ids:
            reasons.append("unknown_graph_scope")

        normalized = re.sub(r"\s+", "", substantive).lower()
        if normalized:
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            content_hashes[digest].append(str(document.get("id") or path.name))

        for image_match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
            target = image_match.group(1).strip().split("#", 1)[0].split("?", 1)[0]
            if target.startswith(("http://", "https://", "data:")):
                continue
            if target and not (path.parent / target).resolve().exists():
                missing_media.append({"document_id": str(document.get("id") or ""), "target": target})

        audit_row = {
            "document_id": str(document.get("id") or ""),
            "filename": str(document.get("filename") or path.name),
            "scope_id": scope_id,
            "substantive_chars": len(substantive),
            "chinese_chars": chinese_chars,
            "reasons": reasons,
        }
        if reasons:
            invalid_docs.append(audit_row)
        else:
            quality_by_scope[scope_id].append(audit_row)

    duplicate_content_groups = [ids for ids in content_hashes.values() if len(ids) > 1]
    duplicate_leaf_labels = [
        label
        for label, count in Counter(str(node.get("label") or "").strip() for node in leaves).items()
        if label and count > 1
    ]
    unwanted_nodes = [
        {"id": str(node.get("id") or ""), "label": str(node.get("label") or "")}
        for node in nodes
        if str(node.get("label") or "").strip() in UNWANTED_LABELS
    ]
    uncovered = []
    for leaf in leaves:
        leaf_id = str(leaf.get("id") or "")
        quality_docs = quality_by_scope.get(leaf_id, [])
        chinese_quality = sum(
            1 for doc in docs_by_scope.get(leaf_id, [])
            if str(doc.get("content_language") or "").lower().startswith("zh")
            and any(row["document_id"] == str(doc.get("id") or "") for row in quality_docs)
        )
        if len(quality_docs) < 3 or chinese_quality < 2:
            uncovered.append(
                {
                    "node_id": leaf_id,
                    "label": str(leaf.get("label") or ""),
                    "document_count": len(docs_by_scope.get(leaf_id, [])),
                    "quality_document_count": len(quality_docs),
                    "chinese_quality_document_count": chinese_quality,
                }
            )

    report = {
        "course_dir": str(course_dir),
        "graph": {
            "node_count": len(nodes),
            "leaf_count": len(leaves),
            "duplicate_leaf_labels": duplicate_leaf_labels,
            "unwanted_nodes": unwanted_nodes,
        },
        "documents": {
            "document_count": len(index),
            "valid_document_count": len(index) - len(invalid_docs),
            "invalid_document_count": len(invalid_docs),
            "duplicate_content_group_count": len(duplicate_content_groups),
            "missing_media_count": len(missing_media),
            "source_domains": dict(source_domains.most_common()),
        },
        "coverage": {
            "qualified_leaf_count": len(leaves) - len(uncovered),
            "coverage_rate": round((len(leaves) - len(uncovered)) / len(leaves), 4) if leaves else 0.0,
            "unqualified_leaf_count": len(uncovered),
        },
        "unqualified_leaves": uncovered,
        "invalid_documents": invalid_docs,
        "duplicate_content_groups": duplicate_content_groups,
        "missing_media": missing_media,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

