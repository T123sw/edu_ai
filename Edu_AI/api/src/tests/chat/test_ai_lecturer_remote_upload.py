from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


def _load_unified_gateway():
    src_dir = Path(__file__).resolve().parents[2]
    module_dir = src_dir / "modules" / "AI_Lecturer"
    for path in (src_dir, module_dir):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)
    from modules.AI_Lecturer import unified_gateway

    return unified_gateway


def test_offline_upload_endpoint_accepts_slide_files(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_LECTURER_OFFLINE_ENABLED", "1")
    unified_gateway = _load_unified_gateway()

    calls = []

    def fake_build_course_video(course_title, pages_data, final_output_filename):
        calls.append(
            {
                "course_title": course_title,
                "pages_data": pages_data,
                "final_output_filename": final_output_filename,
            }
        )
        Path(final_output_filename).write_bytes(b"fake mp4")

    monkeypatch.setattr(unified_gateway, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(unified_gateway, "build_course_video", fake_build_course_video)
    unified_gateway.OFFLINE_TASK_DB.clear()

    client = TestClient(unified_gateway.app)
    response = client.post(
        "/api/v1/offline/generate_full_video_upload",
        data={
            "metadata": (
                '{"course_title":"remote course","pages":['
                '{"filename":"slide-001.png","content_text":"page one"},'
                '{"filename":"slide-002.png","content_text":"page two"}'
                "]}"
            )
        },
        files=[
            ("files", ("slide-001.png", b"png-1", "image/png")),
            ("files", ("slide-002.png", b"png-2", "image/png")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    task_id = payload["task_id"]
    assert task_id.startswith("course_")
    assert unified_gateway.OFFLINE_TASK_DB[task_id]["status"] == "success"
    assert calls[0]["course_title"] == "remote course"
    assert len(calls[0]["pages_data"]) == 2
    assert calls[0]["pages_data"][0]["outline_prompt"] == "page one"
    assert Path(calls[0]["pages_data"][0]["ppt_image"]).name == "slide-001.png"
    assert str(tmp_path) in calls[0]["pages_data"][0]["ppt_image"]
