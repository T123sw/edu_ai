import pytest

from app.services.visual_assets.models import VisualBrief
from app.services.visual_assets.planner import parse_visual_brief


def test_visual_brief_parser_assigns_stable_slots_and_preserves_outline():
    brief = parse_visual_brief(
        """
        {
          "outline": [
            {"section_id": "concept", "title": "核心概念"},
            {"section_id": "implementation", "title": "实现方式"}
          ],
          "visuals": [
            {
              "section_id": "implementation",
              "purpose": "解释链表节点和 next 指针关系",
              "query": "linked list node next pointer diagram",
              "preferred_kind": "diagram",
              "required": false,
              "caption_hint": "链表节点连接关系"
            }
          ]
        }
        """,
        resource_type="report",
        topic="链表如何实现",
    )

    assert isinstance(brief, VisualBrief)
    assert [section.section_id for section in brief.outline] == [
        "concept",
        "implementation",
    ]
    assert brief.slots[0].slot_id == "implementation-visual-1"
    assert brief.slots[0].query == "linked list node next pointer diagram"


def test_visual_brief_parser_rejects_duplicate_explicit_slot_ids():
    with pytest.raises(ValueError, match="duplicate visual slot"):
        parse_visual_brief(
            """
            {
              "outline": [{"section_id": "one", "title": "第一节"}],
              "visuals": [
                {"slot_id": "same", "section_id": "one", "purpose": "a", "query": "a"},
                {"slot_id": "same", "section_id": "one", "purpose": "b", "query": "b"}
              ]
            }
            """,
            resource_type="report",
            topic="测试",
        )


def test_visual_brief_parser_limits_slots_by_resource_policy():
    payload = {
        "outline": [{"section_id": "one", "title": "第一节"}],
        "visuals": [
            {
                "section_id": "one",
                "purpose": f"purpose-{index}",
                "query": f"query-{index}",
            }
            for index in range(10)
        ],
    }

    brief = parse_visual_brief(
        payload,
        resource_type="report",
        topic="测试",
    )

    assert len(brief.slots) == 4
