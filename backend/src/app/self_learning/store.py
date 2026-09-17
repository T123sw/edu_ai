"""User-owned learning overlays, using the configured application-state backend."""
from __future__ import annotations
import hashlib
import json
import os
import threading
from pathlib import Path
from uuid import uuid4
from core.config import Config

lock = threading.RLock()

class LearningStore:
    def __init__(self, root=None, repository=None):
        self.root = Path(root or Config.STORAGE_ROOT) / 'self_learning'
        self.repository = repository
        if repository is None and os.getenv('APP_STATE_PERSISTENCE_MODE', 'json') == 'postgres':
            from app.persistence.dependencies import get_postgres_app_state_repository
            self.repository = get_postgres_app_state_repository()

    def _namespace(self, owner):
        return 'self_learning:' + hashlib.sha256(owner.encode()).hexdigest()

    def get(self, owner, key):
        namespace = self._namespace(owner)
        if self.repository:
            return self.repository.get(namespace, key) or {}
        path = self.root / namespace.split(':')[1] / (hashlib.sha256(key.encode()).hexdigest() + '.json')
        return json.loads(path.read_text()) if path.exists() else {}

    def put(self, owner, key, data):
        namespace = self._namespace(owner)
        if self.repository:
            self.repository.put(namespace, key, data, owner_user_id=owner)
            return
        directory = self.root / namespace.split(':')[1]
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (hashlib.sha256(key.encode()).hexdigest() + '.json')
        temporary = target.with_suffix('.' + uuid4().hex + '.tmp')
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
