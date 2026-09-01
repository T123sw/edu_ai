from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from app.services.knowledge_ingestion.structural_chunker import (
    ApproximateTokenCounter,
    StructuralChunker,
)
from modules.rag_v2.rag_main import system as runtime_system


def _chunker(*, target: int = 80, maximum: int = 120) -> StructuralChunker:
    return StructuralChunker(
        child_target_tokens=target,
        child_max_tokens=maximum,
        parent_target_tokens=maximum * 3,
        parent_max_tokens=maximum * 4,
        minimum_child_tokens=12,
    )


def test_short_code_formula_and_callout_are_never_split_internally() -> None:
    markdown = """# 算法分析

## 示例程序

下面的程序计算前 n 项之和。

```python
def total(n: int) -> int:
    result = 0
    for value in range(1, n + 1):
        result += value
    return result
```

其时间复杂度满足：

$$
T(n) = \sum_{i=1}^{n} 1 = n
$$

!!! tip "检查"
    应同时检查正确性和输入边界。
"""

    result = _chunker(target=45, maximum=90).chunk_markdown(
        markdown,
        document_id="doc-code",
        document_title="算法分析",
    )

    assert result.children
    assert all(chunk.embedding_text.count("```") % 2 == 0 for chunk in result.children)
    assert all(chunk.embedding_text.count("$$") % 2 == 0 for chunk in result.children)
    assert any("def total" in chunk.display_content for chunk in result.children)
    assert any("检查正确性" in chunk.display_content for chunk in result.children)


def test_long_markdown_table_repeats_header_in_every_table_fragment() -> None:
    rows = "\n".join(f"| {index} | O(n^{index}) | 第 {index} 类增长 |" for index in range(1, 35))
    markdown = f"""# 复杂度

## 增长率比较

| 编号 | 复杂度 | 说明 |
| --- | --- | --- |
{rows}
"""

    result = _chunker(target=55, maximum=80).chunk_markdown(
        markdown,
        document_id="doc-table",
        document_title="复杂度",
    )
    table_chunks = [chunk for chunk in result.children if chunk.kind == "table"]

    assert len(table_chunks) >= 2
    assert all("| 编号 | 复杂度 | 说明 |" in chunk.display_content for chunk in table_chunks)
    assert all("| --- | --- | --- |" in chunk.display_content for chunk in table_chunks)


def test_single_oversized_table_row_is_bounded_and_remains_a_table() -> None:
    giant_row = " ".join(f"[概念{index}](https://example.test/{index})" for index in range(300))
    markdown = f"""# 课程

## 超长表格

| 条目 |
| --- |
| {giant_row} |
"""

    result = _chunker(target=55, maximum=80).chunk_markdown(
        markdown,
        document_id="doc-giant-table-row",
        document_title="课程",
    )
    table_chunks = [chunk for chunk in result.children if chunk.kind == "table"]

    assert len(table_chunks) > 1
    assert all("| 续表内容 |" in chunk.display_content for chunk in table_chunks)
    assert all(chunk.token_count <= 80 for chunk in table_chunks)


def test_single_oversized_code_and_formula_lines_keep_balanced_fences() -> None:
    markdown = "# 边界\n\n```text\n" + ("x" * 3000) + "\n```\n\n$$\n" + ("a+b+" * 800) + "\n$$"

    result = _chunker(target=55, maximum=80).chunk_markdown(
        markdown,
        document_id="doc-giant-special-lines",
        document_title="边界",
    )

    assert len(result.children) > 2
    assert all(chunk.token_count <= 80 for chunk in result.children)
    assert all(chunk.display_content.count("```") % 2 == 0 for chunk in result.children)
    assert all(chunk.display_content.count("$$") % 2 == 0 for chunk in result.children)


def test_tiny_peer_paragraphs_merge_without_crossing_heading_boundary() -> None:
    markdown = """# 计算思维

## 分解

识别子问题。

确定子问题边界。

组合子问题答案。

## 抽象

保留关键属性。
"""

    result = _chunker(target=60, maximum=100).chunk_markdown(
        markdown,
        document_id="doc-merge",
        document_title="计算思维",
    )

    decomposition = [chunk for chunk in result.children if chunk.heading_path[-1:] == ("分解",)]
    abstraction = [chunk for chunk in result.children if chunk.heading_path[-1:] == ("抽象",)]
    assert len(decomposition) == 1
    assert "识别子问题" in decomposition[0].display_content
    assert "组合子问题答案" in decomposition[0].display_content
    assert len(abstraction) == 1
    assert "保留关键属性" in abstraction[0].display_content
    assert "识别子问题" not in abstraction[0].display_content


