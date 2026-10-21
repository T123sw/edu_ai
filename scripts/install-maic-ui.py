"""Install the complete, pinned MAIC-UI repository used by the native adapter."""
from pathlib import Path
import subprocess

REVISION = 'aad58ddcc2103058b4c2deffc48a3c13e2c64dd6'
target = Path(__file__).resolve().parents[1] / '.runtime/maic-ui-native'
target.parent.mkdir(parents=True, exist_ok=True)
if not target.exists():
    subprocess.run(['git', 'clone', 'https://github.com/THU-MAIC/MAIC-UI.git', str(target)], check=True)
if subprocess.check_output(['git', '-C', str(target), 'status', '--porcelain'], text=True).strip():
    raise SystemExit('MAIC-UI checkout has local changes; preserve them before reinstalling.')
if subprocess.run(['git', '-C', str(target), 'cat-file', '-e', REVISION + '^{commit}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
    subprocess.run(['git', '-C', str(target), 'fetch', 'origin', REVISION], check=True)
subprocess.run(['git', '-C', str(target), 'checkout', '--detach', REVISION], check=True)
actual = subprocess.check_output(['git', '-C', str(target), 'rev-parse', 'HEAD'], text=True).strip()
assert actual == REVISION
print(f'Installed complete MAIC-UI repository at {actual}: {target}')
