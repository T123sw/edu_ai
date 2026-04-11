from pathlib import Path


def test_start_api_bat_uses_start_workdir_for_html2ppt():
    script = Path(r"d:\Edu_AI_1\Edu_AI\api\Edu_AI\start_api.bat").read_text(
        encoding="utf-8"
    )

    assert 'start "html2ppt-service" /D "%PPT_DIR%" cmd /k npm start' in script
    assert r'cmd /k "cd /d \"%PPT_DIR%\" && npm start"' not in script
