from __future__ import annotations

from pathlib import Path


def test_application_does_not_register_legacy_teaching_video_routes():
    from app.bootstrap import create_app

    paths = {route.path for route in create_app().routes if hasattr(route, "path")}

    assert not any("/teaching-videos" in path for path in paths)
    assert not any("/lecture-sessions" in path for path in paths)


def test_bootstrap_has_no_ai_lecturer_process_lifecycle():
    from app import bootstrap

    assert not hasattr(bootstrap, "get_ai_lecturer_process_manager")
    assert not hasattr(bootstrap, "_startup_ai_lecturer_bridge")
    assert not hasattr(bootstrap, "_shutdown_ai_lecturer_bridge")


def test_application_does_not_register_legacy_direct_ppt_routes():
    from app.bootstrap import create_app

    paths = {route.path for route in create_app().routes if hasattr(route, "path")}

    assert "/api/chat/v2/ppt/outline" not in paths
    assert "/api/chat/v2/ppt/generate" not in paths


def test_backend_source_has_no_html2ppt_runtime_reference():
    app_root = Path(__file__).resolve().parents[2] / "app"
    matches = []

    for path in app_root.rglob("*.py"):
        if "html2ppt" in path.read_text(encoding="utf-8", errors="ignore").lower():
            matches.append(path.relative_to(app_root).as_posix())

    assert matches == []
