"""Classrooms are delivered with structural validation, without model review."""

CLASSROOM_REVIEW_POLICY = 'classroom-no-extra-review-v1'


def can_resume_classroom_without_review(artifact):
    body = artifact.get('content') or {}
    failure = artifact.get('failure_detail') or body.get('_failure_detail') or {}
    candidate = body.get('_review_candidate') or {}
    return (artifact.get('resource_type') == 'classroom'
            and (failure.get('phase') == 'resource_review'
                 or (failure.get('phase') == 'classroom_write' and failure.get('code') in (
                     'CONTEXT_BUDGET_EXCEEDED', 'BUDGET_EXHAUSTED', 'CLASSROOM_BINDINGS_INVALID',
                     'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT', 'HARNESS_UNAVAILABLE')))
            and failure.get('code') not in ('CANCELED', 'RESOURCE_PERMISSION_DENIED', 'RESOURCE_LEASE_EXPIRED')
            and candidate.get('review_state', {}).get('generator') == 'openmaic-native'
            and bool(candidate.get('content', {}).get('scenes')))


def classroom_structure_receipt(content):
    from .reviewed_resource import digest
    return {'decision': 'skipped', 'method': 'structural_validation',
            'policy': CLASSROOM_REVIEW_POLICY, 'resource_type': 'classroom',
            'content_sha256': digest('classroom', content),
            'reason': '按用户要求，生成后不做额外模型审查；仅校验结构与可定位性。'}


def valid_classroom_structure_receipt(artifact, content):
    from .reviewed_resource import digest
    from .preparation_content import value_digest
    state = artifact.get('generation_state') or {}
    receipt = state.get('resource_review') or {}
    metadata = state.get('preparation')
    return (receipt.get('decision') == 'skipped'
            and receipt.get('method') == 'structural_validation'
            and receipt.get('policy') == CLASSROOM_REVIEW_POLICY
            and receipt.get('resource_type') == 'classroom'
            and receipt.get('content_sha256') == digest('classroom', content)
            and (metadata is None and 'preparation_sha256' not in receipt
                 or isinstance(metadata, dict) and receipt.get('preparation_sha256') == value_digest(metadata)))
