#!/usr/bin/env python3
"""Install the reusable Chinese font once; generation does not download fonts."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / 'hyperframes-runtime/assets/fonts'
FILES = {
    'NotoSansSC-Variable.ttf': ('NotoSansSC%5Bwght%5D.ttf', 'a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da'),
    'OFL-NotoSansSC.txt': ('OFL.txt', '1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9'),
}

if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, (remote, digest) in FILES.items():
        target = ROOT / name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            print(name + ': ready')
            continue
        with urllib.request.urlopen('https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/' + remote, timeout=120) as response:
            body = response.read()
        if hashlib.sha256(body).hexdigest() != digest:
            raise RuntimeError('Upstream font changed; verify before updating the pinned checksum')
        temp = target.with_suffix('.download')
        temp.write_bytes(body)
        temp.replace(target)
        print(name + ': installed')
