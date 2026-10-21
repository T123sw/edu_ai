"""Typed, bounded recovery decisions; never infer a retry from exception prose."""
from typing import Literal
from pydantic import model_validator
from .schemas import Contract, Identifier, ShortText
from .manifest import ContentDigest

MAX_RECOVERY_ATTEMPTS = 2
SCOPES = {'provider': 'provider', 'review_format': 'review', 'content': 'content',
          'render': 'content', 'contract': 'content', 'permission': 'none',
          'budget': 'none', 'canceled': 'none'}


class FailureDetail(Contract):
    code: Identifier
    phase: Identifier
    category: Literal['provider', 'review_format', 'content', 'render', 'contract', 'permission', 'budget', 'canceled']
    message: ShortText
    retry_scope: Literal['none', 'provider', 'review', 'content']
    artifact_id: Identifier | None = None
    content_digest: ContentDigest | None = None
    budget_metric: Literal['calls', 'tokens', 'cost_micro_usd'] | None = None

    @model_validator(mode='after')
    def validate_scope(self):
        if self.retry_scope not in ('none', SCOPES[self.category]):
            raise ValueError('FAILURE_RETRY_SCOPE_MISMATCH')
        return self


class GenerationFailure(RuntimeError):
    def __init__(self, detail: FailureDetail | dict):
        self.detail = FailureDetail.model_validate(detail)
        self.code = self.detail.code
        super().__init__(f'{self.code}: {self.detail.message}')


def recovery_scope(detail: FailureDetail | dict, *, attempts: int = 0) -> str:
    detail = FailureDetail.model_validate(detail)
    if detail.retry_scope == 'none' or attempts >= MAX_RECOVERY_ATTEMPTS:
        raise GenerationFailure(detail.model_copy(update={'retry_scope': 'none'}))
    return detail.retry_scope
