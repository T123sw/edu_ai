"""Install the full pinned upstream in this service's own Python environment."""
from pathlib import Path
import subprocess
import sys

from prepare_upstream import ROOT, prepare


def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Use Python 3.12 to reproduce this dependency lock")
    source = ROOT / ".upstream" / "DeepTutor"
    prepare(source)
    venv = ROOT / ".venv"
    if not venv.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    if "include-system-site-packages = false" not in (venv / "pyvenv.cfg").read_text().lower():
        raise SystemExit("The service environment must not inherit system site-packages")
    python = str(venv / "bin" / "python")
    subprocess.run([python, "-m", "pip", "install", "-r", str(ROOT / "requirements.lock.txt")], check=True)
    subprocess.run([python, "-m", "pip", "install", "--no-deps", "-e", str(source), "-e", str(ROOT) + "[test]"], check=True)
    subprocess.run([python, "-m", "pip", "check"], check=True)


if __name__ == "__main__":
    main()
