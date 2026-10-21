"""Read-only evidence tools for the independent experiment teaching Agent.

The caller must obtain context through ExperimentRepository with authenticated
ownership. Evidence is data, never instructions or authority to advance tasks.
"""
from typing import Literal
from pydantic import Field
from .contracts import Contract

class EvidenceRequest(Contract):
    tool: Literal['get_design', 'get_snapshot', 'list_events', 'get_attempt', 'compare_snapshots', 'get_fact_summary', 'list_operations', 'get_operation']
    operation_id: str | None = Field(default=None, max_length=200)
    snapshot_id: str | None = Field(default=None, max_length=80)
    other_snapshot_id: str | None = Field(default=None, max_length=80)
    attempt_id: str | None = Field(default=None, max_length=80)
    after_seq: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


def read_evidence(context, request: EvidenceRequest):
    def snapshot(identifier):
        if identifier not in context['snapshots']: raise ValueError('快照不存在于此提问的冻结上下文中')
        return context['snapshots'][identifier]
    if request.tool in {'get_fact_summary', 'list_operations', 'get_operation'}:
        from .facts import timeline, summary, operation_detail, compact, current_state, recorded_completions
        operations, assessments = timeline(context)
        if request.tool == 'get_fact_summary':
            result = {'current': current_state(context), 'totals': summary(context, operations, assessments),
                      'recorded_completions': recorded_completions(context)}
        elif request.tool == 'get_operation':
            operation = next((o for o in operations if o['event']['id'] == request.operation_id), None)
            if operation is None: raise ValueError('操作不存在于此提问的冻结上下文中')
            result = operation_detail(context, operation)
        else:
            remaining = [o for o in operations if o['event']['seq'] > request.after_seq]
            page = remaining[:request.limit]
            result = {'items': [compact(o) for o in page], 'has_more': len(remaining) > len(page),
                      'next_seq': page[-1]['event']['seq'] if page else request.after_seq,
                      'total_operations': len(operations)}
    elif request.tool == 'get_design':
        result = context['design']
    elif request.tool == 'get_snapshot':
        result = snapshot(request.snapshot_id or str(context['state_revision']))
    elif request.tool == 'list_events':
        events = [e for e in context['events'] if e['seq'] > request.after_seq]
        result = {'items': events[:request.limit], 'has_more': len(events) > request.limit, 'next_seq': events[min(request.limit, len(events)) - 1]['seq'] if events else request.after_seq}
    elif request.tool == 'get_attempt':
        attempt = request.attempt_id or context['attempt_id']
        events = [e for e in context['events'] if e.get('attempt_id') == attempt]
        if not events and attempt != context['attempt_id']: raise ValueError('尝试不存在')
        refs = {e[k] for e in events for k in ['before', 'after']}
        result = {'attempt_id': attempt, 'events': events, 'snapshots': {k: snapshot(k) for k in refs}, 'assessment': [e for e in events if e.get('type') == 'attempt_submitted']}
    else:
        before, after = snapshot(request.snapshot_id), snapshot(request.other_snapshot_id)
        result = {'before_id': request.snapshot_id, 'after_id': request.other_snapshot_id, 'changes': [{'field': k, 'before_present': k in before, 'after_present': k in after, 'before': before.get(k), 'after': after.get(k)} for k in sorted(before.keys() | after.keys()) if k not in before or k not in after or before[k] != after[k]]}
    return {'context_version': context['context_version'], 'context_id': context['context_id'], 'revision': context['revision'], 'run_id': context['run_id'], 'state_revision': context['state_revision'], 'attempt_id': context['attempt_id'], 'evidence_source': 'browser_reported', 'result': result}


def response_matches_context(response, context):
    """Teacher output binds to its original question and never auto-advances."""
    return all(response.get(k) == context.get(k) for k in ['context_id', 'revision', 'run_id', 'state_revision', 'attempt_id'])
