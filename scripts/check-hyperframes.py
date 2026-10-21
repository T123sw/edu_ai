"""Check installed native runtime dependencies without contacting providers."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend/src'))
from app.integrations.hyperframes.runtime import NativeRuntime

bwrap = os.environ.get('HYPERFRAMES_BWRAP_PATH') or shutil.which('bwrap')
if sys.platform != 'linux' or not bwrap or not Path(bwrap).is_file():
    raise SystemExit('Native generation worker requires Linux bubblewrap (apt install bubblewrap).')

for executable in ('node', 'ffmpeg', 'ffprobe'):
    if not shutil.which(executable): raise SystemExit(f'Missing executable: {executable}')
if int(subprocess.check_output(['node','--version'],text=True).strip().lstrip('v').split('.')[0]) < 22:
    raise SystemExit('HyperFrames requires Node >=22')
for package in ('hyperframes', '@hyperframes/player'):
    manifest=ROOT/'hyperframes-runtime/node_modules'/package/'package.json'
    if not manifest.is_file() or json.loads(manifest.read_text())['version']!='0.8.168':
        raise SystemExit(f'Missing pinned runtime package: {package} 0.8.168')
browser = os.environ.get('HYPERFRAMES_BROWSER_PATH')
if not browser:
    candidates = list((Path.home()/'.cache/hyperframes/chrome').glob('**/chrome-headless-shell'))
    candidates += list((Path.home()/'.cache/puppeteer/chrome-headless-shell').glob('**/chrome-headless-shell'))
    browser = next((str(p) for p in candidates if p.is_file()), '')
if not browser or not Path(browser).is_file():
    raise SystemExit('Missing Chromium: run npm --prefix hyperframes-runtime exec -- hyperframes browser ensure, or set HYPERFRAMES_BROWSER_PATH')
print('Native HyperFrames packages, Chromium, bubblewrap, Node, ffmpeg and ffprobe are available.')
