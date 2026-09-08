"""Single-host pilot store. Atomic state and a cross-process conversation lock."""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock


class HarnessStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def report_source(self, request, task_id):
        """Recover legacy provenance only; never return or merge private history."""
        if not request.owner or not request.course_id:
            return None
        sources = set()
        for path in self.root.glob("*/state.json"):
            try:
                data = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict) or task_id not in (data.get("jobs") or {}):
                continue
            for record in data.get("responses", {}).values():
                identity = record.get("request") or {}
                if (identity.get("owner") == request.owner and identity.get("course_id") == request.course_id
                        and identity.get("conversation_id")):
                    sources.add(identity["conversation_id"])
        return next(iter(sources)) if len(sources) == 1 else None

    def directory(self, request) -> Path:
        if not request.owner or not request.conversation_id:
            raise ValueError("Harness requires an authenticated conversation")
        identity = [request.owner, request.course_id, request.conversation_id]
        key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        directory = self.root / key
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        return directory

    @contextmanager
    def session(self, request):
        directory = self.directory(request)
        with FileLock(str(directory / "session.lock"), timeout=0):
            path = directory / "state.json"
            state = json.loads(path.read_text()) if path.exists() else {
                "version": 1, "history": [], "evidence": {}, "outlines": {},
                "active_outline": None, "jobs": {}, "responses": {},
            }
            session = SessionState(directory, state)
            if not path.exists():
                self._migrate_legacy(request, session)
            yield session

    def _migrate_legacy(self, request, session):
        # Old shards carry authenticated request identities in response records.
        # Never infer ownership from model text or filenames alone.
        candidates = []
        for path in self.root.glob("*/state.json"):
            if path.parent == session.directory:
                continue
            data = json.loads(path.read_text())
            records = list(data.get("responses", {}).values())
            matching = [r.get("request", {}) for r in records if all(r.get("request", {}).get(k) == getattr(request, k)
                         for k in ("owner", "course_id", "conversation_id"))]
            if matching:
                candidates.append((path.stat().st_mtime, path, matching[-1]))
        for _, path, old_request in sorted(candidates):
            with FileLock(str(path.parent / "session.lock"), timeout=0):
                data = json.loads(path.read_text())
                scope = {"scope_type": old_request.get("scope_type") or "course", "scope_id": old_request.get("scope_id")}
                for group in ("outlines", "evidence", "organizations"):
                    for item in data.get(group, {}).values():
                        if "source_policy" in item:
                            for k, v in scope.items(): item["source_policy"].setdefault(k, v)
                        if group == "outlines": item.setdefault("workspace", scope)
                for group in ("outlines", "evidence", "organizations", "jobs", "responses"):
                    session.data.setdefault(group, {}).update(data.get(group, {}))
                session.data["history"].extend(data.get("history", []))
                if data.get("active_outline"): session.data["active_outline"] = data["active_outline"]
                if data.get("knowledge_plan"): session.data["knowledge_plan"] = data["knowledge_plan"]
        session.data["history"] = session.data["history"][-20:]
        session.data["version"] = 2
        session.save()


class SessionState:
    def __init__(self, directory, data):
        self.directory, self.data = directory, data

    def save(self):
        path = self.directory / "state.tmp"
        with path.open("w", encoding="utf-8") as stream:
            json.dump(self.data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, self.directory / "state.json")

    def event(self, event):
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
