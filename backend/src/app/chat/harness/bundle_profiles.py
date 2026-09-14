from pathlib import Path


SKILL = Path(__file__).parent / "skills" / "edu-standard-resource-bundle" / "SKILL.md"


def standard_resource_bundle_contract() -> str:
    text = SKILL.read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[-1]
    return text.strip()
