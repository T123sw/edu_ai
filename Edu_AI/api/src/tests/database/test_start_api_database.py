from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


API_ROOT = Path(__file__).resolve().parents[2]


def test_startup_check_rejects_missing_postgres_environment_file(tmp_path: Path):
    environment = os.environ.copy()
    environment["EDU_AI_POSTGRES_ENV_FILE"] = str(
        tmp_path / "missing.env.postgres"
    )

    result = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/v:on",
            "/c",
            "call start_api.bat --check & exit /b !errorlevel!",
        ],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "PostgreSQL environment file not found" in result.stdout


def test_startup_check_rejects_database_environment_without_connection_url(
    tmp_path: Path,
):
    postgres_environment = tmp_path / ".env.postgres"
    postgres_environment.write_text(
        "POSTGRES_DB=edu_ai\n"
        "POSTGRES_USER=edu_ai\n"
        "POSTGRES_PASSWORD=local-test-password\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["EDU_AI_POSTGRES_ENV_FILE"] = str(postgres_environment)

    result = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/v:on",
            "/c",
            "call start_api.bat --check & exit /b !errorlevel!",
        ],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "DATABASE_URL is missing" in result.stdout


def test_startup_check_rejects_invalid_postgres_compose_configuration(
    tmp_path: Path,
):
    postgres_environment = tmp_path / ".env.postgres"
    postgres_environment.write_text(
        "POSTGRES_DB=edu_ai\n"
        "POSTGRES_USER=edu_ai\n"
        "POSTGRES_PASSWORD=local-test-password\n"
        "DATABASE_URL=postgresql+psycopg://edu_ai:local-test-password@127.0.0.1:5432/edu_ai\n",
        encoding="utf-8",
    )
    invalid_compose = tmp_path / "compose.yml"
    invalid_compose.write_text("this is not a compose file\n", encoding="utf-8")
    environment = os.environ.copy()
    environment["EDU_AI_POSTGRES_ENV_FILE"] = str(postgres_environment)
    environment["EDU_AI_POSTGRES_COMPOSE_FILE"] = str(invalid_compose)

    result = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/v:on",
            "/c",
            "call start_api.bat --check & exit /b !errorlevel!",
        ],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "PostgreSQL Compose configuration is invalid" in result.stdout


def test_database_only_start_recovers_stopped_container_without_wait_errors():
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not installed")
    if not (API_ROOT.parents[2] / "infra" / "postgres" / ".env.postgres").exists():
        pytest.skip("Local PostgreSQL environment file is not configured")
    docker_ready = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        timeout=15,
        check=False,
    )
    if docker_ready.returncode != 0:
        pytest.skip("Docker engine is not running")
    container_exists = subprocess.run(
        ["docker", "inspect", "edu-ai-postgres"],
        capture_output=True,
        timeout=15,
        check=False,
    )
    if container_exists.returncode != 0:
        pytest.skip("Edu AI PostgreSQL container has not been created")

    subprocess.run(
        ["docker", "stop", "edu-ai-postgres"],
        capture_output=True,
        timeout=30,
        check=True,
    )
    try:
        result = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/v:on",
                "/c",
                "call start_api.bat --database-only & exit /b !errorlevel!",
            ],
            cwd=API_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    finally:
        subprocess.run(
            ["docker", "start", "edu-ai-postgres"],
            capture_output=True,
            timeout=30,
            check=False,
        )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output
    assert "Input redirection is not supported" not in combined_output
    assert (
        "Core persistence modes: user=postgres course=postgres membership=postgres"
        in combined_output
    )
    assert "Conversation persistence mode: postgres" in combined_output
