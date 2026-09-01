from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse


AUTHORITY_RANK = {
    "reviewed_open_textbook": 5,
    "reviewed_curriculum_source": 5,
    "reviewed_supplementary_source": 4,
    "reviewed_authored_material": 3,
}


def _score(material: dict) -> tuple[int, int, int, str]:
    language = str(material.get("language") or "").lower()
    return (
        1 if language.startswith("zh") else 0,
        AUTHORITY_RANK.get(str(material.get("authority_tier") or ""), 1),
        1 if material.get("source_url") else 0,
        str(material.get("title") or ""),
    )


def _source_identity(material: dict) -> str:
    host = urlparse(str(material.get("source_url") or "")).netloc.casefold()
    return host or str(material.get("source_group") or "")


def _select(materials: list[dict]) -> list[dict]:
    ranked = sorted(materials, key=_score, reverse=True)
    selected: list[dict] = []

    def add(predicate) -> None:
        for material in ranked:
            if len(selected) >= 3:
                return
            if material in selected or not predicate(material):
                continue
            selected.append(material)

    # First guarantee two Chinese documents, preferring source diversity.
    add(
        lambda item: str(item.get("language") or "").lower().startswith("zh")
        and _source_identity(item)
        not in {_source_identity(value) for value in selected}
    )
    add(lambda item: str(item.get("language") or "").lower().startswith("zh"))
    # Then prefer a third independent source; English is allowed as supplement.
    add(
        lambda item: _source_identity(item)
        not in {_source_identity(value) for value in selected}
    )
    add(lambda _item: True)
    return selected[:3]


def main() -> int:
    parser = argparse.ArgumentParser(description="Select the reviewed v2 course corpus from the shadow audit")
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("scripts/fixtures/course_corpus_20260808/2026-08-08-shadow-corpus-audit.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/shadow/computational-thinking-v2/selected-manifest.json"),
    )
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    by_node: dict[str, list[dict]] = defaultdict(list)
    for material in audit.get("accepted_materials") or []:
        by_node[str(material.get("scope_id") or "")].append(material)

    selected: list[dict] = []
    failures: list[dict] = []
    for node_id, materials in sorted(by_node.items()):
        chosen = _select(materials)
        chinese = sum(
            1 for item in chosen if str(item.get("language") or "").lower().startswith("zh")
        )
        if len(chosen) < 3 or chinese < 2:
            failures.append(
                {
                    "scope_id": node_id,
                    "selected_count": len(chosen),
                    "chinese_count": chinese,
                }
            )
        selected.extend(chosen)

    payload = {
        "builder": "shadow-reviewed-selection-v1",
        "status": "ready" if not failures and len(by_node) == 49 else "incomplete",
        "node_count": len(by_node),
        "document_count": len(selected),
        "failures": failures,
        "documents": selected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**payload, "documents": "omitted"}, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
