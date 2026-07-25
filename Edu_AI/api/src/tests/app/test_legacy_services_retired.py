from __future__ import annotations


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

