"""Content-addressed immutable native multi-file projects."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from .contracts import safe_path


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def manifest_digest(files):
    return digest_bytes(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())


class ProjectStore:
    def __init__(self, root=None):
        self.root = Path(root or Path(os.environ.get('COURSE_STORAGE_ROOT', 'data/course_storage')) / 'hyperframes' / 'projects').absolute()

    def _directory(self, project):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', project['id']) or not re.fullmatch(r'[0-9a-f]{64}', project['digest']):
            raise ValueError('Invalid project identity')
        directory = self.root / project['id'] / project['digest']
        self._no_symlinks(directory)
        return directory

    def _no_symlinks(self, path):
        for item in (path, *path.parents):
            if item.is_symlink(): raise ValueError('Project symlinks are forbidden')

    def publish(self, project_id, files):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', project_id): raise ValueError('Invalid project ID')
        data = {}
        for name, value in files.items():
            safe_path(name)
            if isinstance(value, Path):
                self._no_symlinks(value)
                value = value.read_bytes()
            if isinstance(value, str): value = value.encode()
            if not isinstance(value, bytes): raise ValueError('Expected bytes, text or Path')
            data[name] = value
        if 'index.html' not in data: raise ValueError('Missing index.html')
        hashes = {name: digest_bytes(value) for name, value in data.items()}
        project = {'id': project_id, 'digest': manifest_digest(hashes), 'entry': 'index.html'}
        directory = self._directory(project)
        directory.parent.mkdir(parents=True, exist_ok=True)
        if not directory.exists():
            staging = Path(tempfile.mkdtemp(prefix='.publish-', dir=directory.parent))
            try:
                for name, value in data.items():
                    destination = staging / 'files' / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(value)
                (staging / 'manifest.json').write_text(json.dumps(hashes, sort_keys=True))
                try: staging.rename(directory)
                except OSError:
                    if not directory.exists(): raise
            finally:
                if staging.exists(): shutil.rmtree(staging)
        for name in data: self.file(project, name)
        return project

    def manifest(self, project):
        path = self._directory(project) / 'manifest.json'
        self._no_symlinks(path)
        hashes = json.loads(path.read_text())
        if manifest_digest(hashes) != project['digest']: raise ValueError('Project digest mismatch')
        return hashes

    def file(self, project, path):
        safe_path(path)
        hashes = self.manifest(project)
        if path not in hashes: raise FileNotFoundError(path)
        target = self._directory(project) / 'files' / path
        self._no_symlinks(target)
        if digest_bytes(target.read_bytes()) != hashes[path]: raise ValueError('Project file digest mismatch')
        return target
