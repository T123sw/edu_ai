from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from langchain_core.documents import Document

from modules.rag_v2.rag_main.system import DocumentProcessor


def _leaves(graph: dict) -> list[dict]:
    return [leaf for module in graph.get("children") or [] for leaf in module.get("children") or []]


def _content_quality(text: str, language: str) -> list[str]:
    reasons = []
    visible = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    visible = re.sub(r"^> (?:来源|许可|语言|版本|署名|使用限制|编写|类型|编写依据).*$", " ", visible, flags=re.MULTILINE)
    visible = re.sub(r"[#>*_`|\-]+", " ", visible)
    visible = re.sub(r"\s+", " ", visible).strip()
    chinese = len(re.findall(r"[\u3400-\u9fff]", visible))
    if str(language).lower().startswith("zh"):
        has_teaching_structure = "```" in text or "$$" in text or bool(
            re.search(r"^\s*\|.+\|\s*$", text, re.MULTILINE)
        )
        if chinese < 800 and not (chinese >= 500 and has_teaching_structure):
            reasons.append("chinese_content_below_800")
    elif len(visible) < 1200:
        reasons.append("source_content_below_1200")
    if text.count("```") % 2:
        reasons.append("broken_code_fence")
    if text.count("$$") % 2:
        reasons.append("broken_display_math")
    for code in re.findall(r"```(?:python|py)\s*\n(.*?)```", text, flags=re.I | re.DOTALL):
        try:
            ast.parse(code)
        except SyntaxError:
            reasons.append("invalid_python_example")
            break
    if any(value in text for value in ("待补充", "教材原文对应小节", "暂无内容", "占位")):
        reasons.append("placeholder_content")
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser(description="审计 v2 影子课程语料与节点覆盖")
    parser.add_argument("--graph", type=Path, default=Path("evaluation/candidates/computational-thinking-knowledge-graph-v2.json"))
    parser.add_argument(
        "--legacy-mapping",
        type=Path,
        default=Path("scripts/fixtures/course_corpus_20260808/2026-08-08-legacy-to-v2-mapping.json"),
    )
    parser.add_argument("--course-dir", type=Path, default=Path("../course_data/courses/computational-thinking"))
    parser.add_argument("--shadow-root", type=Path, default=Path("evaluation/shadow/computational-thinking-v2"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    leaves = _leaves(graph)
    leaf_ids = {str(leaf["id"]) for leaf in leaves}
    leaves_by_id = {str(leaf["id"]): leaf for leaf in leaves}
    mapping = json.loads(args.legacy_mapping.read_text(encoding="utf-8"))
    candidates: list[dict] = []

    for node_id, value in (mapping.get("node_materials") or {}).items():
        for document in (value.get("documents") or [])[:3]:
            candidates.append(
                {
                    **document,
                    "scope_id": node_id,
                    "source_group": "legacy-reviewed",
                    "absolute_path": args.course_dir / str(document.get("path") or ""),
                }
            )

    for manifest_path in args.shadow_root.glob("**/manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for document in manifest.get("documents") or []:
            candidates.append(
                {
                    **document,
                    "source_group": str(manifest.get("source_id") or manifest.get("builder") or "shadow"),
                    "absolute_path": manifest_path.parent / str(document.get("path") or ""),
                }
            )

    repaired_legacy_ids = {
        str(material.get("legacy_document_id") or "")
        for material in candidates
        if material.get("legacy_document_id")
    }
    candidates = [
        material
        for material in candidates
        if not (
            material.get("source_group") == "legacy-reviewed"
            and str(material.get("document_id") or "") in repaired_legacy_ids
        )
    ]

    processor = DocumentProcessor()
    accepted_by_node: dict[str, list[dict]] = defaultdict(list)
    invalid: list[dict] = []
    missing_media: list[dict] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    seen_ids: set[str] = set()
    for material in candidates:
        material_id = str(material.get("document_id") or material.get("id") or material.get("filename") or "")
        if material_id in seen_ids:
            continue
        seen_ids.add(material_id)
        node_id = str(material.get("scope_id") or "")
        path = Path(material["absolute_path"])
        reasons = []
        if node_id not in leaf_ids:
            reasons.append("unknown_scope")
        if not path.exists():
            reasons.append("file_missing")
            text = ""
        else:
            text = path.read_text(encoding="utf-8", errors="strict")
            reasons.extend(_content_quality(text, str(material.get("content_language") or material.get("language") or "")))
            language = str(material.get("content_language") or material.get("language") or "").lower()
            leaf = leaves_by_id.get(node_id) or {}
            keywords = [
                str(value).strip()
                for value in ((leaf.get("data") or {}).get("keywords") or [])
                if len(str(value).strip()) >= 2
            ]
            if language.startswith("zh") and keywords and not any(keyword in text for keyword in keywords):
                reasons.append("no_topic_keyword_match")
            chunks = processor.split_documents(
                [Document(page_content=text, metadata={"source": str(path), "document_name": path.name})]
            )
            if not chunks:
                reasons.append("no_structural_chunks")
            if any(int((chunk.metadata or {}).get("token_count") or 0) > 800 for chunk in chunks):
                reasons.append("chunk_over_token_cap")
        for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
            target = match.group(1).strip().split("#", 1)[0].split("?", 1)[0]
            if target.startswith(("http://", "https://", "data:")):
                reasons.append("remote_or_inline_media_not_materialized")
                missing_media.append({"material_id": material_id, "target": target})
            elif target and not (path.parent / target).resolve().exists():
                reasons.append("missing_local_media")
                missing_media.append({"material_id": material_id, "target": target})
        normalized = re.sub(r"\s+", "", text).lower()
        if normalized:
            hashes[hashlib.sha256(normalized.encode("utf-8")).hexdigest()].append(material_id)
        row = {
            "material_id": material_id,
            "scope_id": node_id,
            "title": material.get("source_title") or material.get("filename"),
            "path": str(path),
            "language": material.get("content_language") or material.get("language"),
            "source_group": material.get("source_group"),
            "authority_tier": material.get("authority_tier"),
            "doc_kind": material.get("doc_kind"),
            "source_url": material.get("source_url") or material.get("url"),
            "reasons": sorted(set(reasons)),
        }
        if reasons:
            invalid.append(row)
        else:
            accepted_by_node[node_id].append(row)

    gaps = []
    for leaf in leaves:
        node_id = str(leaf["id"])
        materials = accepted_by_node.get(node_id, [])
        chinese = sum(1 for item in materials if str(item.get("language") or "").lower().startswith("zh"))
        if len(materials) < 3 or chinese < 2:
            gaps.append(
                {
                    "scope_id": node_id,
                    "label": leaf["label"],
                    "valid_document_count": len(materials),
                    "chinese_document_count": chinese,
                    "missing_total": max(0, 3 - len(materials)),
                    "missing_chinese": max(0, 2 - chinese),
                }
            )

    duplicate_groups = [ids for ids in hashes.values() if len(ids) > 1]
    report = {
        "graph_leaf_count": len(leaves),
        "candidate_material_count": len(candidates),
        "valid_material_count": sum(len(value) for value in accepted_by_node.values()),
        "invalid_material_count": len(invalid),
        "qualified_node_count": len(leaves) - len(gaps),
        "coverage_rate": round((len(leaves) - len(gaps)) / len(leaves), 4) if leaves else 0.0,
        "missing_media_count": len(missing_media),
        "duplicate_content_group_count": len(duplicate_groups),
        "accepted_materials": [
            material
            for node_id in sorted(accepted_by_node)
            for material in accepted_by_node[node_id]
        ],
        "coverage_gaps": gaps,
        "invalid_materials": invalid,
        "missing_media": missing_media,
        "duplicate_content_groups": duplicate_groups,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
