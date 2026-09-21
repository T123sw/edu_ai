"""Server-only capability for private candidates, never a model tool/payload.

The artifact JSON envelope is private until ArtifactStore.save replaces it with
an independently reviewed artifact. No new table or migration is required.
"""
from copy import deepcopy
from typing import Protocol
from sqlalchemy.orm import Session
from .tool_registry import digest


class ResourceCheckpointPort(Protocol):
    def load_review_candidate(self) -> dict | None: ...
    def save_review_candidate(self, *, content: dict | str, content_digest: str,
                              spec_digest: str, review_state: dict) -> None: ...


class ArtifactResourceCheckpoint:
    def __init__(self, store, context):
        self._store, self._context = store, deepcopy(context)

    def load_review_candidate(self):
        with Session(self._store.engine) as session, session.begin():
            row, prep, attempt, _ = self._store._locked(session, self._context)
            candidate = (row.content or {}).get('_review_candidate')
            if candidate is None:
                return None
            self._validate(candidate, row, prep, attempt)
            return deepcopy(candidate)

    @staticmethod
    def _validate(candidate, row, prep, attempt):
        if (digest(row.content) != row.content_digest
                or candidate['owner_user_id'] != row.owner_user_id
                or candidate['preparation_id'] != prep.preparation_id
                or candidate['parent_attempt_no'] != attempt.attempt_no
                or candidate['artifact_id'] != row.artifact_id
                or candidate['resource_id'] != row.resource_id
                or candidate['resource_version'] != row.resource_version
                or candidate['spec_digest'] != row.spec_digest
                or digest(row.spec) != row.spec_digest
                or candidate['content_digest'] != digest(candidate['content'])
                or candidate['teaching_context_digest'] != digest(row.spec.get('teaching_context'))):
            raise ValueError('REVIEW_CANDIDATE_STALE')

    def save_review_candidate(self, *, content, content_digest, spec_digest, review_state):
        if digest(content) != content_digest:
            raise ValueError('REVIEW_CANDIDATE_CONTENT_MISMATCH')
        with Session(self._store.engine) as session, session.begin():
            row, prep, attempt, _ = self._store._locked(session, self._context)
            if row.spec_digest != spec_digest or digest(row.spec) != spec_digest:
                raise ValueError('REVIEW_CANDIDATE_SPEC_MISMATCH')
            previous = (row.content or {}).get('_review_candidate') or (row.content or {}).get('_generation_recovery')
            candidate = {'schema_version': 1, 'owner_user_id': row.owner_user_id,
                'preparation_id': prep.preparation_id, 'parent_attempt_no': attempt.attempt_no,
                'artifact_id': row.artifact_id, 'resource_id': row.resource_id,
                'resource_version': row.resource_version, 'spec_digest': spec_digest,
                'teaching_context_digest': digest(row.spec.get('teaching_context')),
                'content': deepcopy(content), 'content_digest': content_digest,
                'review_state': deepcopy(review_state),
                'recovery_attempt': previous.get('recovery_attempt', 0) if previous else 0}
            # A review-only retry cannot silently rewrite the saved body.
            if previous and previous.get('recovery_scope') == 'review' and previous['content_digest'] != content_digest:
                raise ValueError('REVIEW_RETRY_CHANGED_CONTENT')
            if previous:
                for key in ('recovery_scope','recovery_key','recovery_receipt'):
                    if key in previous: candidate[key] = deepcopy(previous[key])
            row.content = {'_review_candidate': candidate}
            row.content_digest = digest(row.content)
