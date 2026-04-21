import os
import subprocess
import sys
import time
import webbrowser


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIVETALKING_DIR = os.path.join(BASE_DIR, "LiveTalking-main")
BACKEND_ENV_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", ".env"))


def _load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND_ENV_PATH, override=True)
except Exception:
    _load_env_file(BACKEND_ENV_PATH)


def _quote(value: str) -> str:
    return f'"{value}"'


def _python_executable() -> str:
    conda_env = os.getenv("AI_LECTURER_CONDA_ENV", "").strip()
    if os.getenv("AI_LECTURER_PYTHON", "").strip():
        return os.getenv("AI_LECTURER_PYTHON", "").strip()
    if conda_env:
        return "python"
    return sys.executable


def _base_command(workdir: str) -> str:
    conda_env = os.getenv("AI_LECTURER_CONDA_ENV", "").strip()
    commands: list[str] = []
    if conda_env:
        commands.append(f"call conda activate {_quote(conda_env)}")
    commands.append(f"cd /d {_quote(workdir)}")
    return " && ".join(commands)


def _start_named_window(
    title: str,
    command: list[str],
    *,
    cwd: str,
    extra_env: dict[str, str] | None = None,
) -> None:
    env = os.environ.copy()
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})

    conda_env = os.getenv("AI_LECTURER_CONDA_ENV", "").strip()
    if conda_env:
        escaped_args = " ".join(_quote(str(part)) for part in command)
        full_command = f"{_base_command(cwd)} && {escaped_args}"
        escaped_command = full_command.replace('"', '""')
        subprocess.Popen(
            f'start "{title}" cmd /k "{escaped_command}"',
            shell=True,
            cwd=cwd,
            env=env,
        )
        return

    subprocess.Popen(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )


def start_engines():
    print("==================================================")
    print("        Starting AI Lecturer unified stack")
    print("==================================================")

    python_exe = _python_executable()
    hf_endpoint = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
    avatar_id = os.getenv("AI_LECTURER_AVATAR_ID", "my_teacher")
    ref_file = os.getenv("AI_LECTURER_REF_FILE", "zh-CN-XiaoxiaoNeural")
    model = os.getenv("AI_LECTURER_MODEL", "wav2lip")
    tts = os.getenv("AI_LECTURER_TTS", "edgetts")

    print("\n[1/3] Starting LiveTalking WebRTC engine on port 8010...")
    livetalking_command = [
        python_exe,
        "app.py",
        "--transport",
        "webrtc",
        "--model",
        model,
        "--avatar_id",
        avatar_id,
        "--tts",
        tts,
        "--REF_FILE",
        ref_file,
    ]
    _start_named_window(
        "LiveTalking WebRTC (8010)",
        livetalking_command,
        cwd=LIVETALKING_DIR,
        extra_env={"HF_ENDPOINT": hf_endpoint},
    )

    print("      Waiting for LiveTalking to initialize...")
    time.sleep(float(os.getenv("AI_LECTURER_LIVETALKING_BOOT_WAIT_SEC", "8")))

    print("\n[2/3] Starting AI Lecturer unified gateway on port 8008...")
    gateway_command = [python_exe, "unified_gateway.py"]
    _start_named_window("AI Lecturer Gateway (8008)", gateway_command, cwd=BASE_DIR)

    print("      Waiting for gateway to initialize...")
    time.sleep(float(os.getenv("AI_LECTURER_GATEWAY_BOOT_WAIT_SEC", "4")))


def open_dashboard():
    print("\n[3/3] Opening AI Lecturer gateway docs...")
    webbrowser.open("http://127.0.0.1:8008/docs")
    print("\nStartup commands were issued.")
    print("Check http://127.0.0.1:8010/webrtcapi.html for LiveTalking WebRTC.")
    print("Check http://127.0.0.1:8008/docs for the gateway.")
    print("==================================================")


if __name__ == "__main__":
    start_engines()
    open_dashboard()
