"""Map staged textbook chunks onto confirmed graph leaves."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.services.course_knowledge_source_discovery import execution_topics


MINIMUM_MAPPING_CONFIDENCE = 0.25
MAX_MAPPED_CHUNKS_PER_TEXTBOOK_LEAF = 4

_OPERATING_SYSTEM_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("进程的概念", "进程概念"), ("process", "processes", "process control block", "pcb")),
    (("进程控制块", "上下文切换"), ("process control block", "pcb", "context switch", "context switching")),
    (("进程状态",), ("process state", "ready", "running", "blocked", "sleep")),
    (("线程",), ("thread", "threads", "multithreading")),
    (("系统调用",), ("system call", "system calls", "trap", "interface")),
    (("管道", "共享内存", "进程间通信"), ("pipe", "pipes", "shared memory", "interprocess communication", "ipc")),
    (("调度基本", "调度指标", "调度准则", "CPU 调度", "常见cpu调度", "常见 CPU 调度"), ("scheduling", "scheduler", "fcfs", "sjf", "round robin", "turnaround", "response")),
    (("等待时间计算", "计算实例"), ("waiting time", "turnaround time", "scheduling example", "workload", "response time")),
    (("先来先服务", "短作业优先"), ("fcfs", "first come", "sjf", "shortest job")),
    (("时间片轮转", "优先级调度"), ("round robin", "priority scheduling", "time slice")),
    (("临界区", "竞争条件"), ("critical section", "race", "mutual exclusion", "locking")),
    (("信号量",), ("semaphore", "semaphores", "synchronization")),
    (("典型同步", "生产者消费者", "生产者-消费者"), ("producer consumer", "producer", "consumer", "bounded buffer", "synchronization")),
    (("死锁的概念", "必要条件"), ("deadlock", "lock ordering", "circular wait")),
    (("死锁的处理", "死锁预防", "避免与检测"), ("deadlock prevention", "avoidance", "detection", "recovery")),
    (("分页", "地址转换"), ("paging", "page table", "address space", "address translation")),
    (("缺页", "页面置换"), ("page fault", "replacement", "fifo", "lru", "opt")),
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _terms(value: str) -> set[str]:
    normalized = _clean(value).casefold()
    result = set(re.findall(r"[a-z0-9+#.-]{2,}", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    result.update(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    return {item for item in result if item}


def _cross_language_terms(topic: Mapping[str, Any]) -> set[str]:
    # Cross-language aliases identify the leaf's primary concept.  Objectives
    # often mention a broad parent module (for example a cgroups leaf may say
    # "extend the process module"); using that prose caused an entire process
    # textbook to be attached to the new cgroups leaf.  Keep aliases anchored
    # to the explicit leaf title and let ordinary overlap handle supporting
    # objective language conservatively.
    text = _clean(topic.get("title"))
    aliases: set[str] = set()
    folded = text.casefold()
    for chinese_signals, english_signals in _OPERATING_SYSTEM_ALIASES:
        if any(signal in text for signal in chinese_signals) or any(
            signal.casefold() in folded for signal in english_signals
        ):
            for signal in english_signals:
                aliases.update(_terms(signal))
    return aliases


def map_textbook_chunks_to_graph(build: Mapping[str, Any]) -> dict[str, Any]:
    graph = dict(build.get("graph_draft") or {})
    topics = execution_topics(build)
    refs_by_leaf: dict[str, set[str]] = {}

    def visit(node: Mapping[str, Any]) -> None:
        children = [item for item in node.get("children") or [] if isinstance(item, Mapping)]
        if not children:
            refs_by_leaf[str(node.get("id") or "")] = {
                _clean(item).casefold()
                for item in (node.get("data") or {}).get("source_outline_refs") or []
                if _clean(item)
            }
        for child in children:
            visit(child)

    visit(graph)
    topic_terms = {
        topic["topic_id"]: _terms(f"{topic['title']} {topic['objective']} {topic['graph_path']}")
        for topic in topics
    }
    cross_language_terms = {
        topic["topic_id"]: _cross_language_terms(topic) for topic in topics
    }
    mappings: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    textbooks = [
        *(build.get("textbooks") or []),
        *(build.get("online_textbooks") or []),
    ]
    for textbook in textbooks:
        if textbook.get("status") != "ready":
            continue
        textbook_id = str(textbook.get("textbook_id") or "")
        for chunk in (textbook.get("parse_result") or {}).get("chunks") or []:
            chapter_keys = {
                _clean(chunk.get("chapter_id")).casefold(),
                _clean(chunk.get("chapter_title")).casefold(),
            } - {""}
            exact_leaf = next(
                (
                    topic["topic_id"]
                    for topic in topics
                    if refs_by_leaf.get(topic["topic_id"], set()) & chapter_keys
                ),
                None,
            )
            targets: list[tuple[str, str, float]] = []
            if exact_leaf:
                targets = [(exact_leaf, "outline_anchor", 1.0)]
            else:
                chunk_terms = _terms(
                    f"{chunk.get('chapter_title')} {_clean(chunk.get('content'))[:3000]}"
                )
                chapter_title = _clean(chunk.get("chapter_title")).casefold()
                cross_scores = {
                    topic["topic_id"]: (
                        len(cross_language_terms[topic["topic_id"]] & chunk_terms)
                        / len(cross_language_terms[topic["topic_id"]])
                        if cross_language_terms[topic["topic_id"]]
                        else 0.0
                    )
                    for topic in topics
                }
                scores = {
                    topic["topic_id"]: (
                        0.9
                        if _clean(topic["title"]).casefold() in chapter_title
                        else max(
                            len(topic_terms[topic["topic_id"]] & chunk_terms)
                            / len(topic_terms[topic["topic_id"]])
                            if topic_terms[topic["topic_id"]]
                            else 0.0,
                            cross_scores[topic["topic_id"]],
                        )
                    )
                    for topic in topics
                }
                direct_cross_language_targets = sorted(
                    (
                        (topic_id, "cross_language_semantic", confidence)
                        for topic_id, confidence in cross_scores.items()
                        if confidence >= MINIMUM_MAPPING_CONFIDENCE
                    ),
                    key=lambda item: item[2],
                    reverse=True,
                )
                if direct_cross_language_targets:
                    # A textbook section can legitimately support multiple nearby
                    # leaves (for example one scheduling chapter supports both the
                    # algorithm overview and a waiting-time worked example).  A
                    # single-winner rule made every such section "ambiguous" and
                    # left both leaves uncovered.  Explicit bilingual concept
                    # evidence is strong enough to retain each supported mapping;
                    # generic lexical matches still use the ambiguity guard below.
                    targets = direct_cross_language_targets
                else:
                    ranked_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
                    leaf_id, confidence = ranked_scores[0] if ranked_scores else ("", 0.0)
                    second_confidence = ranked_scores[1][1] if len(ranked_scores) > 1 else 0.0
                    if (
                        confidence >= MINIMUM_MAPPING_CONFIDENCE
                        and second_confidence > 0
                        and confidence - second_confidence < 0.05
                    ):
                        targets = [("", "ambiguous", confidence)]
                    else:
                        targets = [(leaf_id, "semantic_overlap", confidence)]
            for leaf_id, method, confidence in targets:
                record = {
                    "textbook_id": textbook_id,
                    "filename": textbook.get("filename"),
                    "chunk_id": chunk.get("chunk_id"),
                    "chapter_id": chunk.get("chapter_id"),
                    "chapter_title": chunk.get("chapter_title"),
                    "page": chunk.get("page"),
                    "content": chunk.get("content"),
                    "content_chars": len(_clean(chunk.get("content"))),
                    "content_hash": chunk.get("content_hash"),
                    "knowledge_node_id": leaf_id or None,
                    "mapping_method": method,
                    "mapping_confidence": round(float(confidence), 4),
                    "source_url": chunk.get("source_url") or textbook.get("source_url"),
                }
                if leaf_id and confidence >= MINIMUM_MAPPING_CONFIDENCE:
                    mappings.append(record)
                else:
                    record["knowledge_node_id"] = None
                    unmapped.append(record)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in mappings:
        grouped.setdefault(
            (str(item.get("textbook_id") or ""), str(item.get("knowledge_node_id") or "")),
            [],
        ).append(item)
    bounded_mappings = []
    for items in grouped.values():
        bounded_mappings.extend(sorted(
            items,
            key=lambda item: (
                float(item.get("mapping_confidence") or 0),
                int(item.get("content_chars") or 0),
            ),
            reverse=True,
        )[:MAX_MAPPED_CHUNKS_PER_TEXTBOOK_LEAF])
    pruned_mapping_count = len(mappings) - len(bounded_mappings)
    return {
        "mappings": bounded_mappings,
        "unmapped": unmapped,
        "metrics": {
            "mapped_chunk_count": len(bounded_mappings),
            "pruned_redundant_mapping_count": pruned_mapping_count,
            "unmapped_chunk_count": len(unmapped),
            "ambiguous_mapping_count": sum(
                item.get("mapping_method") == "ambiguous" for item in unmapped
            ),
            "invalid_mapping_count": 0,
        },
    }
