from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent

ACTIVE_FILES = [
    ROOT / ".env.example",
    ROOT / "environment.yml",
    ROOT / "README.md",
    ROOT / "DEPENDENCIES.md",
    ROOT / "项目总览地图.md",
    ROOT / "scripts" / "install-all.sh",
    ROOT / "scripts" / "install-all.ps1",
    ROOT / "scripts" / "build-production.sh",
    *sorted((ROOT / "deploy").rglob("*")),
    *sorted((ROOT / "docs" / "deployment").rglob("*.md")),
]

REQUIRED_CONTENT = {
    ROOT / "environment.yml": ["python=3.12", "nodejs=22", "pnpm=10.28", "ffmpeg>=6"],
    ROOT / ".env.example": [
        "VITE_API_BASE_URL=/backend",
        "STORAGE_ROOT=/data/edu_ai/storage",
        "OPENMAIC_DATA_ROOT=/data/edu_ai/openmaic",
    ],
    ROOT / "deploy" / "nginx" / "edu-ai.conf": [
        "root /home/zxqs_ep/Edu_AI/frontend/dist;",
        "proxy_pass http://127.0.0.1:8001/;",
    ],
    ROOT / "deploy" / "systemd" / "edu-ai-backend.service": [
        "WorkingDirectory=/home/zxqs_ep/Edu_AI/backend/src",
        "--port 8001",
    ],
    ROOT / "deploy" / "systemd" / "edu-ai-openmaic.service": [
        "WorkingDirectory=/home/zxqs_ep/Edu_AI/openmaic-sidecar",
        "--port 3000",
    ],
}

REMOVED_PATHS = [
    ROOT / "backend" / "src" / ".env.example",
    ROOT / "backend" / "src" / "environment.yml",
    ROOT / "backend" / "src" / "start_api.bat",
    ROOT / "backend" / "src" / "start_simple_chat.sh",
    ROOT / "deploy" / "postgres" / "compose.yml",
]

FORBIDDEN_ACTIVE_TEXT = [
    "Edu_AI/api",
    "Edu_AI/src",
    "nodejs=20",
    "python3.10",
    "python3.11",
    "npm ci",
    "npm install",
    "docker compose",
    "localhost:8000",
    "127.0.0.1:8000",
    "start_api",
    "start_simple_chat",
]


def main() -> int:
    errors: list[str] = []

    for path, snippets in REQUIRED_CONTENT.items():
        if not path.is_file():
            errors.append(f"missing required file: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} is missing: {snippet}")

    for path in REMOVED_PATHS:
        if path.exists():
            errors.append(f"obsolete deployment path still exists: {path.relative_to(ROOT)}")

    for path in ACTIVE_FILES:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for snippet in FORBIDDEN_ACTIVE_TEXT:
            if snippet.lower() in text.lower():
                errors.append(f"{path.relative_to(ROOT)} contains obsolete text: {snippet}")

    if errors:
        print("Deployment consistency check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Deployment consistency check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
