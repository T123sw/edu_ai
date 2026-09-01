import pytest
from pydantic import ValidationError

from app.chat.api.schemas_v2 import (
    DirectQuizConfigV2,
    KnowledgeBaseDirectGameRequestV2,
)


def test_quiz_audience_and_independent_switches_are_preserved():
    config = DirectQuizConfigV2(
        topic="力学",
        audience="本科一年级",
        include_answers=True,
        include_explanations=False,
    )

    assert config.audience == "本科一年级"
    assert config.include_answers is True
    assert config.include_explanations is False


def test_game_schema_preserves_visible_settings_and_bounds_count():
    payload = KnowledgeBaseDirectGameRequestV2(
        source_mode="none",
        game_type="memory_flip",
        topic="概念配对",
        card_count=12,
        difficulty="hard",
        duration_minutes=8,
    )

    assert payload.model_dump()["card_count"] == 12
    assert payload.model_dump()["duration_minutes"] == 8
    with pytest.raises(ValidationError):
        KnowledgeBaseDirectGameRequestV2(
            source_mode="none",
            game_type="memory_flip",
            card_count=31,
        )
