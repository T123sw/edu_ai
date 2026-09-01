from scripts.migrate_conversation_source_chunks import migrate_payload


def test_migrate_payload_replaces_parent_context_with_exact_child_chunk() -> None:
    payload = {
        "conversations": [
            {
                "messages": [
                    {
                        "sources": [
                            {
                                "chunk_id": "chunk-1",
                                "content": "同一个扩展后的父章节",
                            }
                        ]
                    }
                ]
            }
        ]
    }
    records = {
        "chunk-1": {
            "content": "【章节上下文】: 链表 > 初始化\n\n```java\nnode.next = head;\n```",
            "metadata": {"source_start_line": 20, "source_end_line": 23},
        }
    }

    changed = migrate_payload(payload, records)

    source = payload["conversations"][0]["messages"][0]["sources"][0]
    assert changed == 1
    assert source["content"] == "```java\nnode.next = head;\n```"
    assert source["source_start_line"] == 20
    assert source["source_end_line"] == 23
