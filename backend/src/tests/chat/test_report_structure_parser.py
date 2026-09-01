from app.chat.orchestrator.report_structure_parser import parse_report_nodes


def test_parse_markdown_report_nodes():
    content = """# 李白性格分析

## 摘要
这是摘要。

## 第二部分
这是第二部分。

## 结论
这是结论。
"""

    nodes = parse_report_nodes(
        artifact_id="report-1",
        version_id="v1",
        artifact_type="report",
        content=content,
    )

    assert [node["node_type"] for node in nodes] == ["summary", "section", "conclusion"]
    assert nodes[0]["title"] == "摘要"
    assert nodes[1]["title"] == "第二部分"
    assert nodes[2]["title"] == "结论"


def test_parse_outline_nodes_from_outline_payload():
    outline = [
        {
            "chapter_id": 1,
            "chapter_title": "问题界定",
            "sections": [{"section_id": "1.1", "title": "课堂纪律现状"}],
        },
        {
            "chapter_id": 2,
            "chapter_title": "成因分析",
            "sections": [{"section_id": "2.1", "title": "互动不足"}],
        },
    ]

    nodes = parse_report_nodes(
        artifact_id="outline-1",
        version_id="v1",
        artifact_type="report_outline",
        content=outline,
    )

    assert [node["title"] for node in nodes] == ["问题界定", "成因分析"]
    assert [node["order_index"] for node in nodes] == [1, 2]
