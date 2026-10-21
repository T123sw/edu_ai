"""Prepare an explicit user retry without reusing expired child jobs.

Completed drafts and source evidence survive verbatim. Incomplete resource
specifications get new revisions/jobs; their old artifacts remain diagnostic
records so late provider usage can still settle against the shared budget.
"""
from copy import deepcopy

from sqlalchemy import select

from app.database.models import PreparationArtifact as Artifact
from .tool_registry import digest


def prepare_retry_checkpoint(session, prep, attempt, checkpoint, *, node_id=None):
    checkpoint = deepcopy(checkpoint)
    specifications = checkpoint.get('resource_specs') or []
    if node_id is not None and not any(s['node_id'] == node_id for s in specifications):
        raise ValueError('RETRY_NODE_UNAVAILABLE')
    if node_id is None:
        checkpoint.pop('retry_node_id', None)
    else:
        checkpoint['retry_node_id'] = node_id
    if not specifications:
        # A manual retry starts a new bounded repair attempt, keeping the
        # sources, plan and review feedback that explain the prior failure.
        state = checkpoint.get('research_state')
        if state:
            state['repairs'] = 0
        checkpoint.pop('node_research_repairs', None)
        return checkpoint, attempt.stage, {}
    artifacts = session.scalars(select(Artifact).where(
        Artifact.preparation_id == prep.preparation_id).with_for_update()).all()
    by_spec = {row.spec_digest: row for row in artifacts}
    restarted, retained, revised = [], [], []
    receipts = dict(checkpoint.get('generation_receipts', {}))
    from app.chat.harness.classroom_policy import can_resume_classroom_without_review
    for spec in specifications:
        key = digest(spec)
        artifact = by_spec.get(key)
        if node_id is not None and spec['node_id'] != node_id:
            revised.append(spec)
            continue
        if artifact is None:
            revised.append(spec)
            continue
        if artifact.owner_user_id != prep.owner_user_id or digest(artifact.spec) != key:
            raise ValueError('RETRY_ARTIFACT_IDENTITY_MISMATCH')
        if artifact.status == 'draft':
            if artifact.content is None or digest(artifact.content) != artifact.content_digest:
                raise ValueError('ARTIFACT_CONTENT_MISMATCH')
            retained.append(artifact.artifact_id)
            revised.append(spec)
        elif can_resume_classroom_without_review({'resource_type': artifact.resource_type,
                'status': artifact.status, 'content': artifact.content}):
            # Existing policy migration can safely adopt this exact candidate.
            revised.append(spec)
        else:
            revision = {**spec, 'revision': spec.get('revision', 1) + 1}
            candidate = (artifact.content or {}).get('_review_candidate')
            if artifact.status == 'failed' and artifact.resource_type in ('report', 'quiz') and candidate:
                from .resource_checkpoint import ArtifactResourceCheckpoint
                ArtifactResourceCheckpoint._validate(candidate, artifact, prep, attempt)
                feedback = [*spec.get('revision_feedback', []), *candidate.get('review_state', {}).get('feedback', [])]
                message = ((artifact.content or {}).get('_failure_detail') or {}).get('message')
                if message:
                    feedback.append(message)
                revision.update(original_content=deepcopy(candidate['content']),
                    revision_feedback=list(dict.fromkeys(feedback)))
            revised.append(revision)
            restarted.append(artifact.artifact_id)
            receipts.pop(key, None)
    if restarted:
        checkpoint.update(resource_specs=revised, generation_receipts=receipts,
            artifact_results={k: v for k, v in checkpoint.get('artifact_results', {}).items() if k in receipts})
        checkpoint['manual_retry_resources'] = [*checkpoint.get('manual_retry_resources', []),
            {'retry_of': attempt.attempt_no, 'superseded_artifact_ids': restarted}]
        for key in ('artifacts', 'quality', 'candidate_manifest'):
            checkpoint.pop(key, None)
    return checkpoint, 'produce' if restarted or node_id is not None else attempt.stage, {
        'retained_artifact_ids': retained, 'restarted_artifact_ids': restarted}
