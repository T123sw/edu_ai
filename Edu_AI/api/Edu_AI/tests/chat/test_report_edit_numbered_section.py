from app.chat.orchestrator.report_edit_intent_parser import parse_report_edit_intent
from app.chat.workflows.report.edit_runtime import ReportEditRuntime


NESTED_REPORT_MD = """# 变量本质、动态特性及其教学价值分析报告

## 1. 引言
引言内容。

## 5. 变量作为程序记忆信息核心工具的教学价值
总述内容。

### 5.1 现实问题建模的工具
5.1 内容。

### 5.2 代码可读性与意图表达
5.2 内容。

### 5.3 后续知识的基石
5.3 内容。

### 5.4 教学策略建议
5.4 内容。

## 6. 结语
结语内容。
"""


def test_parse_edit_intent_targets_decimal_section_number_for_delete():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="删除5.4 教学策略建议",
        structure_nodes=[
            {"node_id": "section-1", "node_type": "section", "title": "1. 引言", "order_index": 1},
            {"node_id": "section-5", "node_type": "section", "title": "5. 变量作为程序记忆信息核心工具的教学价值", "order_index": 5},
            {"node_id": "section-54", "node_type": "section", "title": "5.4 教学策略建议", "order_index": 9},
        ],
    )

    assert request["target_type"] == "report"
    assert request["action_type"] == "delete"
    assert request["target_node_id"] == "section-54"


def test_report_edit_runtime_deletes_targeted_decimal_subsection():
    runtime = ReportEditRuntime(llm=None)
    result = runtime.run(
        question="删除5.4 教学策略建议",
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        source_artifact={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "变量本质、动态特性及其教学价值分析报告.md",
            "content": NESTED_REPORT_MD,
        },
    )

    report_artifact = next(artifact for artifact in result["artifacts"] if artifact["artifact_type"] == "report")
    assert "### 5.4 教学策略建议" not in report_artifact["content"]
    assert "### 5.3 后续知识的基石" in report_artifact["content"]
    assert "## 6. 结语" in report_artifact["content"]
