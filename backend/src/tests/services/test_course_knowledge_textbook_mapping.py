from __future__ import annotations

from app.services.course_knowledge_textbook_mapping import map_textbook_chunks_to_graph


def test_textbook_mapping_prefers_outline_anchor_then_semantic_overlap():
    build = {
        "graph_draft": {
            "id": "root",
            "label": "代数",
            "children": [{
                "id": "module",
                "label": "模块",
                "children": [
                    {"id": "linear", "label": "一元方程", "data": {"summary": "方程求解", "source_outline_refs": ["chapter-1"]}, "children": []},
                    {"id": "function", "label": "一次函数", "data": {"summary": "函数图像与斜率"}, "children": []},
                ],
            }],
        },
        "textbooks": [{
            "textbook_id": "book-1",
            "filename": "教材.md",
            "status": "ready",
            "parse_result": {"chunks": [
                {"chunk_id": "c1", "chapter_id": "chapter-1", "chapter_title": "方程", "content": "解方程", "content_hash": "h1"},
                {"chunk_id": "c2", "chapter_id": "chapter-2", "chapter_title": "函数图像", "content": "一次函数图像的斜率", "content_hash": "h2"},
                {"chunk_id": "c3", "chapter_id": "appendix", "chapter_title": "附录", "content": "天气与地理", "content_hash": "h3"},
            ]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)

    by_chunk = {item["chunk_id"]: item for item in result["mappings"]}
    assert by_chunk["c1"]["knowledge_node_id"] == "linear"
    assert by_chunk["c1"]["mapping_method"] == "outline_anchor"
    assert by_chunk["c2"]["knowledge_node_id"] == "function"
    assert result["unmapped"][0]["chunk_id"] == "c3"


def test_online_textbook_is_mapped_to_multiple_leaf_nodes_at_required_confidence():
    build = {
        "graph_draft": {
            "id": "root",
            "label": "高等数学",
            "children": [{
                "id": "module",
                "label": "微积分",
                "children": [
                    {"id": "limit", "label": "函数极限", "data": {"summary": "极限定义与计算"}, "children": []},
                    {"id": "derivative", "label": "导数", "data": {"summary": "导数定义与求导法则"}, "children": []},
                ],
            }],
        },
        "textbooks": [],
        "online_textbooks": [{
            "textbook_id": "online-book",
            "filename": "高等数学完整教材.pdf",
            "status": "ready",
            "source_url": "https://example.edu/calculus.pdf",
            "parse_result": {"chunks": [
                {"chunk_id": "limit-chapter", "chapter_title": "函数极限", "content": "函数极限的定义、性质与计算方法。", "content_hash": "limit-hash"},
                {"chunk_id": "derivative-chapter", "chapter_title": "导数", "content": "导数定义、求导法则和导函数。", "content_hash": "derivative-hash"},
            ]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)

    by_chunk = {item["chunk_id"]: item for item in result["mappings"]}
    assert by_chunk["limit-chapter"]["knowledge_node_id"] == "limit"
    assert by_chunk["derivative-chapter"]["knowledge_node_id"] == "derivative"
    assert all(item["mapping_confidence"] >= 0.25 for item in by_chunk.values())
    assert all(item["source_url"] == "https://example.edu/calculus.pdf" for item in by_chunk.values())


def test_ambiguous_semantic_mapping_is_not_counted_as_coverage():
    build = {
        "graph_draft": {
            "id": "root",
            "label": "Algebra",
            "children": [{
                "id": "module",
                "label": "Foundations",
                "children": [
                    {"id": "linear", "label": "Linear algebra", "data": {"summary": "algebra vector"}, "children": []},
                    {"id": "abstract", "label": "Abstract algebra", "data": {"summary": "algebra group"}, "children": []},
                ],
            }],
        },
        "textbooks": [{
            "textbook_id": "book-1", "filename": "book.md", "status": "ready",
            "parse_result": {"chunks": [{
                "chunk_id": "ambiguous", "chapter_title": "Algebra foundations",
                "content": "algebra concepts", "content_hash": "ambiguous-hash",
            }]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)

    assert result["mappings"] == []
    assert result["unmapped"][0]["chunk_id"] == "ambiguous"
    assert result["unmapped"][0]["mapping_method"] == "ambiguous"


def test_english_os_textbook_maps_to_chinese_leaf_topics():
    build = {
        "graph_draft": {
            "id": "root",
            "label": "操作系统",
            "children": [{
                "id": "module",
                "label": "核心机制",
                "children": [
                    {"id": "paging", "label": "分页与地址转换", "data": {"summary": "页表和地址转换"}, "children": []},
                    {"id": "scheduling", "label": "调度基本概念与评价指标", "data": {"summary": "周转时间与响应时间"}, "children": []},
                    {"id": "deadlock", "label": "死锁的处理策略", "data": {"summary": "预防、避免、检测与恢复"}, "children": []},
                ],
            }],
        },
        "online_textbooks": [{
            "textbook_id": "xv6",
            "filename": "xv6.pdf",
            "status": "ready",
            "source_url": "https://pdos.csail.mit.edu/xv6.pdf",
            "parse_result": {"chunks": [
                {"chunk_id": "c1", "chapter_title": "Page tables", "content": "Paging hardware and process address space use page tables for address translation.", "content_hash": "h1"},
                {"chunk_id": "c2", "chapter_title": "Scheduling", "content": "The scheduler controls response and turnaround through context switching.", "content_hash": "h2"},
                {"chunk_id": "c3", "chapter_title": "Deadlock handling", "content": "Deadlock prevention, avoidance, detection, and recovery.", "content_hash": "h3"},
            ]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)
    by_chunk = {item["chunk_id"]: item["knowledge_node_id"] for item in result["mappings"]}

    assert by_chunk == {"c1": "paging", "c2": "scheduling", "c3": "deadlock"}


def test_mapping_caps_redundant_chunks_per_textbook_and_leaf():
    build = {
        "graph_draft": {
            "id": "root", "label": "操作系统", "children": [{
                "id": "module", "label": "进程", "children": [{
                    "id": "process", "label": "进程概念",
                    "data": {"summary": "进程", "source_outline_refs": ["chapter-process"]},
                    "children": [],
                }],
            }],
        },
        "textbooks": [{
            "textbook_id": "book", "filename": "book.md", "status": "ready",
            "parse_result": {"chunks": [
                {"chunk_id": f"chunk-{index}", "chapter_id": "chapter-process",
                 "chapter_title": "进程", "content": "进程机制 " * (index + 1),
                 "content_hash": f"hash-{index}"}
                for index in range(15)
            ]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)

    assert len(result["mappings"]) == 4
    assert result["metrics"]["pruned_redundant_mapping_count"] == 11


def test_english_os_textbook_maps_real_teacher_leaf_wording():
    labels_and_chunks = [
        ("proc", "进程控制块与上下文切换", "Process control block and context switching", "The PCB saves process state during each context switch."),
        ("ipc", "管道与共享内存通信", "Interprocess communication", "Pipes and shared memory are IPC mechanisms between processes."),
        ("schedule", "常见 CPU 调度算法与等待时间计算", "Scheduling policies", "FCFS, SJF, and round robin affect turnaround and response."),
        ("calculation", "调度算法等待时间计算实例", "Scheduling example", "A workload example calculates waiting time and turnaround time."),
        ("deadlock", "死锁预防、避免与检测", "Deadlock handling", "Deadlock prevention, avoidance, detection, and recovery."),
    ]
    build = {
        "graph_draft": {
            "id": "root", "label": "操作系统", "children": [{
                "id": "module", "label": "核心机制", "children": [
                    {"id": topic_id, "label": label, "data": {"summary": label}, "children": []}
                    for topic_id, label, _chapter, _content in labels_and_chunks
                ],
            }],
        },
        "online_textbooks": [{
            "textbook_id": "ostep", "filename": "ostep.pdf", "status": "ready",
            "source_url": "https://pages.cs.wisc.edu/~remzi/OSTEP/",
            "parse_result": {"chunks": [
                {"chunk_id": topic_id, "chapter_title": chapter, "content": content,
                 "content_hash": f"hash-{topic_id}"}
                for topic_id, _label, chapter, content in labels_and_chunks
            ]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)
    mapped_pairs = {
        (item["chunk_id"], item["knowledge_node_id"])
        for item in result["mappings"]
    }

    assert {
        (topic_id, topic_id) for topic_id, *_rest in labels_and_chunks
    } <= mapped_pairs


def test_one_authoritative_scheduling_section_can_support_adjacent_explicit_leaves():
    build = {
        "graph_draft": {
            "id": "root", "label": "操作系统", "children": [{
                "id": "module", "label": "处理器调度", "children": [
                    {"id": "criteria", "label": "常见 CPU 调度算法与等待时间计算",
                     "data": {"summary": "FCFS、SJF、时间片与评价指标"}, "children": []},
                    {"id": "case", "label": "调度算法等待时间计算实例",
                     "data": {"summary": "给定进程到达和运行时间进行计算"}, "children": []},
                ],
            }],
        },
        "online_textbooks": [{
            "textbook_id": "ostep", "filename": "ostep-scheduling.pdf",
            "status": "ready", "source_url": "https://pages.cs.wisc.edu/~remzi/OSTEP/",
            "parse_result": {"chunks": [{
                "chunk_id": "scheduling-section", "chapter_title": "Scheduling policies",
                "content": (
                    "FCFS, SJF, and round robin scheduling are compared with a workload. "
                    "The example calculates waiting time, turnaround time, and response time."
                ),
                "content_hash": "schedule-hash",
            }]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)
    mapped_leaf_ids = {
        item["knowledge_node_id"]
        for item in result["mappings"]
        if item["chunk_id"] == "scheduling-section"
    }

    assert mapped_leaf_ids == {"criteria", "case"}
    assert all(
        item["mapping_method"] == "cross_language_semantic"
        for item in result["mappings"]
    )


def test_parent_process_word_in_objective_does_not_map_process_book_to_cgroups():
    build = {
        "graph_draft": {
            "id": "root", "label": "操作系统", "children": [{
                "id": "process-module", "label": "进程与线程", "children": [{
                    "id": "cgroups", "label": "Linux cgroups 与容器资源隔离",
                    "data": {
                        "summary": "在进程与线程模块新增容器资源限制机制",
                        "type": "knowledge_point",
                    },
                    "children": [],
                }],
            }],
        },
        "selected_topic_ids": ["cgroups"],
        "online_textbooks": [{
            "textbook_id": "ostep", "filename": "ostep-process.pdf", "status": "ready",
            "source_url": "https://pages.cs.wisc.edu/~remzi/OSTEP/",
            "parse_result": {"chunks": [{
                "chunk_id": "process", "chapter_title": "Process abstraction",
                "content": "A process has state and a process control block for context switching.",
                "content_hash": "process-only",
            }]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)

    assert result["mappings"] == []
    assert result["unmapped"][0]["chunk_id"] == "process"


def test_os_aliases_cover_common_generated_leaf_title_variants():
    variants = [
        ("fcfs", "FCFS 与 SJF 调度算法", "Scheduling", "FCFS and SJF scheduling compare turnaround and response."),
        ("criteria", "CPU 调度准则与指标", "Scheduling metrics", "Scheduling uses turnaround and response metrics."),
        ("producer", "生产者消费者问题", "Bounded buffer", "The producer consumer problem uses synchronization."),
    ]
    build = {
        "graph_draft": {
            "id": "root", "label": "操作系统", "children": [{
                "id": "module", "label": "核心机制", "children": [
                    {"id": topic_id, "label": label,
                     "data": {"summary": label, "type": "knowledge_point"}, "children": []}
                    for topic_id, label, _chapter, _content in variants
                ],
            }],
        },
        "online_textbooks": [{
            "textbook_id": "ostep", "filename": "ostep.pdf", "status": "ready",
            "source_url": "https://pages.cs.wisc.edu/~remzi/OSTEP/",
            "parse_result": {"chunks": [
                {"chunk_id": topic_id, "chapter_title": chapter, "content": content,
                 "content_hash": f"hash-{topic_id}"}
                for topic_id, _label, chapter, content in variants
            ]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)
    mapped_pairs = {
        (item["chunk_id"], item["knowledge_node_id"])
        for item in result["mappings"]
    }

    assert {(topic_id, topic_id) for topic_id, *_rest in variants} <= mapped_pairs
