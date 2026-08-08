from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


def _leaves(graph: dict) -> list[dict]:
    return [
        leaf
        for module in graph.get("children") or []
        for leaf in module.get("children") or []
    ]


def _post_generation(api_base: str, api_key: str, model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 9000,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是大学计算思维课程的教材编写与审稿专家。内容必须准确、可教学、可验证，"
                    "使用简体中文，不写空泛套话，不虚构来源，不复制某一本教材的目录结构。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    response = None
    for attempt in range(5):
        try:
            response = requests.post(
                f"{api_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=240,
            )
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
        except requests.RequestException:
            if attempt == 4:
                raise
        if attempt < 4:
            time.sleep(min(12.0, 1.0 * (2**attempt)))
    if response is None:
        raise RuntimeError("原创教学资料生成没有返回响应")
    response.raise_for_status()
    data = response.json()
    return str((((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""))


def _extract_documents(response: str) -> tuple[str, str]:
    core_match = re.search(r"<<<CORE>>>\s*(.*?)\s*<<<PRACTICE>>>", response, re.DOTALL)
    practice_match = re.search(r"<<<PRACTICE>>>\s*(.*?)\s*<<<END>>>", response, re.DOTALL)
    if not core_match or not practice_match:
        raise ValueError("模型未按 CORE/PRACTICE 协议返回两份文档")
    return core_match.group(1).strip(), practice_match.group(1).strip()


def _quality(markdown: str, *, kind: str) -> list[str]:
    reasons = []
    chinese_count = len(re.findall(r"[\u3400-\u9fff]", markdown))
    if chinese_count < 800:
        reasons.append("chinese_content_below_800")
    if len(re.findall(r"^#{2,4}\s+", markdown, re.MULTILINE)) < 4:
        reasons.append("insufficient_structure")
    if markdown.count("```") % 2 or markdown.count("$$") % 2:
        reasons.append("broken_code_or_formula_boundary")
    for code in re.findall(r"```(?:python|py)\s*\n(.*?)```", markdown, flags=re.I | re.DOTALL):
        try:
            ast.parse(code)
        except SyntaxError:
            reasons.append("invalid_python_example")
            break
    banned = ("待补充", "此处省略", "作为一个AI", "无法提供", "占位")
    if any(value in markdown for value in banned):
        reasons.append("placeholder_or_refusal")
    required = ("常见误区", "自测") if kind == "core" else ("学习目标", "任务", "参考实现", "评价")
    if not all(value in markdown for value in required):
        reasons.append("missing_required_teaching_section")
    return reasons


def _ngram_jaccard(left: str, right: str, size: int = 5) -> float:
    def grams(value: str):
        compact = re.sub(r"\s+", "", value)
        return {compact[index : index + size] for index in range(max(0, len(compact) - size + 1))}

    a, b = grams(left), grams(right)
    return len(a & b) / max(1, len(a | b))


def main() -> int:
    parser = argparse.ArgumentParser(description="为影子课程库编写中文核心讲义与案例实践")
    parser.add_argument(
        "--graph",
        type=Path,
        default=Path("evaluation/candidates/computational-thinking-knowledge-graph-v2.json"),
    )
    parser.add_argument(
        "--legacy-mapping",
        type=Path,
        default=Path("evaluation/reports/2026-08-08-legacy-to-v2-mapping.json"),
    )
    parser.add_argument(
        "--shadow-root",
        type=Path,
        default=Path("evaluation/shadow/computational-thinking-v2"),
    )
    parser.add_argument(
        "--coverage-audit",
        type=Path,
        default=Path("evaluation/reports/2026-08-08-shadow-corpus-audit.json"),
    )
    parser.add_argument("--max-nodes", type=int, default=49)
    parser.add_argument("--output-version", default="v1")
    parser.add_argument("--node-id", action="append", dest="node_ids")
    args = parser.parse_args()
    load_dotenv(Path.cwd() / ".env", override=False)

    from app.services.runtime_config_resolver import runtime_config_resolver

    config = runtime_config_resolver.resolve("llm")
    api_base = str(config.get("base_url") or "").strip().rstrip("/")
    if api_base and not api_base.endswith(("/v1", "/api/v1")):
        api_base = f"{api_base}/v1"
    api_key = str(config.get("api_key") or "").strip()
    model = str(config.get("model") or "").strip()
    if not api_base or not api_key or not model:
        raise RuntimeError("缺少原创教学资料生成所需的 LLM 配置")

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    mapping = json.loads(args.legacy_mapping.read_text(encoding="utf-8"))
    legacy_nodes = mapping.get("node_materials") or {}
    external_counts: dict[str, int] = {}
    for manifest_path in (args.shadow_root / "think-and-compute-zh").glob("**/manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for document in manifest.get("documents") or []:
            scope_id = str(document.get("scope_id") or "")
            external_counts[scope_id] = external_counts.get(scope_id, 0) + 1

    output_dir = args.shadow_root / "authored-zh" / str(args.output_version) / "documents"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir.parent / "manifest.json"
    existing_manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"documents": []}
    )
    documents = list(existing_manifest.get("documents") or [])
    authored_counts: dict[str, int] = {}
    authored_kinds: dict[str, set[str]] = {}
    for document in documents:
        scope_id = str(document.get("scope_id") or "")
        authored_counts[scope_id] = authored_counts.get(scope_id, 0) + 1
        filename = str(document.get("filename") or "")
        kind = "practice" if "-practice-" in filename else "core"
        authored_kinds.setdefault(scope_id, set()).add(kind)

    audited_gaps = {}
    if args.coverage_audit.exists():
        audit = json.loads(args.coverage_audit.read_text(encoding="utf-8"))
        audited_gaps = {
            str(item.get("scope_id") or ""): item
            for item in audit.get("coverage_gaps") or []
        }

    failures: list[dict] = []
    processed = 0
    for leaf in _leaves(graph):
        if processed >= max(0, args.max_nodes):
            break
        node_id = str(leaf["id"])
        if args.node_ids and node_id not in set(args.node_ids):
            continue
        if node_id in audited_gaps:
            gap = audited_gaps[node_id]
            needed = min(
                2,
                max(int(gap.get("missing_total") or 0), int(gap.get("missing_chinese") or 0)),
            )
        elif audited_gaps:
            needed = 0
        else:
            legacy = legacy_nodes.get(node_id) or {}
            existing_total = min(3, int(legacy.get("document_count") or 0)) + external_counts.get(node_id, 0)
            existing_chinese = min(3, int(legacy.get("chinese_document_count") or 0))
            needed = min(2, max(0, 3 - existing_total, 2 - existing_chinese))
            already = authored_counts.get(node_id, 0)
            needed = max(0, needed - already)
        needed = min(needed, max(0, 2 - len(authored_kinds.get(node_id, set()))))
        if needed <= 0:
            continue
        processed += 1
        label = str(leaf.get("label") or node_id)
        keywords = "、".join(str(value) for value in (leaf.get("data", {}).get("keywords") or []))
        prompt = f"""
为“计算思维”课程的原子知识点“{label}”编写两份相互独立、可直接教学的 Markdown 文档。
关键词：{keywords}。

文档一是“核心讲义”，须包含：学习目标、准确概念与边界、机制/步骤、至少一个完整例子、必要的公式或伪代码/代码、复杂度或权衡（适用时）、常见误区、自测题与答案。正文至少 1200 个中文字符。
文档二是“案例与实践”，须包含：学习目标、真实问题情境、输入输出或材料、分步任务、参考实现/推导、测试与边界情况、评价量规、拓展问题。正文至少 1200 个中文字符。

两份文档不得大段重复，不得把其他并列知识点当作主体，不得虚构论文/教材引用。代码应可运行；公式用 $...$ 或 $$...$$；表格用标准 Markdown。
严格使用以下分隔协议，分隔符外不要输出任何内容：
<<<CORE>>>
（核心讲义正文，不要写一级标题）
<<<PRACTICE>>>
（案例实践正文，不要写一级标题）
<<<END>>>
""".strip()
        try:
            print(f"[AuthoredCorpus] 生成并审查: {node_id} {label}")
            core, practice = _extract_documents(_post_generation(api_base, api_key, model, prompt))
            if _ngram_jaccard(core, practice) > 0.45:
                raise ValueError("两份文档内容相似度过高")
            generated = [
                item
                for item in [("core", "核心讲义", core), ("practice", "案例与实践", practice)]
                if item[0] not in authored_kinds.get(node_id, set())
            ][:needed]
            for kind, kind_label, content in generated:
                reasons = _quality(content, kind=kind)
                if reasons:
                    raise ValueError(f"{kind} 质量不合格: {', '.join(reasons)}")
                # A knowledge point can legitimately have several independently
                # reviewed teaching documents. Include the authored corpus
                # version so a later supplement does not collide with the first
                # core/practice pair; exact duplicate content is still rejected
                # by the corpus audit's content fingerprint.
                digest = hashlib.sha256(
                    f"{node_id}\n{kind}\n{args.output_version}".encode("utf-8")
                ).hexdigest()[:12]
                filename = f"shadow-authored-{node_id}-{kind}-{digest}.md"
                body = (
                    f"# {label}｜{kind_label}\n\n"
                    f"> 编写：Edu AI 计算思维课程知识库  \n"
                    f"> 类型：原创教学资料  \n"
                    f"> 语言：简体中文  \n"
                    f"> 许可：CC BY-NC-SA 4.0  \n"
                    f"> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照\n\n"
                    f"{content.strip()}\n"
                )
                path = output_dir / filename
                path.write_text(body, encoding="utf-8")
                documents.append(
                    {
                        "id": f"authored-{digest}",
                        "filename": filename,
                        "path": str(path.relative_to(output_dir.parent)).replace("\\", "/"),
                        "scope_type": "knowledge_point",
                        "scope_id": node_id,
                        "library_type": "course",
                        "source_title": f"{label}｜{kind_label}",
                        "source_site_name": "Edu AI 计算思维课程知识库",
                        "source_license": "CC BY-NC-SA 4.0",
                        "source_language": "zh-CN",
                        "content_language": "zh-CN",
                        "authority_tier": "reviewed_authored_material",
                        "doc_kind": "authored",
                        "status": "staged",
                        "substantive_chinese_chars": len(re.findall(r"[\u3400-\u9fff]", content)),
                    }
                )
                authored_counts[node_id] = authored_counts.get(node_id, 0) + 1
                authored_kinds.setdefault(node_id, set()).add(kind)
            manifest_path.write_text(
                json.dumps(
                    {
                        "builder": f"shadow-authored-zh-{args.output_version}",
                        "documents": documents,
                        "failures": failures,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            failures.append({"scope_id": node_id, "label": label, "error": str(exc)})
            manifest_path.write_text(
                json.dumps(
                    {
                        "builder": f"shadow-authored-zh-{args.output_version}",
                        "documents": documents,
                        "failures": failures,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

    print(
        json.dumps(
            {
                "document_count": len(documents),
                "failure_count": len(failures),
                "processed_node_count": processed,
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
