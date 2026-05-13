from pathlib import Path


def test_start_api_bat_uses_start_workdir_for_html2ppt():
    script = Path(r"d:\Edu_AI_1\Edu_AI\api\Edu_AI\start_api.bat").read_text(
        encoding="utf-8"
    )

    assert 'start "html2ppt-service" /D "%PPT_DIR%" cmd /k npm start' in script
    assert r'cmd /k "cd /d \"%PPT_DIR%\" && npm start"' not in script


def test_start_api_bat_checks_fallback_local_venv():
    script = Path(r"d:\Edu_AI_1\Edu_AI\api\Edu_AI\start_api.bat").read_text(
        encoding="utf-8"
    )

    assert ".venv_local\\Scripts\\python.exe" in script


def test_start_api_bat_validates_pip_before_selecting_venv():
    script = Path(r"d:\Edu_AI_1\Edu_AI\api\Edu_AI\start_api.bat").read_text(
        encoding="utf-8"
    )

    assert "import pip" in script
