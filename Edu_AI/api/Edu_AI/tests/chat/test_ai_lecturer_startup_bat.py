from pathlib import Path


def test_ai_lecturer_startup_bat_exists_and_uses_local_venv():
    script = Path(r"d:\Edu_AI_1\Edu_AI\api\Edu_AI\AI_Lecturer\start_unified.bat")

    assert script.exists()

    content = script.read_text(encoding="utf-8")

    assert r"..\.venv_local\Scripts\python.exe" in content
    assert r"..\.venv\Scripts\python.exe" in content
    assert "start_unified.py" in content
