from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT.parent
SERVICE_FILE = ROOT / "app" / "chat" / "service.py"
SKILL_FILE = BACKEND_ROOT / "skills" / "edu-report-agent" / "SKILL.md"

# 来自“报告生成_prompt总表.md”的目标 section 清单（报告主链路）
EXPECTED_SECTIONS = [
    "REPORT_SLOT_SCHEMA",
    "EXTRACTOR_SYSTEM_PROMPT",
    "REPORT_HARD_ASK_PROMPT",
    "REPORT_SOFT_CONFIRM_PROMPT",
    "REPORT_OUTLINE_AST_PROMPT",
    "OUTLINE_PATCH_PROMPT",
    "OUTLINE_MODIFY_FEEDBACK_TEMPLATE",
    "REPORT_CHAPTER_GENERATE_PROMPT",
    "REPORT_STITCH_SUMMARY_PROMPT",
]


def parse_skill_sections(skill_text: str) -> set[str]:
    return set(re.findall(r"^###\s+([A-Za-z0-9_\-]+)\s*$", skill_text, flags=re.MULTILINE))


def parse_service_references(service_text: str) -> dict[str, set[str]]:
    load_refs = set(
        re.findall(
            r'_load_prompt_from_skill\(\s*"edu-report-agent"\s*,\s*"([A-Za-z0-9_\-]+)"',
            service_text,
        )
    )
    extract_refs = set(
        re.findall(
            r'extract_section\(\s*"edu-report-agent"\s*,\s*"([A-Za-z0-9_\-]+)"',
            service_text,
        )
    )
    return {"load": load_refs, "extract": extract_refs, "all": load_refs | extract_refs}


def main() -> int:
    if not SERVICE_FILE.exists():
        print(f"[ERROR] service.py not found: {SERVICE_FILE}")
        return 2
    if not SKILL_FILE.exists():
        print(f"[ERROR] SKILL.md not found: {SKILL_FILE}")
        return 2

    service_text = SERVICE_FILE.read_text(encoding="utf-8")
    skill_text = SKILL_FILE.read_text(encoding="utf-8")

    skill_sections = parse_skill_sections(skill_text)
    refs = parse_service_references(service_text)

    expected_missing_in_skill = [s for s in EXPECTED_SECTIONS if s not in skill_sections]
    expected_missing_in_code = [s for s in EXPECTED_SECTIONS if s not in refs["all"]]

    code_ref_but_not_in_skill = sorted([s for s in refs["all"] if s not in skill_sections])
    in_skill_but_unwired_expected = sorted([s for s in EXPECTED_SECTIONS if s in skill_sections and s not in refs["all"]])

    print("=== Report Skill Wiring Check ===")
    print(f"service: {SERVICE_FILE}")
    print(f"skill:   {SKILL_FILE}")
    print("")

    print("[1] Expected sections")
    for s in EXPECTED_SECTIONS:
        status = "OK"
        if s in expected_missing_in_skill:
            status = "MISSING_IN_SKILL"
        elif s in expected_missing_in_code:
            status = "UNWIRED_IN_CODE"
        print(f" - {s}: {status}")

    print("\n[2] Code references")
    print(f" - _load_prompt_from_skill refs: {sorted(refs['load'])}")
    print(f" - extract_section refs:         {sorted(refs['extract'])}")

    print("\n[3] Diagnostics")
    print(f" - expected missing in skill: {expected_missing_in_skill}")
    print(f" - expected missing in code:  {expected_missing_in_code}")
    print(f" - code refs not in skill:    {code_ref_but_not_in_skill}")
    print(f" - expected in skill but unwired: {in_skill_but_unwired_expected}")

    hard_fail = bool(expected_missing_in_skill or expected_missing_in_code or code_ref_but_not_in_skill)
    if hard_fail:
        print("\nRESULT: FAIL")
        return 1

    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