def test_children_have_stable_parent_and_neighbor_links_within_hard_cap() -> None:
    markdown = "# 搜索\n\n## 顺序搜索\n\n" + "。\n\n".join(
        f"步骤 {index}：检查当前位置并记录比较结果" for index in range(1, 30)
    )
    counter = ApproximateTokenCounter()
    chunker = _chunker(target=45, maximum=65)

    first = chunker.chunk_markdown(markdown, document_id="doc-links", document_title="搜索")
    second = chunker.chunk_markdown(markdown, document_id="doc-links", document_title="搜索")

    assert [chunk.chunk_id for chunk in first.children] == [chunk.chunk_id for chunk in second.children]
    assert len(first.children) > 1
    assert all(chunk.parent_id for chunk in first.children)
    assert all(counter.count(chunk.embedding_text) <= 65 for chunk in first.children)
    for index, chunk in enumerate(first.children):
        assert chunk.previous_id == (first.children[index - 1].chunk_id if index else None)
        assert chunk.next_id == (
            first.children[index + 1].chunk_id if index + 1 < len(first.children) else None
        )


def test_embedding_client_sends_complete_input_without_silent_truncation(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    def fake_post(url, *, json, headers, timeout):
        captured["payload"] = json
        return Response()

    monkeypatch.setattr(runtime_system.requests, "post", fake_post)
    client = runtime_system.EmbeddingClient(
        api_base="https://embedding.example/v1",
        api_key="test-key",
        model="gemini-embedding-2-preview",
    )
    source = "计算思维" * 500

    client.embed_documents([source])

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["input"] == [source]


def test_document_processor_uses_structural_chunker_for_markdown_and_docx(tmp_path: Path) -> None:
    markdown_path = tmp_path / "lesson.md"
    markdown_path.write_text(
        "# 课程\n\n## 抽象\n\n抽象保留关键属性。\n\n## 分解\n\n分解建立子问题。",
        encoding="utf-8",
    )
    processor = runtime_system.DocumentProcessor(chunk_size=2000, chunk_overlap=0)

    chunks = processor.process_file(str(markdown_path), owner="alice", doc_id="doc-universal")
    text_chunks = [chunk for chunk in chunks if chunk.metadata.get("modality") == "text"]

    assert text_chunks
    assert all(chunk.metadata.get("chunker_version") == "structural-parent-child-v1" for chunk in text_chunks)
    assert all(chunk.metadata.get("parent_id") for chunk in text_chunks)
    assert {chunk.metadata.get("heading_path") for chunk in text_chunks} >= {
        "课程 > 抽象",
        "课程 > 分解",
    }


def test_legacy_doc_is_rejected_instead_of_read_as_plain_text(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.doc"
    legacy.write_bytes(b"\xd0\xcf\x11\xe0binary-word")
    processor = runtime_system.DocumentProcessor()

    with pytest.raises(ValueError, match="DOCX"):
        processor.process_file(str(legacy))


def test_docx_import_preserves_embedded_images_as_multimodal_chunks(tmp_path: Path) -> None:
    docx_path = tmp_path / "lesson.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>二叉树遍历示例</w:t></w:r></w:p></w:body>
    </w:document>"""
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/media/tree.png", png)

    processor = runtime_system.DocumentProcessor()
    chunks = processor.process_file(
        str(docx_path),
        owner="alice",
        doc_id="docx-images",
        images_root=tmp_path / "images",
    )

    image_chunks = [chunk for chunk in chunks if chunk.metadata.get("modality") == "image"]
    text_chunks = [chunk for chunk in chunks if chunk.metadata.get("modality") == "text"]
    assert len(image_chunks) == 1
    assert Path(image_chunks[0].metadata["image_path"]).is_file()
    assert text_chunks[0].metadata["linked_images"][0]["source"] == "docx"
