from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


RULES: tuple[tuple[str, str], ...] = (
    (r"广度优先|深度优先|\bBFS\b|\bDFS\b", "graph-traversal"),
    (r"二分查找|线性查找", "linear-binary-search"),
    (r"快速排序|归并排序|分治|汉诺塔", "divide-conquer"),
    (r"冒泡排序|选择排序|插入排序", "elementary-sort"),
    (r"动态规划|背包|编辑距离|爬楼梯|零钱兑换", "dynamic-programming"),
    (r"贪心", "greedy"),
    (r"时间复杂度|空间复杂度|复杂度分析|算法效率", "complexity"),
    (r"迭代与递归|递归", "iteration-recursion"),
    (r"字符编码|Unicode|ASCII", "data-encoding"),
    (r"二进制|进制|补码", "binary-number"),
    (r"哈希|散列", "hash"),
    (r"优先队列|堆", "heap"),
    (r"二叉树|搜索树|AVL|树", "tree"),
    (r"栈|队列", "stack-queue"),
    (r"数组|链表|列表", "array-linked-list"),
    (r"图的表示|图基础|图结构|图算法|图", "graph"),
    (r"算法定义|算法是什么", "algorithm-properties"),
    (r"数据结构定义|数据结构与算法", "data-organization"),
    (r"正确性|测试|调试", "correctness-testing"),
    (r"回溯|全排列|子集和", "backtracking"),
)


def _substantive(markdown: str) -> str:
    output = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "![", "!!!")):
            continue
        if stripped.startswith(("来源：", "许可：", "语言：", "版本：", "署名：", "使用限制：")):
            continue
        output.append(stripped)
    return "\n".join(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="将旧教材资料映射到课程图谱 v2 候选节点")
    parser.add_argument(
        "course_dir",
        type=Path,
        nargs="?",
        default=Path("../course_data/courses/computational-thinking"),
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=Path("evaluation/candidates/computational-thinking-knowledge-graph-v2.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    course_dir = args.course_dir.resolve()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    leaf_ids = {
        child["id"]
        for module in graph.get("children") or []
        for child in module.get("children") or []
    }
    index = json.loads((course_dir / "knowledge_base" / "index.json").read_text(encoding="utf-8"))
    mapped: dict[str, list[dict]] = defaultdict(list)
    rejected: list[dict] = []
    unmapped: list[dict] = []

    for document in index:
        path = course_dir / str(document.get("path") or "")
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        substantive = _substantive(text)
        title = str(document.get("source_title") or document.get("filename") or "")
        # 旧资料已经按教材小节命名；只用标题决定主归属，避免正文示例中偶然
        # 出现“数组/栈”等词时把整份资料错挂到示例概念下。
        haystack = title
        reasons = []
        if len(substantive) < 800 and not (
            len(re.findall(r"[\u3400-\u9fff]", substantive)) >= 500
            and any(marker in text for marker in ("```", "$$", "| ---"))
        ):
            reasons.append("content_too_thin")
        if any(value in text for value in ("教材原文对应小节", "一位少女翩翩起舞", "待补充")):
            reasons.append("placeholder_content")
        if reasons:
            rejected.append(
                {"document_id": document.get("id"), "title": title, "reasons": reasons}
            )
            continue

        node_id = None
        for pattern, candidate in RULES:
            if re.search(pattern, haystack, re.IGNORECASE):
                node_id = candidate
                break
        if node_id is None or node_id not in leaf_ids:
            unmapped.append({"document_id": document.get("id"), "title": title})
            continue
        mapped[node_id].append(
            {
                "document_id": document.get("id"),
                "title": title,
                "path": document.get("path"),
                "language": document.get("content_language"),
                "authority_tier": document.get("authority_tier"),
                "source_url": document.get("source_url"),
            }
        )

    node_summary = {
        node_id: {
            "document_count": len(documents),
            "chinese_document_count": sum(
                1 for document in documents
                if str(document.get("language") or "").lower().startswith("zh")
            ),
            "documents": documents,
        }
        for node_id, documents in sorted(mapped.items())
    }
    qualified = sum(
        1 for value in node_summary.values()
        if value["document_count"] >= 3 and value["chinese_document_count"] >= 2
    )
    report = {
        "graph_leaf_count": len(leaf_ids),
        "legacy_document_count": len(index),
        "mapped_document_count": sum(len(value) for value in mapped.values()),
        "rejected_document_count": len(rejected),
        "unmapped_document_count": len(unmapped),
        "nodes_with_materials": len(node_summary),
        "nodes_already_qualified": qualified,
        "node_materials": node_summary,
        "rejected_documents": rejected,
        "unmapped_documents": unmapped,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
