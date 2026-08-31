from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from .models import ResourceLearningManifestRecord
from .analytics import build_resource_learning_analytics
from .repository import ResourceLearningRepository


class ResourceLearningRuleError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ResourceLearningService:
    MAX_HEARTBEAT_SPAN_MS = 20_000
    EVENT_TYPES = frozenset(
        {
            "scene_entered",
            "timeline_heartbeat",
            "playback_paused",
            "scene_completed",
            "demo_entered",
            "demo_interacted",
            "demo_completed",
        }
    )

    def __init__(
        self,
        repository: ResourceLearningRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def freeze_manifest(self, manifest: ResourceLearningManifestRecord):
        return self.repository.freeze_manifest(manifest)

    def start_session(
        self,
        course_id: str,
        resource_id: str,
        resource_version: int,
        student_id: str,
    ):
        self._manifest(course_id, resource_id, resource_version)
        return self.repository.start_session(
            course_id=course_id,
            resource_id=resource_id,
            resource_version=resource_version,
            student_id=student_id,
            now=self._clock(),
        )

    def record_events(
        self,
        session_id: str,
        student_id: str,
        events: Sequence[Mapping[str, Any]],
    ):
        session = self.repository.get_session(session_id)
        if session is None:
            raise ResourceLearningRuleError("SESSION_NOT_FOUND", "session was not found")
        if session.status != "active":
            raise ResourceLearningRuleError("SESSION_INACTIVE", "session is not active")
        manifest = self._manifest(
            session.course_id, session.resource_id, session.resource_version
        )
        scene_by_id = {item.scene_id: item for item in manifest.scenes}
        validated: list[Mapping[str, Any]] = []
        for event in events:
            event_type = str(event.get("event_type") or "")
            if event_type not in self.EVENT_TYPES:
                raise ResourceLearningRuleError("EVENT_TYPE_INVALID", "event type is invalid")
            scene_id = str(event.get("scene_id") or "")
            scene = scene_by_id.get(scene_id)
            if scene is None:
                raise ResourceLearningRuleError("SCENE_NOT_FOUND", "scene is not in the learning manifest")
            if not str(event.get("event_id") or "").strip():
                raise ResourceLearningRuleError("EVENT_ID_REQUIRED", "event id is required")
            try:
                sequence_number = int(event.get("sequence_number"))
            except (TypeError, ValueError) as error:
                raise ResourceLearningRuleError("SEQUENCE_INVALID", "sequence number is invalid") from error
            if sequence_number <= 0:
                raise ResourceLearningRuleError("SEQUENCE_INVALID", "sequence number is invalid")
            if event_type == "timeline_heartbeat":
                if scene.kind != "explanation":
                    raise ResourceLearningRuleError(
                        "SCENE_NOT_EXPLANATION", "timeline heartbeat scene is not an explanation"
                    )
                start = event.get("timeline_from_ms")
                end = event.get("timeline_to_ms")
                if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
                    raise ResourceLearningRuleError("TIMELINE_INVALID", "timeline range is invalid")
                if end - start > self.MAX_HEARTBEAT_SPAN_MS:
                    raise ResourceLearningRuleError(
                        "TIMELINE_SPAN_TOO_LONG", "timeline heartbeat cannot exceed 20 seconds"
                    )
                if end > scene.expected_duration_ms:
                    raise ResourceLearningRuleError(
                        "TIMELINE_OUT_OF_RANGE", "timeline range exceeds the scene duration"
                    )
            if event_type.startswith("demo_") and scene.kind != "demo":
                raise ResourceLearningRuleError("SCENE_NOT_DEMO", "demo event scene is not a demo")
            validated.append(event)
        try:
            return self.repository.record_events(
                session_id=session_id,
                student_id=student_id,
                events=validated,
                now=self._clock(),
            )
        except PermissionError as error:
            raise ResourceLearningRuleError("SESSION_OWNER_MISMATCH", "session owner mismatch") from error
        except ValueError as error:
            message = str(error)
            code = "SEQUENCE_CONFLICT" if "sequence" in message else "EVENT_REJECTED"
            raise ResourceLearningRuleError(code, message) from error

    def submit_questions(
        self,
        course_id: str,
        resource_id: str,
        resource_version: int,
        student_id: str,
        answers: Mapping[str, object],
        idempotency_key: str,
    ):
        if not idempotency_key.strip():
            raise ResourceLearningRuleError("IDEMPOTENCY_KEY_REQUIRED", "idempotency key is required")
        manifest = self._manifest(course_id, resource_id, resource_version)
        questions = {item.question_id: item for item in manifest.questions}
        if not answers:
            raise ResourceLearningRuleError("ANSWERS_REQUIRED", "at least one answer is required")
        for question_id, answer in answers.items():
            if question_id not in questions:
                raise ResourceLearningRuleError("QUESTION_NOT_FOUND", "question is not in the manifest")
            if isinstance(answer, str):
                valid = bool(answer.strip())
            elif isinstance(answer, Sequence):
                valid = bool(answer) and all(bool(str(item).strip()) for item in answer)
            else:
                valid = False
            if not valid:
                raise ResourceLearningRuleError("ANSWER_INVALID", "answer must not be empty")
        return self.repository.submit_questions(
            course_id=course_id,
            resource_id=resource_id,
            resource_version=resource_version,
            student_id=student_id,
            answers=answers,
            idempotency_key=idempotency_key,
            now=self._clock(),
        )

    def end_session(self, session_id: str, student_id: str):
        try:
            return self.repository.end_session(
                session_id=session_id, student_id=student_id, now=self._clock()
            )
        except KeyError as error:
            raise ResourceLearningRuleError("SESSION_NOT_FOUND", "session was not found") from error
        except PermissionError as error:
            raise ResourceLearningRuleError("SESSION_OWNER_MISMATCH", "session owner mismatch") from error

    def get_my_progress(
        self,
        course_id: str,
        resource_id: str,
        resource_version: int,
        student_id: str,
    ):
        progress = self.repository.get_progress(
            course_id, resource_id, resource_version, student_id
        )
        if progress is None:
            raise ResourceLearningRuleError("PROGRESS_NOT_FOUND", "learning progress was not found")
        return progress

    def list_my_course_progress(self, course_id: str, student_id: str):
        return [
            progress
            for _owner, progress in self.repository.list_progress(
                course_id=course_id, student_id=student_id
            )
        ]

    def get_student_progress(
        self,
        course_id: str,
        resource_id: str,
        resource_version: int,
        student_id: str,
    ):
        return self.get_my_progress(
            course_id, resource_id, resource_version, student_id
        )

    def list_student_progress(
        self, course_id: str, resource_id: str, resource_version: int
    ):
        return self.repository.list_progress(
            course_id=course_id,
            resource_id=resource_id,
            resource_version=resource_version,
        )

    def get_analytics(
        self,
        course_id: str,
        resource_id: str,
        resource_version: int,
        enrolled_student_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        records = self.list_student_progress(course_id, resource_id, resource_version)
        enrolled = (
            list(enrolled_student_ids)
            if enrolled_student_ids is not None
            else [student_id for student_id, _progress in records]
        )
        return build_resource_learning_analytics(
            manifest=self._manifest(course_id, resource_id, resource_version),
            progress_records=records,
            question_attempts=self.repository.list_question_attempts(
                course_id=course_id,
                resource_id=resource_id,
                resource_version=resource_version,
            ),
            enrolled_student_ids=enrolled,
        )

    def _manifest(self, course_id: str, resource_id: str, resource_version: int):
        manifest = self.repository.get_manifest(course_id, resource_id, resource_version)
        if manifest is None:
            raise ResourceLearningRuleError("MANIFEST_NOT_FOUND", "learning manifest was not found")
        return manifest
