from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.services.generation_source_resolver import SourceDocumentRecord


@dataclass
class FakeDocumentCatalog:
    records: list[SourceDocumentRecord]
    list_calls: list[str] = field(default_factory=list)
    get_calls: list[str] = field(default_factory=list)

    def list_for_course(self, course_id: str):
        self.list_calls.append(course_id)
        return [item for item in self.records if item.course_id == course_id]

    def get_by_public_id(self, document_id: str):
        self.get_calls.append(document_id)
        return next(
            (item for item in self.records if item.document_id == document_id),
            None,
        )


@dataclass
class FakeDocumentContentReader:
    content_by_key: dict[str, str]
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def read_many(self, rag_index_keys):
        keys = tuple(rag_index_keys)
        self.calls.append(keys)
        return "\n\n".join(
            self.content_by_key[key]
            for key in keys
            if self.content_by_key.get(key)
        )

    def search_many(self, rag_index_keys, query_text, top_k=12):
        return self.read_many(rag_index_keys)


class NoNetworkGenerationProvider:
    def __init__(
        self,
        resource_type: str,
        *,
        entered: threading.Event | None = None,
        release: threading.Event | None = None,
    ) -> None:
        self.resource_type = resource_type
        self.entered = entered
        self.release = release
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        payload,
        *,
        job_id,
        config_snapshot_id,
        execution_context,
    ):
        self.calls.append(
            {
                "job_id": job_id,
                "config_snapshot_id": config_snapshot_id,
                "source_mode": execution_context.source.mode,
                "source_context": execution_context.source.context_text,
                "source_snapshot": execution_context.source.to_snapshot(),
                "payload": payload,
            }
        )
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            if not self.release.wait(timeout=5):
                raise TimeoutError("blocked fake provider was not released")
        return {
            "artifacts": [
                {
                    "artifact_type": self.resource_type,
                    "title": f"{self.resource_type} acceptance artifact",
                    "content": {
                        "resource_type": self.resource_type,
                        "generated_by": "deterministic-fake",
                    },
                }
            ]
        }


def fake_classroom_result(classroom_id: str) -> dict[str, Any]:
    return {
        "id": classroom_id,
        "url": f"http://fake-sidecar/classroom/{classroom_id}",
        "createdAt": "2026-08-07T00:00:00Z",
        "scenesCount": 1,
        "stage": {"id": classroom_id, "name": "Acceptance classroom"},
        "scenes": [
            {
                "id": "scene-1",
                "type": "slide",
                "content": {
                    "type": "slide",
                    "canvas": {
                        "id": "slide-1",
                        "viewportRatio": 0.5625,
                        "elements": [{"id": "text-1", "type": "text"}],
                    },
                },
                "actions": [
                    {"id": "speech-1", "type": "speech", "text": "hello"}
                ],
            }
        ],
    }

