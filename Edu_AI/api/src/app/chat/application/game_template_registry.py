from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GameTemplateSpec:
    game_type: str
    template_id: str
    display_name: str
    html_template_path: Path
    schema_path: Path


_BASE_DIR = Path(__file__).resolve().parents[3] / "dynamic-templates" / "games"

_GAME_TEMPLATES: dict[str, GameTemplateSpec] = {
    "category_sort": GameTemplateSpec(
        game_type="category_sort",
        template_id="category-sort",
        display_name="分类归纳",
        html_template_path=_BASE_DIR / "category-sort.html",
        schema_path=_BASE_DIR / "category-sort.schema.json",
    ),
    "drag_match": GameTemplateSpec(
        game_type="drag_match",
        template_id="drag-match",
        display_name="拖拽配对",
        html_template_path=_BASE_DIR / "drag-match.html",
        schema_path=_BASE_DIR / "drag-match.schema.json",
    ),
    "memory_flip": GameTemplateSpec(
        game_type="memory_flip",
        template_id="memory-flip",
        display_name="翻牌记忆",
        html_template_path=_BASE_DIR / "memory-flip.html",
        schema_path=_BASE_DIR / "memory-flip.schema.json",
    ),
}


def get_game_template_spec(game_type: str) -> GameTemplateSpec:
    try:
        return _GAME_TEMPLATES[str(game_type or "").strip()]
    except KeyError as exc:
        raise ValueError("unsupported_game_type") from exc
