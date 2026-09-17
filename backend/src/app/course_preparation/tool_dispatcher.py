"""Validate an entire decision before reserving or executing any of its tools."""
from .runtime_contracts import ToolCall


class ToolDispatcher:
    def __init__(self, registry, repository):
        self.registry, self.repository = registry, repository

    def dispatch(self, context, calls):
        calls = tuple(ToolCall.model_validate(c.model_dump() if isinstance(c, ToolCall) else c) for c in calls)
        if not calls or len(calls) > 4 or len({c.call_id for c in calls}) != len(calls):
            raise ValueError('INVALID_TOOL_BATCH')
        budget = self.repository.get_public(context.owner_user_id, context.preparation_id)['budget']
        remaining = budget['limits']['calls'] - budget['consumed']['calls'] - budget['reserved']['calls']
        mounted = self.registry.mount(context, remaining_calls=remaining)
        allowed = {s.name: s for s in mounted.tools}
        prepared = []
        for call in calls:
            if call.name not in allowed:
                raise ValueError('TOOL_NOT_MOUNTED')
            spec = allowed[call.name]
            prepared.append((call, spec, spec.arguments.model_validate(call.arguments)))
        if any(not s.readonly for _, s, _ in prepared) and len(prepared) != 1:
            raise ValueError('WRITE_MUST_BE_SINGLE_ACTION')
        # Aggregate preflight; SQL reservation remains the authoritative concurrent gate.
        for metric in ('calls', 'tokens', 'cost_micro_usd'):
            total = sum(getattr(s.cost, metric) for _, s, _ in prepared)
            if budget['reserved'][metric] + budget['consumed'][metric] + total > budget['limits'][metric]:
                raise ValueError('BATCH_BUDGET_EXCEEDED')
        results = []
        for call, spec, args in prepared:
            action = self.repository.begin_action(context, 'tool:' + call.call_id, spec.name,
                {'arguments': args.model_dump(mode='json'), 'tool_set_digest': mounted.digest}, spec.cost)
            if action['status'] in ('completed', 'failed'):
                results.append(action['receipt'])
                continue
            receipt = None
            recovery = None
            if action['replay'] and spec.readonly:
                recovery = self.repository.begin_action(context,
                    'read-recovery:' + action['action_id'] + ':' + context.lease_token, spec.name,
                    {'recovery_of': action['action_id']}, spec.cost)
                if recovery['status'] == 'completed':
                    receipt = recovery['receipt']
            if action['replay'] and not spec.readonly:
                if spec.reconcile is None:
                    raise ValueError('UNKNOWN_WRITE_REQUIRES_RECONCILIATION')
                receipt = spec.reconcile(args, context, action['action_id'])
            if receipt is None:
                # Stable action ID is the downstream idempotency key, never a generated model field.
                receipt = spec.handler(args, context, action['action_id'])
            if recovery is not None:
                self.repository.finish_action(context, recovery['action_id'], receipt)
            self.repository.finish_action(context, action['action_id'], receipt)
            results.append(receipt)
        return {'tool_set_digest': mounted.digest, 'results': results}
