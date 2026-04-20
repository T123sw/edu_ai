import importlib.util
import sys
from pathlib import Path


def _load_recording_paths_module():
    module_path = (
        Path("D:/Edu_AI_1/Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/server/recording_paths.py")
        .resolve()
    )
    if not module_path.exists():
        module_path = (
            Path(__file__).resolve().parents[2]
            / "AI_Lecturer"
            / "LiveTalking-main"
            / "server"
            / "recording_paths.py"
        )
    spec = importlib.util.spec_from_file_location("livetalking_recording_paths", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_recording_output_paths_are_session_specific_and_safe():
    module = _load_recording_paths_module()

    paths = module.recording_paths_for_session("123/../456")

    assert paths.video.name == "temp123__..__456.mp4"
    assert paths.audio.name == "temp123__..__456.aac"
    assert paths.final.name == "record_123__..__456.mp4"
    assert "recordings" in str(paths.final)
