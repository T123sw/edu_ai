import hashlib
import json
from .runtime_contracts import MountedTools


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


class ToolRegistry:
    def __init__(self, specs):
        self.specs = tuple(specs)
        if len({s.name for s in self.specs}) != len(self.specs):
            raise ValueError('duplicate tool name')
        if any(not callable(s.handler) or not hasattr(s.arguments, 'model_validate') for s in self.specs):
            raise ValueError('tool schema/handler pair required')

    def mount(self, context, *, remaining_calls=200):
        selected = tuple(s for s in self.specs if
            (not s.stages or context.stage in s.stages) and context.operation in s.operations and
            not (s.network and context.source_policy == 'uploaded_only') and
            (s.capability is None or s.capability in context.capabilities) and s.cost.calls <= remaining_calls)
        schemas = tuple({'type': 'function', 'function': {'name': s.name, 'parameters': s.arguments.model_json_schema()}}
                        for s in selected)
        signature = {'stage': context.stage, 'operation': context.operation, 'source_policy': context.source_policy,
                     'capabilities': context.capabilities, 'schemas': schemas,
                     'policies': [{'readonly': s.readonly, 'network': s.network, 'cost': s.cost.model_dump()} for s in selected]}
        return MountedTools(selected, digest(signature), schemas)
