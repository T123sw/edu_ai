"""Reassign provisional repair slots using completed siblings, never user budgets."""
from decimal import Decimal, ROUND_FLOOR
import math

from .resource_alignment import preparation_metadata


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def reallocate_duration_caps(artifacts, nodes, hard_limit, origins):
    rows = [row for row in artifacts if row['spec'].get('required', True)]
    known, pending = {}, {}
    for row in rows:
        key = row['artifact_id']
        duration = preparation_metadata(row).get('duration', {})
        value = duration.get('value_minutes')
        if row['status'] == 'draft' and duration.get('basis') in ('estimated', 'measured') and _positive(value):
            known[key] = Decimal(str(value))
        else:
            cap = (row['spec'].get('teaching_context') or {}).get('resource_target_minutes')
            if ((row.get('failure_detail') or {}).get('code') == 'RESOURCE_DURATION_EXCEEDED'
                    and row['spec_digest'] in origins and _positive(cap)
                    and not key.startswith('retained:')):
                pending[key] = Decimal(str(cap))
    # Unavailable/unknown resources must not be treated as consuming zero time.
    if hard_limit is not None and (not _positive(hard_limit)
            or any(r['artifact_id'] not in known and r['artifact_id'] not in pending for r in rows)):
        return {}
    targets = {}
    for node in nodes:
        members = [r for r in rows if r['spec']['node_id'] == node['node_key']]
        keys = [r['artifact_id'] for r in members]
        selected = [key for key in keys if key in pending]
        if not selected or not _positive(node.get('minutes')) or any(key not in known and key not in pending for key in keys):
            continue
        available = Decimal(str(node['minutes'])) - sum((known.get(key, Decimal(0)) for key in keys), Decimal(0))
        if available <= 0:
            continue
        weight = sum(pending[key] for key in selected)
        for row in members:
            key = row['artifact_id']
            if key not in pending:
                continue
            target = available * pending[key] / weight
            original = origins[row['spec_digest']]
            if original is not None:
                if not _positive(original):
                    continue
                target = min(target, Decimal(str(original)))
            targets[key] = target
    if hard_limit is not None:
        # Pending resources without a provable node slot prevent global release.
        if set(pending) != set(targets):
            return {}
        available = Decimal(str(hard_limit)) - sum(known.values(), Decimal(0))
        total = sum(targets.values(), Decimal(0))
        if available <= 0 or total <= 0:
            return {}
        if total > available:
            targets = {key: target * available / total for key, target in targets.items()}
    return {key: float(target.quantize(Decimal('.01'), rounding=ROUND_FLOOR))
            for key, target in targets.items() if target >= Decimal('.01')}
