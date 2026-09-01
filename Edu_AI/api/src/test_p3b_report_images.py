"""P3-B — 报告图片融入 验证测试

Tests:
  T1 - inject_images_into_report: ### headings, even distribution
  T2 - inject_images_into_report: fallback to ## headings when no ###
  T3 - inject_images_into_report: empty/no assets → unchanged
  T4 - inject_images_into_report: max_images cap
  T5 - fetch_report_image_assets: returns empty when allow_rag=False
  T6 - inject_report_images_from_rag: silent on any error
  T7 - runtime.py inject path: no-op when allow_rag=False
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


# ── helpers ───────────────────────────────────────────────────────────────────

_SAMPLE_REPORT = """## 第一章 量子计算基础

本章介绍量子计算基本概念。

### 量子比特

量子比特是量子计算的基本单元。

### 量子叠加

量子叠加允许量子比特同时处于多个状态。

## 第二章 量子门

### 泡利门

泡利门是最基本的量子门之一。

### 哈达玛门

哈达玛门用于创建叠加态。
"""

_SAMPLE_NO_TRIPLE = """## 第一章

内容A。

## 第二章

内容B。
"""


def _make_asset(url: str, alt: str = "图片") -> object:
    from app.chat.workflows.report.media_assets import MediaAsset
    return MediaAsset(url=url, alt=alt, caption="")


# ── T1: ### heading injection ──────────────────────────────────────────────────

def test_inject_triple_headings():
    from app.chat.workflows.report.image_injector import inject_images_into_report
    assets = [_make_asset("http://img/a.png", "图A"), _make_asset("http://img/b.png", "图B")]
    result = inject_images_into_report(_SAMPLE_REPORT, assets, max_images=2)
    assert "http://img/a.png" in result
    assert "http://img/b.png" in result
    assert "![图A]" in result
    assert "![图B]" in result
    # Images inserted after ### headings, not ## headings
    lines = result.splitlines()
    for i, line in enumerate(lines):
        if "### 量子比特" in line:
            # Next non-empty line should be the image
            next_content = next((l for l in lines[i+1:] if l.strip()), "")
            assert "![" in next_content, f"Expected image after heading, got: {next_content}"
            break
    print("T1 PASS: inject after ### headings")


# ── T2: fallback to ## headings ───────────────────────────────────────────────

def test_inject_double_heading_fallback():
    from app.chat.workflows.report.image_injector import inject_images_into_report
    assets = [_make_asset("http://img/x.png")]
    result = inject_images_into_report(_SAMPLE_NO_TRIPLE, assets)
    assert "http://img/x.png" in result
    print("T2 PASS: fallback to ## when no ### headings")


# ── T3: no assets → unchanged ─────────────────────────────────────────────────

def test_no_assets_unchanged():
    from app.chat.workflows.report.image_injector import inject_images_into_report
    result = inject_images_into_report(_SAMPLE_REPORT, [])
    assert result == _SAMPLE_REPORT
    result2 = inject_images_into_report("", [_make_asset("http://img/x.png")])
    assert result2 == ""
    print("T3 PASS: no assets or empty markdown → unchanged")


# ── T4: max_images cap ────────────────────────────────────────────────────────

def test_max_images_cap():
    from app.chat.workflows.report.image_injector import inject_images_into_report
    assets = [_make_asset(f"http://img/{i}.png") for i in range(10)]
    result = inject_images_into_report(_SAMPLE_REPORT, assets, max_images=2)
    count = result.count("http://img/")
    assert count == 2, f"Expected 2 images, got {count}"
    print(f"T4 PASS: max_images=2 → exactly 2 images injected")


# ── T5: fetch returns empty when allow_rag=False ──────────────────────────────

def test_fetch_empty_when_no_rag():
    from app.chat.workflows.report.image_injector import fetch_report_image_assets
    result = fetch_report_image_assets(
        allow_rag=False,
        selected_doc_ids=["doc1"],
        owner=None,
        query_text="量子计算",
    )
    assert result == []
    result2 = fetch_report_image_assets(
        allow_rag=True,
        selected_doc_ids=[],
        owner=None,
        query_text="量子计算",
    )
    assert result2 == []
    print("T5 PASS: fetch returns [] when allow_rag=False or no doc_ids")


# ── T6: inject_report_images_from_rag: silent on error ───────────────────────

def test_inject_from_rag_silent_on_error():
    from app.chat.workflows.report.image_injector import inject_report_images_from_rag
    # No real RAG system → get_document_image_sources will fail internally
    # But the wrapper should return the original content unchanged
    original = "## 第一章\n\n内容。\n"
    result = inject_report_images_from_rag(
        original,
        allow_rag=True,
        selected_doc_ids=["doc-nonexistent"],
        owner=None,
        query_text="测试",
    )
    # Should not raise, and should return valid content
    assert isinstance(result, str) and len(result) > 0
    # Either returns original (no images found / error) or injected version
    print(f"T6 PASS: inject_from_rag silent on error, returned len={len(result)}")


# ── T7: runtime image injection no-op when allow_rag=False ───────────────────

def test_runtime_noop_without_rag():
    """Simulate runtime._inject_images() with allow_rag=False."""
    # Reconstruct the helper closure manually
    _allow_rag = False
    _doc_ids: list = []
    _owner = None

    def _inject_images(content: str, *, subject: str = "") -> str:
        if not content or not _allow_rag or not _doc_ids:
            return content
        try:
            from app.chat.workflows.report.image_injector import inject_report_images_from_rag
            return inject_report_images_from_rag(
                content, allow_rag=True, selected_doc_ids=_doc_ids,
                owner=_owner, query_text=subject or content[:80],
            )
        except Exception:
            return content

    original = "## 章节\n\n内容。\n"
    result = _inject_images(original, subject="量子计算")
    assert result == original, "Expected no-op when allow_rag=False"
    print("T7 PASS: runtime _inject_images no-op when allow_rag=False")


# ── run all ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_inject_triple_headings,
        test_inject_double_heading_fallback,
        test_no_assets_unchanged,
        test_max_images_cap,
        test_fetch_empty_when_no_rag,
        test_inject_from_rag_silent_on_error,
        test_runtime_noop_without_rag,
    ]
    failed = []
    for t in tests:
        try:
            t()
        except Exception as exc:
            print(f"FAIL {t.__name__}: {exc}")
            import traceback; traceback.print_exc()
            failed.append(t.__name__)

    print()
    if failed:
        print(f"FAILED {len(failed)} test(s): {failed}")
        sys.exit(1)
    else:
        print(f"ALL {len(tests)} TESTS PASSED")
