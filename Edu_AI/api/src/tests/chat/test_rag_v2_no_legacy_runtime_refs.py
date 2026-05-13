from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[2]


def test_backend_runtime_code_has_no_new_rag_references():
    runtime_files = [
        *list((API_ROOT / "app").rglob("*.py")),
        *list((API_ROOT / "rag_v2").glob("*.py")),
        *list((API_ROOT / "rag_v2" / "rag_main").rglob("*.py")),
    ]

    offenders = [
        str(path.relative_to(API_ROOT))
        for path in runtime_files
        if "new_rag" in path.read_text(encoding="utf-8", errors="ignore")
    ]

    assert offenders == []
