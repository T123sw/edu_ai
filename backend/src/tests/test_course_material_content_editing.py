import pytest

from app.api.courses import _validate_material_content


def test_text_material_editor_accepts_markdown():
    assert _validate_material_content("report", "# 更新后的报告") == {
        "content": "# 更新后的报告"
    }


def test_mind_map_editor_accepts_valid_tree_and_rejects_missing_root():
    content = {
        "root": {
            "id": "root",
            "title": "链表",
            "children": [{"id": "root-1", "title": "节点", "children": []}],
        },
        "max_depth": 3,
    }
    assert _validate_material_content("graph", content) == {"content": content}
    with pytest.raises(ValueError, match="根节点"):
        _validate_material_content("graph", {"max_depth": 3})


def test_game_editor_rejects_arbitrary_html():
    with pytest.raises(ValueError, match="HTML"):
        _validate_material_content("game", {"html": "<script>alert(1)</script>"})
